"""验证P2/P4/P5评价业务PostgreSQL结构和可逆迁移链。"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from contextlib import closing
from decimal import Decimal
from pathlib import Path
from typing import Any

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, Numeric, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import JSONB

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from config.database import Base  # noqa: E402
from module_feedback import entity as _feedback_entity  # noqa: E402, F401
from module_feedback.entity import do as _feedback_do  # noqa: E402, F401
from scripts.feedback_p0_database_precheck import (  # noqa: E402
    connect_database,
    get_current_revision,
    get_repository_head,
    run_alembic,
)

BASELINE_REVISION = '20260902_01_feedback_baseline'
DOMAIN_REVISION = '20260902_02_feedback_domain'
DESIGNER_REVISION = '20260902_03_feedback_designer'
PUBLICATION_REVISION = '20260902_04_feedback_publication'
FIXED_RELATION_COUNT = 5
EXPECTED_TABLES = {
    'fb_project',
    'fb_project_completion_audit',
    'fb_questionnaire_version',
    'fb_questionnaire_page',
    'fb_question',
    'fb_question_option',
    'fb_indicator',
    'fb_indicator_question',
    'fb_relation',
    'fb_project_target',
    'fb_evaluator_selection',
    'fb_assignment',
    'fb_answer_sheet',
    'fb_answer',
    'fb_score_result',
}
NUMERIC_12_4_COLUMNS = {
    ('fb_question', 'min_score'),
    ('fb_question', 'max_score'),
    ('fb_question_option', 'score'),
    ('fb_indicator', 'weight'),
    ('fb_relation', 'weight'),
    ('fb_answer', 'numeric_value'),
    ('fb_answer', 'raw_score'),
    ('fb_score_result', 'score'),
    ('fb_score_result', 'original_weight'),
    ('fb_score_result', 'effective_weight'),
}
REQUIRED_CONSTRAINTS = {
    'uq_fb_assignment_business_key',
    'uq_fb_evaluator_selection_business_key',
    'uq_fb_answer_sheet_question',
    'uq_fb_questionnaire_page_version_sort',
    'uq_fb_questionnaire_page_version_code',
    'uq_fb_question_page_sort',
    'ck_fb_question_score_range',
    'ck_fb_indicator_weight',
    'ck_fb_relation_weight',
    'ck_fb_assignment_status',
    'ck_fb_answer_value_channel',
    'ck_fb_score_result_dimensions',
    'ck_fb_project_completion_audit_result',
    'ck_fb_project_completion_audit_counts_nonnegative',
    'ck_fb_project_completion_audit_summary_identity',
    'ck_fb_project_completion_audit_closed_count',
}
DESIGNER_COLUMNS = {
    ('fb_questionnaire_version', 'description_doc'),
    ('fb_questionnaire_page', 'page_code'),
}
PUBLICATION_COLUMNS = {
    ('fb_evaluator_selection', 'selection_id'),
    ('fb_evaluator_selection', 'project_id'),
    ('fb_evaluator_selection', 'version_id'),
    ('fb_evaluator_selection', 'target_id'),
    ('fb_evaluator_selection', 'target_user_id'),
    ('fb_evaluator_selection', 'relation_id'),
    ('fb_evaluator_selection', 'evaluator_user_id'),
    ('fb_evaluator_selection', 'create_by'),
    ('fb_evaluator_selection', 'create_time'),
    ('fb_evaluator_selection', 'update_by'),
    ('fb_evaluator_selection', 'update_time'),
    ('fb_evaluator_selection', 'remark'),
}
REQUIRED_INDEXES = {
    'ix_fb_project_status_create_time',
    'ix_fb_assignment_evaluator_status',
    'ix_fb_assignment_target_status',
    'ix_fb_assignment_project_status',
    'ix_fb_evaluator_selection_project_version',
    'ix_fb_evaluator_selection_evaluator_project',
    'ix_fb_answer_sheet_project_submitted',
    'ix_fb_score_result_project_target',
    'uq_fb_score_indicator_relation',
    'uq_fb_score_indicator_composite',
    'uq_fb_score_person_result',
    'uq_fb_project_completion_audit_success',
}
IMMUTABLE_TABLES = {'fb_answer_sheet', 'fb_answer', 'fb_score_result', 'fb_project_completion_audit'}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description='验证评价业务PostgreSQL结构')
    parser.add_argument('--database', default='ruoyi_feedback_test', help='只允许反馈开发库或测试库')
    cycle_group = parser.add_mutually_exclusive_group()
    cycle_group.add_argument('--migration-cycle', action='store_true', help='先降级到P0基线再重新升级到head')
    cycle_group.add_argument(
        '--designer-migration-cycle',
        action='store_true',
        help='用一条P3结构测试数据执行P4升级、降级和再升级',
    )
    cycle_group.add_argument(
        '--publication-migration-cycle',
        action='store_true',
        help='用一组P4项目、页面和目标数据执行P5升级、降级和再升级',
    )
    parser.add_argument('--yes', action='store_true', help='确认在空的反馈测试库执行迁移循环')
    return parser.parse_args()


def validate_database_name(database_name: str, *, cycle: bool) -> str:
    normalized = database_name.strip()
    allowed_suffixes = ('_dev', '_test')
    if not normalized.startswith('ruoyi_feedback_') or not normalized.endswith(allowed_suffixes):
        raise ValueError('只允许验证ruoyi_feedback_dev或ruoyi_feedback_test一类的隔离数据库')
    if cycle and not normalized.endswith('_test'):
        raise ValueError('迁移降级/升级循环只允许在_test后缀数据库执行')
    return normalized


def get_feedback_tables(database_name: str) -> set[str]:
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public' AND LEFT(table_name, 3) = 'fb_'
            """
        )
        return {str(row[0]) for row in cursor.fetchall()}


