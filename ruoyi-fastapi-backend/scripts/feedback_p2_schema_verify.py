"""验证P2评价业务PostgreSQL结构和可逆迁移链。"""

from __future__ import annotations

import argparse
import json
import sys
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
    'uq_fb_question_page_sort',
    'ck_fb_question_score_range',
    'ck_fb_indicator_weight',
    'ck_fb_relation_weight',
    'ck_fb_assignment_status',
    'ck_fb_answer_value_channel',
    'ck_fb_score_result_dimensions',
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
    parser = argparse.ArgumentParser(description='验证P2评价业务PostgreSQL结构')
    parser.add_argument('--database', default='ruoyi_feedback_test', help='只允许反馈开发库或测试库')
    parser.add_argument('--migration-cycle', action='store_true', help='先降级到P0基线再重新升级到head')
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


def model_type_signature(column_type: Any) -> tuple[str, int | None, int | None, int | None]:
    """把P2模型字段类型转换为information_schema可比较签名。"""
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
    raise TypeError(f'P2模型包含未纳入验证的字段类型：{column_type!r}')


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
            raise RuntimeError(f'缺少P2关键约束：{missing_constraints}')

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
        'requiredConstraintCount': len(REQUIRED_CONSTRAINTS),
        'requiredIndexCount': len(REQUIRED_INDEXES),
        'immutableTablesWithoutSoftDelete': sorted(IMMUTABLE_TABLES),
    }


def main() -> int:
    args = parse_args()
    database_name = validate_database_name(args.database, cycle=args.migration_cycle)
    cycle_result = None
    if args.migration_cycle:
        if not args.yes:
            raise RuntimeError('执行迁移循环必须显式传入--yes')
        cycle_result = run_migration_cycle(database_name)
    payload = verify_schema(database_name)
    if cycle_result is not None:
        payload['migrationCycle'] = cycle_result
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
