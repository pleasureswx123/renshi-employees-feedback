"""验证P2/P4评价业务PostgreSQL结构和可逆迁移链。"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from contextlib import closing
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
EXPECTED_TABLES = {
    'fb_project',
    'fb_questionnaire_version',
    'fb_questionnaire_page',
    'fb_question',
    'fb_question_option',
    'fb_indicator',
    'fb_indicator_question',
    'fb_relation',
    'fb_project_target',
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
    ('fb_answer_sheet', 'raw_total_score'),
    ('fb_answer', 'numeric_value'),
    ('fb_answer', 'raw_score'),
    ('fb_score_result', 'score'),
    ('fb_score_result', 'original_weight'),
    ('fb_score_result', 'effective_weight'),
}
REQUIRED_CONSTRAINTS = {
    'uq_fb_assignment_business_key',
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
}
DESIGNER_COLUMNS = {
    ('fb_questionnaire_version', 'description_doc'),
    ('fb_questionnaire_page', 'page_code'),
}
REQUIRED_INDEXES = {
    'ix_fb_project_status_create_time',
    'ix_fb_assignment_evaluator_status',
    'ix_fb_assignment_target_status',
    'ix_fb_assignment_project_status',
    'ix_fb_answer_sheet_project_submitted',
    'ix_fb_score_result_project_target',
    'uq_fb_score_indicator_relation',
    'uq_fb_score_indicator_composite',
    'uq_fb_score_person_result',
}
IMMUTABLE_TABLES = {'fb_answer_sheet', 'fb_answer', 'fb_score_result'}


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
    if get_current_revision(database_name) != DESIGNER_REVISION:
        raise RuntimeError(f'迁移往返必须从{DESIGNER_REVISION}开始')

    marker = f'P4迁移往返-{uuid.uuid4()}'
    project_id: int | None = None
    page_id: int | None = None
    first_page_code: str | None = None
    second_page_code: str | None = None
    try:
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
        if get_current_revision(database_name) != DESIGNER_REVISION:
            run_alembic(database_name, 'upgrade', DESIGNER_REVISION)
        if project_id is not None:
            cleanup_designer_migration_fixture(database_name, project_id)

    return {
        'database': database_name,
        'fromRevision': DOMAIN_REVISION,
        'toRevision': DESIGNER_REVISION,
        'firstPageCode': first_page_code,
        'secondPageCode': second_page_code,
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


def verify_schema(database_name: str) -> dict[str, Any]:
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
        for key in NUMERIC_12_4_COLUMNS:
            if column_types.get(key) != ('numeric', 12, 4):
                raise RuntimeError(f'正式分数或权重字段不是NUMERIC(12,4)：{key} -> {column_types.get(key)}')
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
            raise RuntimeError(f'缺少P2关键索引：{missing_indexes}')

    return {
        'ok': True,
        'database': database_name,
        'revision': current_revision,
        'tableCount': len(EXPECTED_TABLES),
        'columnCommentCount': len(columns),
        'modelColumnContractCount': model_column_count,
        'numeric12Scale4Count': len(NUMERIC_12_4_COLUMNS),
        'designerRevision': DESIGNER_REVISION,
        'designerColumnCount': len(DESIGNER_COLUMNS),
        'requiredConstraintCount': len(REQUIRED_CONSTRAINTS),
        'requiredIndexCount': len(REQUIRED_INDEXES),
        'immutableTablesWithoutSoftDelete': sorted(IMMUTABLE_TABLES),
    }


def main() -> int:
    args = parse_args()
    cycle_requested = args.migration_cycle or args.designer_migration_cycle
    database_name = validate_database_name(args.database, cycle=cycle_requested)
    cycle_result = None
    if cycle_requested:
        if not args.yes:
            raise RuntimeError('执行迁移循环必须显式传入--yes')
        cycle_result = (
            run_migration_cycle(database_name) if args.migration_cycle else run_designer_migration_cycle(database_name)
        )
    payload = verify_schema(database_name)
    if cycle_result is not None:
        payload['designerMigrationCycle' if args.designer_migration_cycle else 'migrationCycle'] = cycle_result
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