def ensure_feedback_tables_empty(database_name: str) -> None:
    tables = get_feedback_tables(database_name)
    if tables != EXPECTED_TABLES:
        raise RuntimeError(f'迁移循环前评价表集合不完整：{sorted(tables)}')
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        non_empty: list[str] = []
        for table_name in sorted(tables):
            cursor.execute(f'SELECT EXISTS (SELECT 1 FROM {table_name} LIMIT 1)')
            if bool(cursor.fetchone()[0]):
                non_empty.append(table_name)
        if non_empty:
            raise RuntimeError(f'目标测试库包含评价业务数据，拒绝执行迁移循环：{non_empty}')


def run_migration_cycle(database_name: str) -> dict[str, Any]:
    ensure_feedback_tables_empty(database_name)
    run_alembic(database_name, 'downgrade', BASELINE_REVISION)
    downgraded_tables = get_feedback_tables(database_name)
    upgrade_error: BaseException | None = None
    try:
        if downgraded_tables:
            raise RuntimeError(f'降级后仍存在评价业务表：{sorted(downgraded_tables)}')
    finally:
        try:
            run_alembic(database_name, 'upgrade', 'head')
        except BaseException as exc:  # 确保迁移恢复失败不会被原检查错误掩盖
            upgrade_error = exc
    if upgrade_error is not None:
        raise upgrade_error
    return {
        'database': database_name,
        'downgradeRevision': BASELINE_REVISION,
        'tablesAfterDowngrade': len(downgraded_tables),
        'upgradeRevision': get_current_revision(database_name),
    }


def insert_designer_migration_fixture(database_name: str, marker: str) -> tuple[int, int, int]:
    """在P3结构下插入最小问卷页面，用于验证P4确定性回填。"""
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT user_id FROM sys_user WHERE del_flag = '0' AND status = '0' ORDER BY user_id LIMIT 1")
        user_row = cursor.fetchone()
        if user_row is None:
            raise RuntimeError('迁移往返测试需要至少一个可用的系统用户')
        cursor.execute(
            """
            INSERT INTO fb_project(project_name, owner_user_id, create_by, update_by)
            VALUES (%s, %s, 'p4-migration-test', 'p4-migration-test')
            RETURNING project_id
            """,
            (marker, int(user_row[0])),
        )
        project_id = int(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO fb_questionnaire_version(
                project_id, version_no, title, create_by, update_by
            )
            VALUES (%s, 1, 'P4迁移往返问卷', 'p4-migration-test', 'p4-migration-test')
            RETURNING version_id
            """,
            (project_id,),
        )
        version_id = int(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO fb_questionnaire_page(
                version_id, page_title, sort_order, create_by, update_by
            )
            VALUES (%s, 'P3既有页面', 1, 'p4-migration-test', 'p4-migration-test')
            RETURNING page_id
            """,
            (version_id,),
        )
        page_id = int(cursor.fetchone()[0])
        connection.commit()
        return project_id, version_id, page_id


