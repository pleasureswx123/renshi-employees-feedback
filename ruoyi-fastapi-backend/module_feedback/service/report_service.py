from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException

from common.vo import PageModel
from module_feedback.calculators.report_score import CALCULATION_VERSION, calculate_report, display_decimal
from module_feedback.dao.progress_dao import FeedbackProgressDao
from module_feedback.dao.publication_dao import FeedbackPublicationDao
from module_feedback.dao.report_dao import FeedbackReportDao
from module_feedback.entity.do import FbScoreResult
from module_feedback.entity.vo.employee_vo import AnswerValueModel, EmployeeQuestionnaireModel
from module_feedback.entity.vo.report_vo import (
    PersonalReportModel,
    ReportCalculationModel,
    ReportProjectModel,
    ReportRowModel,
    SubmittedAnswerDetailModel,
    SubmittedAnswerRowModel,
    TeamReportModel,
)
from module_feedback.service.questionnaire_service import FeedbackQuestionnaireService
from module_feedback.service.scoring_input import build_scoring_inputs


class FeedbackReportService:
    @staticmethod
    def problem(status: int, code: str, message: str) -> HTTPException:
        return HTTPException(status_code=status, detail={'code': code, 'message': message})

    @classmethod
    async def context(
        cls,
        db: Any,
        project_id: int,
        project_scope: Any,
        target_scope: Any,
        *,
        calculating: bool = False,
        completed: bool = True,
    ) -> tuple:
        project = await FeedbackProgressDao.get_project_scoped(
            db,
            project_id,
            project_scope,
            for_update=calculating,
            for_share=not calculating,
        )
        if project is None or project.current_questionnaire_version_id is None:
            raise cls.problem(404, 'PROJECT_NOT_FOUND', '项目不存在')
        targets = await FeedbackReportDao.targets(
            db, project_id, project.current_questionnaire_version_id, target_scope
        )
        if not targets:
            raise cls.problem(404, 'PROJECT_NOT_FOUND', '项目不存在')
        if completed and project.status != 'COMPLETED':
            raise cls.problem(409, 'REPORT_PROJECT_NOT_COMPLETED', '项目完成后才能生成和查看报告')
        _, all_count = await FeedbackProgressDao.get_visible_target_ids(
            db,
            project_id,
            project.current_questionnaire_version_id,
            target_scope,
        )
        return project, targets, len(targets) == all_count

    @staticmethod
    async def list_projects(
        db: Any, query: Any, project_scope: Any, target_scope: Any
    ) -> PageModel[ReportProjectModel]:
        projects, total = await FeedbackReportDao.list_projects(db, query, project_scope, target_scope)
        return PageModel[ReportProjectModel](
            rows=[ReportProjectModel.model_validate(project) for project in projects],
            total=total,
            pageNum=query.page_num,
            pageSize=query.page_size,
            hasNext=query.page_num * query.page_size < total,
        )

    @staticmethod
    def _complete_keys(version: Any, keys: list) -> bool:
        expected = {('PERSON_TOTAL', None, None), ('COVERAGE', None, None)}
        for indicator in version.indicators:
            expected.add(('INDICATOR_COMPOSITE', indicator.indicator_id, None))
            expected.update(
                ('INDICATOR_RELATION', indicator.indicator_id, r.relation_id) for r in version.relations if r.is_enabled
            )
        return (
            len(keys) == len(expected)
            and {(row.result_type, row.indicator_id, row.relation_id) for row in keys} == expected
            and all(row.calculation_version == CALCULATION_VERSION for row in keys)
        )

    @classmethod
    async def calculate(cls, db: Any, project_id: int, project_scope: Any, target_scope: Any) -> ReportCalculationModel:
        try:
            project, targets, scope_complete = await cls.context(
                db,
                project_id,
                project_scope,
                target_scope,
                calculating=True,
            )
            version_id = project.current_questionnaire_version_id
            if not await FeedbackReportDao.scoring_precision_ready(db):
                raise cls.problem(409, 'REPORT_SCHEMA_NOT_READY', '报告暂不可用，请联系管理员完成数据库升级')
            version = await FeedbackPublicationDao.get_version_document(db, project_id, version_id)
            if version is None or version.status != 'FROZEN':
                raise cls.problem(409, 'REPORT_INPUT_INVALID', '冻结问卷不可用')
            keys = await FeedbackReportDao.result_keys(db, project_id, version_id, {t.target_id for t in targets})
            missing = []
            for target in targets:
                target_keys = [key for key in keys if key.target_id == target.target_id]
                if not target_keys:
                    missing.append(target)
                elif not cls._complete_keys(version, target_keys):
                    raise cls.problem(409, 'REPORT_RESULT_INCONSISTENT', '已有报告结果不完整，请联系管理员核查')
            if missing:
                ids = {t.target_id for t in missing}
                tasks = await FeedbackReportDao.tasks(db, project_id, version_id, ids)
                sheets, answers = await FeedbackReportDao.submitted_inputs(db, project_id, version_id, ids)
                try:
                    inputs = build_scoring_inputs(version, missing, tasks, sheets, answers)
                    now = datetime.now()
                    for target in missing:
                        rows, _ = calculate_report(inputs[target.target_id])
                        await FeedbackReportDao.add_results(
                            db,
                            [
                                FbScoreResult(
                                    project_id=project_id,
                                    version_id=version_id,
                                    target_id=target.target_id,
                                    target_user_id=target.target_user_id,
                                    calculation_version=CALCULATION_VERSION,
                                    calculated_time=now,
                                    **row,
                                )
                                for row in rows
                            ],
                        )
                except (ValueError, KeyError, StopIteration, ArithmeticError) as exc:
                    raise cls.problem(
                        409, 'REPORT_INPUT_INVALID', '冻结配置或已提交答案不一致，请联系管理员核查'
                    ) from exc
            result = ReportCalculationModel(
                projectId=project_id,
                calculatedCount=len(missing),
                existingCount=len(targets) - len(missing),
                dataScopeComplete=scope_complete,
            )
            await db.commit()
            return result
        except HTTPException:
            await db.rollback()
            raise
        except Exception as exc:
            await db.rollback()
            raise cls.problem(500, 'REPORT_CALCULATION_FAILED', '报告生成失败，请重试；已有正式结果不会被覆盖') from exc

    @classmethod
    async def team(cls, db: Any, project_id: int, query: Any, project_scope: Any, target_scope: Any) -> TeamReportModel:
        project, targets, scope_complete = await cls.context(db, project_id, project_scope, target_scope)
        version_id = project.current_questionnaire_version_id
        ids = {target.target_id for target in targets}
        version = await FeedbackPublicationDao.get_version_document(db, project_id, version_id)
        keys = await FeedbackReportDao.result_keys(db, project_id, version_id, ids)
        ready = all(
            cls._complete_keys(version, [key for key in keys if key.target_id == target.target_id])
            for target in targets
        )
        tasks = await FeedbackReportDao.tasks(db, project_id, version_id, ids)
        submitted = sum(task.status == 'SUBMITTED' for task in tasks)
        rows, total = await FeedbackReportDao.team_rows(db, project_id, version_id, ids, query) if ready else ([], 0)
        return TeamReportModel(
            projectId=project_id,
            projectName=project.project_name,
            versionId=version_id,
            ready=ready,
            dataScopeComplete=scope_complete,
            scopeMessage=None if scope_complete else '当前数据范围仅覆盖部分被评价人，排名和统计仅限可见范围',
            targetCount=len(targets),
            expectedCount=len(tasks),
            submittedCount=submitted,
            completionRate=display_decimal(Decimal(submitted) / len(tasks) * 100) if tasks else '0.00',
            rows=[
                ReportRowModel.model_validate(
                    {
                        **row['report'],
                        'targetName': row['target_user_name'],
                        'targetDeptName': row['target_dept_name'],
                        'rank': row['rank'] if row['score'] is not None else None,
                    }
                )
                for row in rows
            ],
            total=total,
            pageNum=query.page_num,
            pageSize=query.page_size,
        )

    @classmethod
    async def person(
        cls, db: Any, project_id: int, target_user_id: int, project_scope: Any, target_scope: Any
    ) -> PersonalReportModel:
        project, targets, _ = await cls.context(db, project_id, project_scope, target_scope)
        target = next((t for t in targets if t.target_user_id == target_user_id), None)
        if target is None:
            raise cls.problem(404, 'REPORT_TARGET_NOT_FOUND', '被评价人不存在')
        result = await FeedbackReportDao.personal_result(
            db, project_id, project.current_questionnaire_version_id, target.target_id
        )
        version = await FeedbackPublicationDao.get_version_document(
            db, project_id, project.current_questionnaire_version_id
        )
        keys = await FeedbackReportDao.result_keys(db, project_id, version.version_id, {target.target_id})
        if result is None or not cls._complete_keys(version, keys):
            raise cls.problem(409, 'REPORT_NOT_READY', '请先生成完整报告')
        return PersonalReportModel.model_validate(
            {
                **result.calculation_basis['report'],
                'targetName': target.target_user_name,
                'targetDeptName': target.target_dept_name,
                'projectId': project_id,
                'projectName': project.project_name,
                'versionId': result.version_id,
                'calculationVersion': result.calculation_version,
                'calculatedTime': result.calculated_time,
            }
        )

    @staticmethod
    def _answer_row(task: Any) -> SubmittedAnswerRowModel:
        return SubmittedAnswerRowModel(
            assignmentId=task.assignment_id,
            targetUserId=task.target_user_id,
            targetName=task.target_snapshot.target_user_name,
            targetDeptName=task.target_snapshot.target_dept_name,
            evaluatorName=task.evaluator_user_name,
            evaluatorDeptName=task.evaluator_dept_name,
            relationName=task.relation.relation_name,
            submittedTime=task.submitted_time,
        )

    @classmethod
    async def answers(
        cls, db: Any, project_id: int, query: Any, project_scope: Any, target_scope: Any
    ) -> PageModel[SubmittedAnswerRowModel]:
        project, targets, _ = await cls.context(db, project_id, project_scope, target_scope, completed=False)
        if query.target_user_id and query.target_user_id not in {t.target_user_id for t in targets}:
            raise cls.problem(404, 'REPORT_TARGET_NOT_FOUND', '被评价人不存在')
        tasks, total = await FeedbackReportDao.submitted_tasks(
            db,
            project_id,
            project.current_questionnaire_version_id,
            {t.target_id for t in targets},
            query,
        )
        return PageModel[SubmittedAnswerRowModel](
            rows=[cls._answer_row(task) for task in tasks],
            total=total,
            pageNum=query.page_num,
            pageSize=query.page_size,
            hasNext=query.page_num * query.page_size < total,
        )

    @classmethod
    async def answer(
        cls, db: Any, project_id: int, assignment_id: int, project_scope: Any, target_scope: Any
    ) -> SubmittedAnswerDetailModel:
        project, targets, _ = await cls.context(db, project_id, project_scope, target_scope, completed=False)
        task = await FeedbackReportDao.submitted_task(
            db,
            project_id,
            project.current_questionnaire_version_id,
            {t.target_id for t in targets},
            assignment_id,
        )
        if task is None:
            raise cls.problem(404, 'SUBMITTED_ANSWER_NOT_FOUND', '已提交答卷不存在')
        version = await FeedbackPublicationDao.get_version_document(db, project_id, task.version_id)
        document = FeedbackQuestionnaireService._document_payload(version)
        return SubmittedAnswerDetailModel(
            **cls._answer_row(task).model_dump(),
            projectId=project_id,
            projectName=project.project_name,
            questionnaire=EmployeeQuestionnaireModel(
                **{key: document[key] for key in ('versionId', 'title', 'description', 'descriptionDoc', 'pages')}
            ),
            answers=[AnswerValueModel.model_validate(answer) for answer in task.answer_sheet.answers],
        )
