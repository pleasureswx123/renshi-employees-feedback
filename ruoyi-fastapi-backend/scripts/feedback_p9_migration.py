"""评价数据库只读审计、备份恢复与严格校验后的Alembic接管。

已受Alembic管理的数据库使用正常upgrade。此工具仅处理早期create_all
形成的已知混合结构，未知差异一律拒绝；接管在一个事务内复用已有迁移。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from alembic.config import Config  # noqa: E402
from alembic.migration import MigrationContext  # noqa: E402
from alembic.operations import Operations  # noqa: E402
from alembic.script import ScriptDirectory  # noqa: E402
from sqlalchemy import URL, create_engine, text  # noqa: E402

from scripts.feedback_p0_database_precheck import (  # noqa: E402
    DataBaseConfig,
    build_source_payload,
    create_database,
    database_exists,
    get_public_objects,
)
from scripts.feedback_p2_schema_verify import EXPECTED_TABLES  # noqa: E402

P4 = '20260902_03_feedback_designer'
P5 = '20260902_04_feedback_publication'
P6 = '20260902_05_feedback_answering'
PERMISSIONS = '20260902_06_feedback_permissions'
P8 = '20260903_08_feedback_scoring'
P4_COLUMNS = {'fb_questionnaire_page.page_code', 'fb_questionnaire_version.description_doc'}
WIDEN_COLUMNS = {'fb_answer_sheet.raw_total_score', 'fb_score_result.score', 'fb_score_result.effective_weight'}
P4_UNIQUE = 'fb_questionnaire_page.uq_fb_questionnaire_page_version_code'


def database_engine(database: str) -> Any:
    source = build_source_payload(database)
    return create_engine(
        URL.create(
            'postgresql+psycopg2',
            username=source['db_username'],
            password=source['db_password'],
            host=source['db_host'],
            port=source['db_port'],
            database=database,
        ),
        echo=False,
    )


def canonical_default(value: str | None) -> str | None:
    if value in ('now()', 'CURRENT_TIMESTAMP'):
        return 'CURRENT_TIMESTAMP'
    if value and re.fullmatch(r"'0'::(?:smallint|integer|bigint|numeric)", value):
        return '0'
    return value


def canonical_expression(value: str) -> str:
    """pg_dump恢复会把常量数组的整体text转换展开为逐元素转换；只归一这一等价形式。"""
    literal = r"'(?:[^']|'')*'::character varying"
    pattern = rf'\(ARRAY\[({literal}(?:, {literal})*)\]\)::text\[\]'
    return re.sub(
        pattern, lambda match: 'ARRAY[' + re.sub(literal, lambda item: f'({item[0]})::text', match[1]) + ']', value
    )


def schema_snapshot(connection: Any) -> dict[str, Any]:
    columns = connection.execute(
        text(
            "SELECT table_name,column_name,data_type,is_nullable,column_default,numeric_precision,numeric_scale,character_maximum_length FROM information_schema.columns WHERE table_schema='public' AND left(table_name,3)='fb_' ORDER BY table_name,column_name"
        )
    ).all()
    constraints = connection.execute(
        text(
            "SELECT c.relname,con.conname,con.contype,pg_get_constraintdef(con.oid),con.convalidated FROM pg_constraint con JOIN pg_class c ON c.oid=con.conrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND left(c.relname,3)='fb_' ORDER BY 1,2"
        )
    ).all()
    indexes = connection.execute(
        text(
            "SELECT c.relname,i.relname,pg_get_indexdef(i.oid),x.indisvalid,x.indisready,x.indisprimary FROM pg_index x JOIN pg_class c ON c.oid=x.indrelid JOIN pg_class i ON i.oid=x.indexrelid JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND left(c.relname,3)='fb_' ORDER BY 1,2"
        )
    ).all()
    comments = connection.execute(
        text(
            "SELECT c.relname,COALESCE(a.attname,''),CASE WHEN a.attname IS NULL THEN obj_description(c.oid,'pg_class') ELSE col_description(c.oid,a.attnum) END FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace LEFT JOIN pg_attribute a ON a.attrelid=c.oid AND a.attnum>0 AND NOT a.attisdropped WHERE n.nspname='public' AND c.relkind='r' AND left(c.relname,3)='fb_' ORDER BY 1,2"
        )
    ).all()
    tables = connection.execute(
        text(
            "SELECT c.relname,obj_description(c.oid,'pg_class') FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname='public' AND c.relkind='r' AND left(c.relname,3)='fb_' ORDER BY 1"
        )
    ).all()
    revision = []
    if connection.scalar(text("SELECT to_regclass('public.alembic_version') IS NOT NULL")):
        revision = list(connection.scalars(text('SELECT version_num FROM alembic_version ORDER BY version_num')))
    return {
        'revision': revision,
        'tables': dict(tables),
        'columns': {f'{row[0]}.{row[1]}': [row[2], row[3], canonical_default(row[4]), *row[5:]] for row in columns},
        'constraints': {
            f'{table}.{name if kind != "p" else "PRIMARY_KEY"}': [kind, canonical_expression(definition), valid]
            for table, name, kind, definition, valid in constraints
        },
        'indexes': {
            f'{table}.{name}': [canonical_expression(definition), valid, ready]
            for table, name, definition, valid, ready, primary in indexes
            if not primary
        },
        'comments': {f'{table}.{column}': comment for table, column, comment in comments},
    }


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()
    ).hexdigest()


def compare_schema(source: dict, reference: dict) -> tuple[list[dict], list[dict]]:
    """只有既有迁移明确负责的差异可被接管，默认值等价和主键名称已规范化。"""
    accepted, rejected = [], []
    for category in ('tables', 'columns', 'constraints', 'indexes', 'comments'):
        for key in sorted(source[category].keys() | reference[category].keys()):
            actual, expected = source[category].get(key), reference[category].get(key)
            if actual == expected:
                continue
            known = False
            if category == 'columns' and key in P4_COLUMNS and actual is None:
                known = True
            elif category == 'columns' and key in WIDEN_COLUMNS and actual is not None and expected is not None:
                known = actual == [*expected[:3], 12, 4, expected[5]]
            elif (category in ('constraints', 'indexes') and key == P4_UNIQUE and actual is None) or (
                category == 'comments' and key in P4_COLUMNS and actual is None
            ):
                known = True
            entry = {'category': category, 'object': key, 'actual': actual, 'expected': expected}
            (accepted if known else rejected).append(entry)
    missing = {key for key in P4_COLUMNS if key not in source['columns']}
    if missing and missing != P4_COLUMNS:
        rejected.append({'category': 'columns', 'object': 'P4_PARTIAL_COLUMNS'})
    return accepted, rejected


def load_snapshot(database: str) -> dict:
    engine = database_engine(database)
    try:
        with engine.connect() as connection:
            return schema_snapshot(connection)
    finally:
        engine.dispose()


def audit(database: str, reference: str) -> dict:
    source, expected = load_snapshot(database), load_snapshot(reference)
    if expected['revision'] != [P8] or set(expected['tables']) != EXPECTED_TABLES:
        raise RuntimeError('参考库必须是已完整迁移的P8数据库')
    accepted, rejected = compare_schema(source, expected)
    return {
        'database': database,
        'reference': reference,
        'revision': source['revision'],
        'schemaSha256': digest(source),
        'knownDifferences': accepted,
        'unknownDifferences': rejected,
        'canAdopt': not source['revision'] and not rejected,
    }


def pg_command(binary: str, database: str, arguments: list[str], pg_bin: Path) -> None:
    source = build_source_payload(database)
    completed = subprocess.run(
        [
            str(pg_bin / f'{binary}{".exe" if os.name == "nt" else ""}'),
            '--host',
            source['db_host'],
            '--port',
            str(source['db_port']),
            '--username',
            source['db_username'],
            '--dbname',
            database,
            '--no-password',
            *arguments,
        ],
        env={**os.environ, 'PGPASSWORD': source['db_password']},
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        # 客户端错误可能包含连接信息，详细输出不进入工具结果或版本库。
        raise RuntimeError(f'{binary}失败，退出码{completed.returncode}；请检查客户端版本和目标库权限')


def backup(database: str, path: Path, pg_bin: Path) -> dict:
    if path.exists():
        raise RuntimeError('备份路径已存在，拒绝覆盖')
    path.parent.mkdir(parents=True, exist_ok=True)
    engine = database_engine(database)
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection, connection.begin():
            before = schema_snapshot(connection)
            fingerprints, _ = row_fingerprints(connection, before['columns'])
            snapshot_id = connection.scalar(text('SELECT pg_export_snapshot()'))
            pg_command(
                'pg_dump',
                database,
                ['--format=custom', '--no-owner', '--no-acl', '--snapshot', snapshot_id, '--file', str(path)],
                pg_bin,
            )
    finally:
        engine.dispose()
    result = {
        'database': database,
        'file': str(path),
        'backupSha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'schemaSha256': digest(before),
        'dataFingerprints': fingerprints,
    }
    path.with_suffix(path.suffix + '.json').write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    return result


def restore(database: str, path: Path, pg_bin: Path) -> dict:
    if (
        not re.fullmatch(r'ruoyi_feedback_p9_[a-z0-9_]+_test', database)
        or database == DataBaseConfig.default_source.db_database
    ):
        raise RuntimeError('恢复只允许新建的ruoyi_feedback_p9_*_test隔离库')
    if database_exists(database):
        raise RuntimeError('恢复目标库已存在，拒绝覆盖')
    metadata = json.loads(path.with_suffix(path.suffix + '.json').read_text(encoding='utf-8'))
    if metadata['backupSha256'] != hashlib.sha256(path.read_bytes()).hexdigest():
        raise RuntimeError('备份校验和不一致')
    create_database(database)
    if get_public_objects(database):
        raise RuntimeError('恢复目标库不是空库')
    pg_command(
        'pg_restore', database, ['--no-owner', '--no-acl', '--exit-on-error', '--single-transaction', str(path)], pg_bin
    )
    snapshot = load_snapshot(database)
    if digest(snapshot) != metadata['schemaSha256']:
        raise RuntimeError('恢复后结构与备份不一致')
    engine = database_engine(database)
    try:
        with engine.connect() as connection:
            restored_rows, _ = row_fingerprints(connection, snapshot['columns'])
            if restored_rows != metadata.get('dataFingerprints'):
                raise RuntimeError('恢复后的评价数据与备份摘要不一致')
    finally:
        engine.dispose()
    return {'database': database, 'restored': True, 'schemaSha256': digest(snapshot)}


def row_fingerprints(connection: Any, columns: dict, identities: dict | None = None) -> tuple[dict, dict]:
    """比较既有行的全部原字段；允许迁移增加字段或补充固定关系，但不允许改写既有值。"""
    quote = connection.dialect.identifier_preparer.quote
    signatures, row_ids = {}, {}
    for table in sorted(EXPECTED_TABLES):
        names = sorted(key.split('.', 1)[1] for key in columns if key.startswith(f'{table}.'))
        primary = connection.scalar(
            text(
                "SELECT a.attname FROM pg_constraint c JOIN pg_attribute a ON a.attrelid=c.conrelid AND a.attnum=ANY(c.conkey) WHERE c.conrelid=to_regclass(:table) AND c.contype='p'"
            ),
            {'table': f'public.{table}'},
        )
        if not primary:
            raise RuntimeError(f'表缺少主键：{table}')
        restriction = f' WHERE {quote(primary)} = ANY(:ids)' if identities is not None else ''
        result = connection.execute(
            text(
                f'SELECT {quote(primary)}, row_to_json(t)::text FROM (SELECT {", ".join(quote(name) for name in names)} FROM {quote(table)}{restriction}) t ORDER BY {quote(primary)}'
            ),
            {'ids': identities[table]} if identities is not None else {},
        )
        hasher, ids = hashlib.sha256(), []
        for identity, serialized in result:
            ids.append(identity)
            hasher.update(serialized.encode())
            hasher.update(b'\n')
        signatures[table] = {'count': len(ids), 'sha256': hasher.hexdigest()}
        row_ids[table] = ids
    return signatures, row_ids


def adopt(database: str, reference: str, expected_sha: str, backup_path: Path) -> dict:  # noqa: PLR0912
    if database != DataBaseConfig.default_source.db_database and not re.fullmatch(
        r'ruoyi_feedback_p9_[a-z0-9_]+_test', database
    ):
        raise RuntimeError('接管只允许当前配置库或本轮隔离演练库')
    reference_schema = load_snapshot(reference)
    if reference_schema['revision'] != [P8] or set(reference_schema['tables']) != EXPECTED_TABLES:
        raise RuntimeError('参考库不是已迁移的P8结构')
    metadata = json.loads(backup_path.with_suffix(backup_path.suffix + '.json').read_text(encoding='utf-8'))
    if database == DataBaseConfig.default_source.db_database and metadata['database'] != database:
        raise RuntimeError('当前配置库必须使用它自身的备份，不能使用其他数据库的备份')
    if (
        hashlib.sha256(backup_path.read_bytes()).hexdigest() != metadata['backupSha256']
        or expected_sha != metadata['schemaSha256']
    ):
        raise RuntimeError('备份摘要或预期结构不一致')
    scripts = ScriptDirectory.from_config(Config(str(BACKEND_DIR / 'alembic.ini')))
    engine = database_engine(database)
    try:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout='10s'"))
            connection.execute(text('LOCK TABLE ' + ', '.join(sorted(EXPECTED_TABLES)) + ' IN ACCESS EXCLUSIVE MODE'))
            before = schema_snapshot(connection)
            if before['revision'] or digest(before) != expected_sha:
                raise RuntimeError('目标已有迁移记录或结构变化，拒绝接管')
            _known, unknown = compare_schema(before, reference_schema)
            if unknown:
                raise RuntimeError('存在未识别结构差异，拒绝接管')
            fingerprints, identities = row_fingerprints(connection, before['columns'])
            if fingerprints != metadata.get('dataFingerprints'):
                raise RuntimeError('备份后评价数据已变化，请重新备份和演练')
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                if not P4_COLUMNS.intersection(before['columns']):
                    scripts.get_revision(P4).module.upgrade()
                if before['columns']['fb_answer_sheet.raw_total_score'][3:5] == [12, 4]:
                    scripts.get_revision(P6).module.upgrade()
                scripts.get_revision(P5).module._backfill_default_relations()
                scripts.get_revision(PERMISSIONS).module.upgrade()
                scripts.get_revision(P8).module.upgrade()
            after = schema_snapshot(connection)
            known, unknown = compare_schema(after, reference_schema)
            if known or unknown:
                raise RuntimeError('迁移后未达到参考结构，事务回滚')
            preserved, _ = row_fingerprints(connection, before['columns'], identities)
            if preserved != fingerprints:
                raise RuntimeError('既有行内容发生变化，事务回滚')
            # 只有结构、约束、索引和既有数据均已验证，才登记实际达到的版本。
            context.stamp(scripts, P8)
            if schema_snapshot(connection)['revision'] != [P8]:
                raise RuntimeError('迁移版本登记失败')
            result = {
                'database': database,
                'revision': P8,
                'preservedRows': fingerprints,
                'schemaSha256': digest(schema_snapshot(connection)),
                'backupSha256': metadata['backupSha256'],
            }
        return result
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['audit', 'backup', 'restore', 'adopt'])
    parser.add_argument('--database', required=True)
    parser.add_argument('--reference', default='ruoyi_feedback_dev')
    parser.add_argument('--file', type=Path)
    parser.add_argument('--pg-bin', type=Path, default=Path('C:/Program Files/PostgreSQL/17/bin'))
    parser.add_argument('--expected-schema-sha')
    parser.add_argument('--yes', action='store_true')
    args = parser.parse_args()
    if args.action != 'audit' and not args.yes:
        parser.error('写入或备份操作需要--yes')
    if args.action != 'audit' and args.file is None:
        parser.error('需要--file指定备份文件')
    if args.action == 'audit':
        result = audit(args.database, args.reference)
    elif args.action == 'backup':
        result = backup(args.database, args.file.resolve(), args.pg_bin)
    elif args.action == 'restore':
        result = restore(args.database, args.file.resolve(), args.pg_bin)
    else:
        result = adopt(args.database, args.reference, args.expected_schema_sha, args.file.resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