def read_designer_migration_fixture(database_name: str, page_id: int) -> tuple[str, Any]:
    """读取P4新增字段，确认页面标识和富文本默认值。"""
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT p.page_code, v.description_doc
            FROM fb_questionnaire_page p
            JOIN fb_questionnaire_version v ON v.version_id = p.version_id
            WHERE p.page_id = %s
            """,
            (page_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError('P4迁移后未找到测试页面')
        return str(row[0]), row[1]


def verify_designer_columns_absent_and_fixture_present(database_name: str, page_id: int) -> None:
    """确认降级回P3后只移除了P4增量字段，既有页面仍保留。"""
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT table_name, column_name
            FROM information_schema.columns
            WHERE table_schema = 'public'
              AND (table_name, column_name) IN (
                ('fb_questionnaire_version', 'description_doc'),
                ('fb_questionnaire_page', 'page_code')
              )
            """
        )
        if cursor.fetchall():
            raise RuntimeError('降级到P3后仍存在P4增量字段')
        cursor.execute('SELECT EXISTS (SELECT 1 FROM fb_questionnaire_page WHERE page_id = %s)', (page_id,))
        if not bool(cursor.fetchone()[0]):
            raise RuntimeError('降级到P3时误删了既有问卷页面')


def cleanup_designer_migration_fixture(database_name: str, project_id: int) -> None:
    """清理由脚本创建的精确测试项目及级联问卷数据。"""
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute('DELETE FROM fb_questionnaire_version WHERE project_id = %s', (project_id,))
        cursor.execute(
            """
            DELETE FROM fb_project
            WHERE project_id = %s AND create_by = 'p4-migration-test'
            """,
            (project_id,),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            raise RuntimeError('迁移测试项目清理目标不唯一，已回滚')
        connection.commit()


def run_designer_migration_cycle(database_name: str) -> dict[str, Any]:
    """在空测试库执行P3→P4→P3→P4的有数据迁移往返。"""
    ensure_feedback_tables_empty(database_name)
    current_head = get_repository_head()
    if get_current_revision(database_name) != current_head:
        raise RuntimeError(f'迁移往返必须从{current_head}开始')

    marker = f'P4迁移往返-{uuid.uuid4()}'
    project_id: int | None = None
    page_id: int | None = None
    first_page_code: str | None = None
    second_page_code: str | None = None
    try:
        run_alembic(database_name, 'downgrade', DESIGNER_REVISION)
        run_alembic(database_name, 'downgrade', DOMAIN_REVISION)
        project_id, _, page_id = insert_designer_migration_fixture(database_name, marker)
        run_alembic(database_name, 'upgrade', DESIGNER_REVISION)
        first_page_code, first_doc = read_designer_migration_fixture(database_name, page_id)
        if first_page_code != f'P_{page_id}' or first_doc is not None:
            raise RuntimeError('首次升级未按约定回填page_code或description_doc默认值')

        run_alembic(database_name, 'downgrade', DOMAIN_REVISION)
        verify_designer_columns_absent_and_fixture_present(database_name, page_id)
        run_alembic(database_name, 'upgrade', DESIGNER_REVISION)
        second_page_code, second_doc = read_designer_migration_fixture(database_name, page_id)
        if second_page_code != first_page_code or second_doc is not None:
            raise RuntimeError('再次升级未保持确定性的page_code回填结果')
    finally:
        if get_current_revision(database_name) != current_head:
            run_alembic(database_name, 'upgrade', current_head)
        if project_id is not None:
            cleanup_designer_migration_fixture(database_name, project_id)

    return {
        'database': database_name,
        'fromRevision': DOMAIN_REVISION,
        'toRevision': DESIGNER_REVISION,
        'firstPageCode': first_page_code,
        'secondPageCode': second_page_code,
        'restoredRevision': get_current_revision(database_name),
        'fixtureCleaned': True,
    }


def insert_publication_migration_fixture(database_name: str, marker: str) -> tuple[int, int, int, int]:
    """在P4结构下插入项目、页面和目标，用于验证P5固定关系与选择表。"""
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT user_id FROM sys_user WHERE del_flag = '0' AND status = '0' ORDER BY user_id LIMIT 1")
        user_row = cursor.fetchone()
        if user_row is None:
            raise RuntimeError('P5迁移往返测试需要至少一个可用的系统用户')
        user_id = int(user_row[0])
        cursor.execute(
            """
            INSERT INTO fb_project(project_name, owner_user_id, create_by, update_by)
            VALUES (%s, %s, 'p5-migration-test', 'p5-migration-test')
            RETURNING project_id
            """,
            (marker, user_id),
        )
        project_id = int(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO fb_questionnaire_version(
                project_id, version_no, title, create_by, update_by
            )
            VALUES (%s, 1, 'P5迁移往返问卷', 'p5-migration-test', 'p5-migration-test')
            RETURNING version_id
            """,
            (project_id,),
        )
        version_id = int(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO fb_questionnaire_page(
                version_id, page_code, page_title, sort_order, create_by, update_by
            )
            VALUES (%s, %s, 'P4既有页面', 1, 'p5-migration-test', 'p5-migration-test')
            """,
            (version_id, f'P_{uuid.uuid4().hex}'),
        )
        cursor.execute(
            """
            INSERT INTO fb_project_target(
                project_id, version_id, target_user_id, target_user_name,
                only_self_evaluation, create_by, update_by
            )
            VALUES (%s, %s, %s, 'P5迁移测试用户', true, 'p5-migration-test', 'p5-migration-test')
            RETURNING target_id
            """,
            (project_id, version_id, user_id),
        )
        target_id = int(cursor.fetchone()[0])
        connection.commit()
        return project_id, version_id, target_id, user_id


def read_publication_default_relations(database_name: str, version_id: int) -> list[tuple[Any, ...]]:
    """读取迁移为指定草稿建立的固定关系。"""
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT relation_code, relation_type, relation_name,
                   is_enabled, participates_in_score, weight, sort_order
            FROM fb_relation
            WHERE version_id = %s
            ORDER BY sort_order
            """,
            (version_id,),
        )
        return list(cursor.fetchall())


def assert_publication_default_relations(rows: list[tuple[Any, ...]]) -> list[str]:
    """断言五个固定关系及自评强制语义完整。"""
    expected = [
        ('REL_SUPERVISOR', 'SUPERVISOR', '上级', False, False, 1),
        ('REL_PEER', 'PEER', '同级', False, False, 2),
        ('REL_SUBORDINATE', 'SUBORDINATE', '下级', False, False, 3),
        ('REL_SELF', 'SELF', '自己', True, False, 4),
        ('REL_OTHER', 'OTHER', '其他', False, False, 5),
    ]
    normalized = [
        (
            str(code),
            str(relation_type),
            str(name),
            bool(enabled),
            bool(scores),
            Decimal(str(weight)),
            int(sort_order),
        )
        for code, relation_type, name, enabled, scores, weight, sort_order in rows
    ]
    expected_with_weight = [(*item[:5], Decimal('0.0000'), item[5]) for item in expected]
    if normalized != expected_with_weight:
        raise RuntimeError(f'P5固定关系回填结果不符合约定：{normalized}')
    return [item[0] for item in normalized]


def insert_publication_selection_fixture(
    database_name: str,
    project_id: int,
    version_id: int,
    target_id: int,
    user_id: int,
) -> int:
    """写入一条自评选择，验证P5复合外键和新表生命周期。"""
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO fb_evaluator_selection(
                project_id, version_id, target_id, target_user_id,
                relation_id, evaluator_user_id, create_by, update_by
            )
            SELECT %s, %s, %s, %s, relation_id, %s,
                   'p5-migration-test', 'p5-migration-test'
            FROM fb_relation
            WHERE project_id = %s AND version_id = %s AND relation_code = 'REL_SELF'
            RETURNING selection_id
            """,
            (project_id, version_id, target_id, user_id, user_id, project_id, version_id),
        )
        row = cursor.fetchone()
        if row is None:
            raise RuntimeError('P5迁移后没有可用于自评选择的REL_SELF关系')
        connection.commit()
        return int(row[0])


