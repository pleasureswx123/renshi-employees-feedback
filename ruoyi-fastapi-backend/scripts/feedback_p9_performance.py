"""在隔离库用真实领域服务建立数据，测量待办、进度、报告并保存执行计划。"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import uuid
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
MIN_TARGETS, MAX_TARGETS = 2, 1000
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import event, select, true  # noqa: E402

from config.database import create_async_db_engine, create_async_session_factory  # noqa: E402
from config.env import DataSourceSettings  # noqa: E402
from module_admin.entity.do.user_do import SysUser  # noqa: E402
from module_feedback.entity.do import FbAssignment  # noqa: E402
from module_feedback.entity.vo import PublicationConfigSaveModel, PublishRequestModel  # noqa: E402
from module_feedback.entity.vo.employee_vo import EmployeePageQueryModel  # noqa: E402
from module_feedback.entity.vo.progress_vo import ProgressQueryModel  # noqa: E402
from module_feedback.entity.vo.report_vo import ReportQueryModel  # noqa: E402
from module_feedback.service.answer_service import FeedbackAnswerService  # noqa: E402
from module_feedback.service.employee_service import FeedbackEmployeeService  # noqa: E402
from module_feedback.service.progress_service import FeedbackProgressService  # noqa: E402
from module_feedback.service.publication_service import FeedbackPublicationService  # noqa: E402
from module_feedback.service.report_service import FeedbackReportService  # noqa: E402
from scripts.feedback_p0_database_precheck import build_source_payload  # noqa: E402
from tests.module_feedback.service.p6_helpers import answer_request, cleanup_p6_project, create_p6_project  # noqa: E402
from tests.module_feedback.service.test_p7_completion_postgresql import complete_request  # noqa: E402


async def measure(engine: Any, factory: Any, action: Any) -> dict:
    timings, counts, captured = [], [], []

    def capture(_connection: Any, _cursor: Any, statement: str, parameters: Any, _context: Any, _many: bool) -> None:
        if statement.lstrip().upper().startswith(('SELECT', 'WITH')):
            captured.append((statement, parameters))

    for _ in range(4):
        captured.clear()
        event.listen(engine.sync_engine, 'before_cursor_execute', capture)
        try:
            async with factory() as db:
                started = time.perf_counter()
                result = await action(db)
                timings.append(round((time.perf_counter() - started) * 1000, 3))
                counts.append(len(captured))
        finally:
            event.remove(engine.sync_engine, 'before_cursor_execute', capture)
    unique = dict(captured)
    plans = []
    async with engine.connect() as connection:
        for statement, parameters in unique.items():
            plan = (
                await connection.exec_driver_sql('EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) ' + statement, parameters)
            ).scalar_one()
            plans.append({'sql': statement, 'plan': plan})
    return {
        'warmupMs': timings[0],
        'elapsedMs': timings[1:],
        'queryCounts': counts[1:],
        'rows': len(result.rows),
        'plans': plans,
    }


async def benchmark(database: str, target_count: int, output: Path) -> None:  # noqa: PLR0915
    if not re.fullmatch(r'ruoyi_feedback_p9_[a-z0-9_]+_test', database):
        raise RuntimeError('性能夹具只允许P9隔离测试库')
    source = DataSourceSettings(**build_source_payload(database))
    engine = create_async_db_engine(config=source)
    factory = create_async_session_factory(engine)
    state = None
    try:
        state = await create_p6_project(factory, publish=False)
        marker = uuid.uuid4().hex[:10]
        async with factory() as db:
            owner = await db.get(SysUser, state['user_ids'][0])
            users = [
                SysUser(
                    user_name=f'p9perf_{marker}_{i}',
                    nick_name=f'性能验收人员{i}',
                    dept_id=owner.dept_id,
                    status='0',
                    del_flag='0',
                )
                for i in range(target_count)
            ]
            db.add_all(users)
            await db.flush()
            added_ids = [user.user_id for user in users]
            state['user_ids'].extend(added_ids)
            await db.commit()
            targets = [state['user_ids'][0], state['user_ids'][2], *added_ids[2:]]
            evaluators = [state['user_ids'][1], *added_ids[:2]]
            config = await FeedbackPublicationService.get_config(db, state['project_id'], true())
            relation_keys = (
                'relationCode',
                'relationType',
                'relationName',
                'isEnabled',
                'participatesInScore',
                'weight',
                'sortOrder',
            )
            relations = [
                {
                    key: value
                    for key, value in relation.model_dump(by_alias=True, mode='json').items()
                    if key in relation_keys
                }
                for relation in config.relations
            ]
            saved = await FeedbackPublicationService.save_config(
                db,
                state['project_id'],
                PublicationConfigSaveModel(
                    projectLockVersion=config.project_lock_version,
                    versionId=config.version_id,
                    versionLockVersion=config.version_lock_version,
                    targets=[{'targetUserId': target} for target in targets],
                    relations=relations,
                    evaluatorSelections=[
                        {'targetUserId': target, 'relationCode': 'REL_PEER', 'evaluatorUserIds': evaluators}
                        for target in targets
                    ],
                ),
                'p9-perf',
                true(),
                true(),
            )
            await FeedbackPublicationService.publish(
                db,
                state['project_id'],
                PublishRequestModel(
                    projectLockVersion=saved.project_lock_version,
                    versionId=saved.version_id,
                    versionLockVersion=saved.version_lock_version,
                ),
                state['user_ids'][0],
                'p9-perf',
                true(),
                true(),
            )
            task_ids = list(
                await db.scalars(
                    select(FbAssignment.assignment_id).where(
                        FbAssignment.project_id == state['project_id'], FbAssignment.evaluator_user_id == evaluators[0]
                    )
                )
            )
            for index, task_id in enumerate(task_ids, start=1):
                detail = await FeedbackEmployeeService.get_task(db, task_id, evaluators[0])
                await FeedbackAnswerService.submit(db, task_id, evaluators[0], answer_request(detail, submit=True))
                if index % 50 == 0:
                    print(f'真实提交完成 {index}/{target_count}', flush=True)
        async with engine.begin() as connection:
            for table in ('fb_project', 'fb_assignment', 'fb_project_target', 'fb_answer_sheet', 'fb_answer'):
                await connection.exec_driver_sql(f'ANALYZE {table}')
        results = {
            'database': database,
            'targets': target_count,
            'assignments': target_count * 4,
            'submitted': target_count,
            'operations': {},
        }
        results['operations']['employeeTodos'] = await measure(
            engine,
            factory,
            lambda db: FeedbackEmployeeService.list_projects(db, evaluators[1], EmployeePageQueryModel()),
        )
        results['operations']['progress'] = await measure(
            engine,
            factory,
            lambda db: FeedbackProgressService.get_progress(
                db, state['project_id'], ProgressQueryModel(), true(), true()
            ),
        )
        async with factory() as db:
            precheck = await FeedbackProgressService.get_precheck(db, state['project_id'], true(), true())
            assert precheck.summary.total_count == target_count * 4 and precheck.summary.submitted_count == target_count
            await FeedbackProgressService.complete_project(
                db, state['project_id'], complete_request(precheck), state['user_ids'][0], 'p9-perf', true(), true()
            )
            started = time.perf_counter()
            await FeedbackReportService.calculate(db, state['project_id'], true(), true())
            results['generationMs'] = round((time.perf_counter() - started) * 1000, 3)
            report = await FeedbackReportService.team(db, state['project_id'], ReportQueryModel(), true(), true())
            assert report.total == target_count and report.completion_rate == '25.00'
            assert all(row.score == '45.55' for row in report.rows)
        async with engine.begin() as connection:
            await connection.exec_driver_sql('ANALYZE fb_score_result')
        results['operations']['reports'] = await measure(
            engine,
            factory,
            lambda db: FeedbackReportService.team(db, state['project_id'], ReportQueryModel(), true(), true()),
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(output.write_text, json.dumps(results, ensure_ascii=False, indent=2), encoding='utf-8')
        print(
            json.dumps(
                {
                    **results,
                    'operations': {
                        key: {field: value for field, value in result.items() if field != 'plans'}
                        for key, result in results['operations'].items()
                    },
                },
                ensure_ascii=False,
            ),
            flush=True,
        )
    finally:
        if state:
            await cleanup_p6_project(factory, state)
        await engine.dispose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database', required=True)
    parser.add_argument('--targets', type=int, default=200)
    parser.add_argument('--output', type=Path, default=BACKEND_DIR / '.tmp/p9/performance.json')
    arguments = parser.parse_args()
    if not MIN_TARGETS <= arguments.targets <= MAX_TARGETS:
        parser.error('被评价人数必须在2至1000之间')
    asyncio.run(benchmark(arguments.database, arguments.targets, arguments.output))
