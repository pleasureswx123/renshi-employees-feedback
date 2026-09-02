from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from config.database import Base
from utils.import_util import ImportUtil


def test_model_discovery_does_not_import_project_venv_or_temporary_scripts(monkeypatch: pytest.MonkeyPatch) -> None:
    root = Path(__file__).resolve().parent
    imported = []

    def walk(path: Path) -> Any:
        dirs = ['.venv', '.tmp', 'module_feedback']
        yield str(path), dirs, []
        for directory in dirs:
            yield str(path / directory), [], ['model.py']

    def import_module(name: str) -> Any:
        imported.append(name)
        return SimpleNamespace()

    monkeypatch.setattr(ImportUtil, 'find_project_root', lambda: root)
    monkeypatch.setattr('utils.import_util.os.walk', walk)
    monkeypatch.setattr('utils.import_util.importlib.import_module', import_module)
    ImportUtil.find_models.cache_clear()
    try:
        ImportUtil.find_models(Base)
        assert imported == ['module_feedback.model']
    finally:
        ImportUtil.find_models.cache_clear()