def verify_publication_downgrade(database_name: str, project_id: int, version_id: int, target_id: int) -> None:
    """确认降级只移除选择表，保留P4数据和已回填固定关系。"""
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT to_regclass('public.fb_evaluator_selection')")
        if cursor.fetchone()[0] is not None:
            raise RuntimeError('降级到P4后仍存在评价人选择配置表')
        cursor.execute(
            """
            SELECT EXISTS(
                SELECT 1
                FROM fb_project_target
                WHERE project_id = %s AND version_id = %s AND target_id = %s
            )
            """,
            (project_id, version_id, target_id),
        )
        if not bool(cursor.fetchone()[0]):
            raise RuntimeError('降级到P4时误删了既有项目目标数据')
        cursor.execute(
            'SELECT COUNT(*) FROM fb_relation WHERE project_id = %s AND version_id = %s', (project_id, version_id)
        )
        if int(cursor.fetchone()[0]) != FIXED_RELATION_COUNT:
            raise RuntimeError('降级到P4后固定关系数量发生变化')


def cleanup_publication_migration_fixture(database_name: str, project_id: int) -> None:
    """清理由脚本创建的精确P5迁移测试项目。"""
    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        cursor.execute('DELETE FROM fb_evaluator_selection WHERE project_id = %s', (project_id,))
        cursor.execute('DELETE FROM fb_project_target WHERE project_id = %s', (project_id,))
        cursor.execute('DELETE FROM fb_questionnaire_version WHERE project_id = %s', (project_id,))
        cursor.execute(
            """
            DELETE FROM fb_project
            WHERE project_id = %s AND create_by = 'p5-migration-test'
            """,
            (project_id,),
        )
        if cursor.rowcount != 1:
            connection.rollback()
            raise RuntimeError('P5迁移测试项目清理目标不唯一，已回滚')
        connection.commit()


