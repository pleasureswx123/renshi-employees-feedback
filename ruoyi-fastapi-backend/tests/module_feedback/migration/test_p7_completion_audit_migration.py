"""验证P7不可变完成审计迁移的受保护降级。"""

import importlib.util
from pathlib import Path
from types import ModuleType, SimpleNamespace

import pytest

MIGRATION_PATH = (
    Path(__file__).parents[3] / 'alembic' / 'versions' / '2026_09_02_1700-20260902_07_feedback_completion_audit.py'
)


def load_migration() -> ModuleType:
    spec = importlib.util.spec_from_file_location('feedback_completion_audit_migration', MIGRATION_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_nonempty_completion_audit_refuses_destructive_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = load_migration()
    dropped: list[str] = []
    bind = SimpleNamespace(
        execute=lambda statement: SimpleNamespace(scalar_one=lambda: 1),
    )
    monkeypatch.setattr(migration.op, 'get_bind', lambda: bind)
    monkeypatch.setattr(migration.op, 'drop_index', lambda *args, **kwargs: dropped.append('index'))
    monkeypatch.setattr(migration.op, 'drop_table', lambda *args, **kwargs: dropped.append('table'))

    with pytest.raises(RuntimeError, match='完成审计'):
        migration.downgrade()

    assert dropped == []


def test_empty_completion_audit_allows_downgrade(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = load_migration()
    dropped: list[str] = []
    bind = SimpleNamespace(
        execute=lambda statement: SimpleNamespace(scalar_one=lambda: 0),
    )
    monkeypatch.setattr(migration.op, 'get_bind', lambda: bind)
    monkeypatch.setattr(migration.op, 'drop_index', lambda *args, **kwargs: dropped.append('index'))
    monkeypatch.setattr(migration.op, 'drop_table', lambda *args, **kwargs: dropped.append('table'))

    migration.downgrade()

    assert dropped == ['index', 'table']


def test_downgrade_locks_completion_audit_before_counting(monkeypatch: pytest.MonkeyPatch) -> None:
    migration = load_migration()
    statements: list[str] = []

    def execute(statement: object) -> SimpleNamespace:
        statements.append(str(statement))
        return SimpleNamespace(scalar_one=lambda: 0)

    monkeypatch.setattr(migration.op, 'get_bind', lambda: SimpleNamespace(execute=execute))
    monkeypatch.setattr(migration.op, 'drop_index', lambda *args, **kwargs: None)
    monkeypatch.setattr(migration.op, 'drop_table', lambda *args, **kwargs: None)

    migration.downgrade()

    assert statements == [
        'LOCK TABLE fb_project_completion_audit IN ACCESS EXCLUSIVE MODE',
        'SELECT count(*) FROM fb_project_completion_audit',
    ]