def run_publication_migration_cycle(database_name: str) -> dict[str, Any]:
    """在空测试库执行P4→P5→P4→P5的有数据迁移往返。"""
    ensure_feedback_tables_empty(database_name)
    current_head = get_repository_head()
    if get_current_revision(database_name) != current_head:
        raise RuntimeError(f'迁移往返必须从{current_head}开始')

    marker = f'P5迁移往返-{uuid.uuid4()}'
    project_id: int | None = None
    version_id: int | None = None
    target_id: int | None = None
    first_relation_codes: list[str] = []
    second_relation_codes: list[str] = []
    selection_id: int | None = None
    try:
        run_alembic(database_name, 'downgrade', DESIGNER_REVISION)
        project_id, version_id, target_id, user_id = insert_publication_migration_fixture(database_name, marker)
        run_alembic(database_name, 'upgrade', PUBLICATION_REVISION)
        first_relation_codes = assert_publication_default_relations(
            read_publication_default_relations(database_name, version_id)
        )
        selection_id = insert_publication_selection_fixture(
            database_name,
            project_id,
            version_id,
            target_id,
            user_id,
        )

        run_alembic(database_name, 'downgrade', DESIGNER_REVISION)
        verify_publication_downgrade(database_name, project_id, version_id, target_id)
        run_alembic(database_name, 'upgrade', PUBLICATION_REVISION)
        second_relation_codes = assert_publication_default_relations(
            read_publication_default_relations(database_name, version_id)
        )
        with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
            cursor.execute('SELECT COUNT(*) FROM fb_evaluator_selection WHERE project_id = %s', (project_id,))
            if int(cursor.fetchone()[0]) != 0:
                raise RuntimeError('P5再次升级后选择表不为空')
    finally:
        if get_current_revision(database_name) != current_head:
            run_alembic(database_name, 'upgrade', current_head)
        if project_id is not None:
            cleanup_publication_migration_fixture(database_name, project_id)

    return {
        'database': database_name,
        'fromRevision': DESIGNER_REVISION,
        'toRevision': PUBLICATION_REVISION,
        'firstRelationCodes': first_relation_codes,
        'secondRelationCodes': second_relation_codes,
        'selectionCreated': selection_id is not None,
        'selectionRemovedByDowngrade': True,
        'restoredRevision': get_current_revision(database_name),
        'fixtureCleaned': True,
    }


def model_type_signature(column_type: Any) -> tuple[str, int | None, int | None, int | None]:
    """把模型字段类型转换为information_schema可比较签名。"""
    if isinstance(column_type, JSONB):
        return ('jsonb', None, None, None)
    if isinstance(column_type, Numeric):
        return ('numeric', None, column_type.precision, column_type.scale)
    if isinstance(column_type, Text):
        return ('text', None, None, None)
    if isinstance(column_type, String):
        return ('character varying', column_type.length, None, None)
    if isinstance(column_type, BigInteger):
        return ('bigint', None, None, None)
    if isinstance(column_type, SmallInteger):
        return ('smallint', None, None, None)
    if isinstance(column_type, Integer):
        return ('integer', None, None, None)
    if isinstance(column_type, Boolean):
        return ('boolean', None, None, None)
    if isinstance(column_type, DateTime):
        return ('timestamp without time zone', None, None, None)
    raise TypeError(f'模型包含未纳入验证的字段类型：{column_type!r}')


def verify_model_column_contract(column_rows: list[tuple[Any, ...]]) -> int:
    """逐表验证数据库字段集合、类型和可空性与SQLAlchemy模型一致。"""
    database_columns = {
        (str(table), str(column)): (
            str(data_type),
            character_length if str(data_type) == 'character varying' else None,
            numeric_precision if str(data_type) == 'numeric' else None,
            numeric_scale if str(data_type) == 'numeric' else None,
            str(is_nullable) == 'YES',
        )
        for table, column, data_type, character_length, numeric_precision, numeric_scale, is_nullable in column_rows
    }
    model_columns: dict[tuple[str, str], tuple[str, int | None, int | None, int | None, bool]] = {}
    for table_name in EXPECTED_TABLES:
        table = Base.metadata.tables[table_name]
        for column in table.columns:
            model_columns[(table_name, column.name)] = (*model_type_signature(column.type), column.nullable)
    if set(database_columns) != set(model_columns):
        missing = sorted(set(model_columns) - set(database_columns))
        unexpected = sorted(set(database_columns) - set(model_columns))
        raise RuntimeError(f'模型与数据库字段集合不一致；缺少：{missing}；多出：{unexpected}')
    mismatches = {
        key: {'model': model_columns[key], 'database': database_columns[key]}
        for key in model_columns
        if model_columns[key] != database_columns[key]
    }
    if mismatches:
        raise RuntimeError(f'模型与数据库字段类型或可空性不一致：{mismatches}')
    return len(model_columns)


def verify_default_relation_contract(cursor: Any) -> int:
    """验证每个可编辑草稿具备固定关系，且自评强制语义未被破坏。"""
    cursor.execute(
        """
        SELECT v.project_id, v.version_id, r.relation_code, r.relation_type,
               r.is_enabled, r.participates_in_score, r.weight
        FROM fb_questionnaire_version v
        JOIN fb_project p ON p.project_id = v.project_id
        LEFT JOIN fb_relation r
          ON r.project_id = v.project_id AND r.version_id = v.version_id
        WHERE v.status = 'DRAFT'
          AND p.status = 'PREPARING'
          AND p.del_flag = '0'
        ORDER BY v.project_id, v.version_id, r.relation_id
        """
    )
    rows = list(cursor.fetchall())
    relations_by_version: dict[tuple[int, int], dict[str, tuple[Any, ...]]] = {}
    for project_id_value, version_id_value, code, relation_type, enabled, scores, weight in rows:
        version_key = (int(project_id_value), int(version_id_value))
        relations_by_version.setdefault(version_key, {})
        if code is not None:
            relations_by_version[version_key][str(code)] = (
                str(relation_type),
                bool(enabled),
                bool(scores),
                Decimal(str(weight)),
            )

    expected_types = {
        'REL_SUPERVISOR': 'SUPERVISOR',
        'REL_PEER': 'PEER',
        'REL_SUBORDINATE': 'SUBORDINATE',
        'REL_SELF': 'SELF',
        'REL_OTHER': 'OTHER',
    }
    for version_key, relations in relations_by_version.items():
        missing = sorted(set(expected_types) - set(relations))
        if missing:
            raise RuntimeError(f'可编辑草稿缺少固定关系：{version_key} -> {missing}')
        invalid_types = {
            code: {'actual': relations[code][0], 'expected': relation_type}
            for code, relation_type in expected_types.items()
            if relations[code][0] != relation_type
        }
        if invalid_types:
            raise RuntimeError(f'固定关系类型不一致：{version_key} -> {invalid_types}')
        _self_type, self_enabled, self_scores, self_weight = relations['REL_SELF']
        if not self_enabled or self_scores or self_weight != Decimal('0.0000'):
            raise RuntimeError(f'自己关系语义不一致：{version_key}')
    return len(relations_by_version)


def verify_schema(database_name: str) -> dict[str, Any]:  # noqa: PLR0912
    repository_head = get_repository_head()
    current_revision = get_current_revision(database_name)
    if current_revision != repository_head:
        raise RuntimeError(f'数据库revision不是仓库head：{current_revision} != {repository_head}')

    with closing(connect_database(database_name)) as connection, connection.cursor() as cursor:
        tables = get_feedback_tables(database_name)
        if tables != EXPECTED_TABLES:
            raise RuntimeError(f'评价业务表集合不一致：{sorted(tables)}')

        cursor.execute(
            """
            SELECT c.relname, obj_description(c.oid, 'pg_class')
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relname = ANY(%s)
            """,
            (list(EXPECTED_TABLES),),
        )
        table_comments = {str(name): comment for name, comment in cursor.fetchall()}
        missing_table_comments = sorted(name for name in EXPECTED_TABLES if not table_comments.get(name))
        if missing_table_comments:
            raise RuntimeError(f'表缺少中文注释：{missing_table_comments}')

        cursor.execute(
            """
            SELECT c.relname, a.attname, col_description(c.oid, a.attnum)
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_attribute a ON a.attrelid = c.oid
            WHERE n.nspname = 'public'
              AND c.relname = ANY(%s)
              AND a.attnum > 0
              AND NOT a.attisdropped
            """,
            (list(EXPECTED_TABLES),),
        )
        columns = {(str(table), str(column)): comment for table, column, comment in cursor.fetchall()}
        missing_column_comments = sorted(key for key, comment in columns.items() if not comment)
        if missing_column_comments:
            raise RuntimeError(f'字段缺少中文注释：{missing_column_comments}')

        cursor.execute(
            """
            SELECT table_name,
                   column_name,
                   data_type,
                   character_maximum_length,
                   numeric_precision,
                   numeric_scale,
                   is_nullable
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = ANY(%s)
            """,
            (list(EXPECTED_TABLES),),
        )
        column_rows = list(cursor.fetchall())
        column_types = {
            (str(table), str(column)): (str(data_type), precision, scale)
            for table, column, data_type, _length, precision, scale, _nullable in column_rows
        }
        missing_designer_columns = sorted(DESIGNER_COLUMNS - set(column_types))
        if missing_designer_columns:
            raise RuntimeError(f'缺少P4问卷设计器字段：{missing_designer_columns}')
        missing_publication_columns = sorted(PUBLICATION_COLUMNS - set(column_types))
        if missing_publication_columns:
            raise RuntimeError(f'缺少P5发布配置字段：{missing_publication_columns}')
        for key in NUMERIC_12_4_COLUMNS:
            if column_types.get(key) != ('numeric', 12, 4):
                raise RuntimeError(f'正式分数或权重字段不是NUMERIC(12,4)：{key} -> {column_types.get(key)}')
        if column_types.get(('fb_answer_sheet', 'raw_total_score')) != ('numeric', 18, 4):
            raise RuntimeError('答卷原始总分必须为NUMERIC(18,4)，以容纳合法多题总分')
        floating_columns = sorted(
            key for key, value in column_types.items() if value[0] in {'real', 'double precision'}
        )
        if floating_columns:
            raise RuntimeError(f'评价表存在二进制浮点字段：{floating_columns}')
        for table_name in IMMUTABLE_TABLES:
            if (table_name, 'del_flag') in column_types:
                raise RuntimeError(f'不可变提交数据表不得包含软删除字段：{table_name}')
        model_column_count = verify_model_column_contract(column_rows)

        cursor.execute(
            """
            SELECT con.conname
            FROM pg_constraint con
            JOIN pg_class rel ON rel.oid = con.conrelid
            JOIN pg_namespace n ON n.oid = rel.relnamespace
            WHERE n.nspname = 'public' AND rel.relname = ANY(%s)
            """,
            (list(EXPECTED_TABLES),),
        )
        constraints = {str(row[0]) for row in cursor.fetchall()}
        missing_constraints = sorted(REQUIRED_CONSTRAINTS - constraints)
        if missing_constraints:
            raise RuntimeError(f'缺少评价业务关键约束：{missing_constraints}')

        cursor.execute(
            """
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename = ANY(%s)
            """,
            (list(EXPECTED_TABLES),),
        )
        indexes = {str(row[0]) for row in cursor.fetchall()}
        missing_indexes = sorted(REQUIRED_INDEXES - indexes)
        if missing_indexes:
            raise RuntimeError(f'缺少评价业务关键索引：{missing_indexes}')
        draft_version_count = verify_default_relation_contract(cursor)

    return {
        'ok': True,
        'database': database_name,
        'revision': current_revision,
        'tableCount': len(EXPECTED_TABLES),
        'columnCommentCount': len(columns),
        'modelColumnContractCount': model_column_count,
        'numeric12Scale4Count': len(NUMERIC_12_4_COLUMNS),
        'numeric18Scale4Count': 1,
        'designerRevision': DESIGNER_REVISION,
        'designerColumnCount': len(DESIGNER_COLUMNS),
        'publicationRevision': PUBLICATION_REVISION,
        'publicationColumnCount': len(PUBLICATION_COLUMNS),
        'draftVersionDefaultRelationCount': draft_version_count,
        'requiredConstraintCount': len(REQUIRED_CONSTRAINTS),
        'requiredIndexCount': len(REQUIRED_INDEXES),
        'immutableTablesWithoutSoftDelete': sorted(IMMUTABLE_TABLES),
    }


def main() -> int:
    args = parse_args()
    cycle_requested = args.migration_cycle or args.designer_migration_cycle or args.publication_migration_cycle
    database_name = validate_database_name(args.database, cycle=cycle_requested)
    cycle_result = None
    if cycle_requested:
        if not args.yes:
            raise RuntimeError('执行迁移循环必须显式传入--yes')
        if args.migration_cycle:
            cycle_result = run_migration_cycle(database_name)
            cycle_key = 'migrationCycle'
        elif args.designer_migration_cycle:
            cycle_result = run_designer_migration_cycle(database_name)
            cycle_key = 'designerMigrationCycle'
        else:
            cycle_result = run_publication_migration_cycle(database_name)
            cycle_key = 'publicationMigrationCycle'
    payload = verify_schema(database_name)
    if cycle_result is not None:
        payload[cycle_key] = cycle_result
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
