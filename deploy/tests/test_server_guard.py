"""保护其他项目：正常容器被替换或重启时必须让发布失败。"""

import importlib.util
import io
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "server_guard", Path(__file__).parents[1] / "server_guard.py"
)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


@pytest.mark.parametrize("enabled", [True, False])
def test_http_health_requires_disabled_crypto(monkeypatch, enabled):
    def response(url, **kwargs):
        payload = {
            "code": 200,
            "data": {
                "transportCryptoEnabled": enabled,
                "transportCryptoMode": "optional" if enabled else "off",
            },
        }
        stream = io.BytesIO(json.dumps(payload).encode())
        stream.status = 200
        return stream

    monkeypatch.setattr(guard, "urlopen", response)
    monkeypatch.setattr(guard.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(
        guard.sys, "argv", ["guard", "health", "192.168.10.122", "12681"]
    )
    if enabled:
        with pytest.raises(ValueError, match="HTTP"):
            guard.main()
    else:
        guard.main()


@pytest.mark.parametrize("change", ["id", "started", "status", "health"])
def test_rejects_changed_existing_service(monkeypatch, tmp_path, change):
    old = {
        "id": "old",
        "started": "yesterday",
        "status": "running",
        "health": "healthy",
    }
    before = tmp_path / "before.json"
    before.write_text(json.dumps({"/existing": old}))
    new = {**old, change: "changed"}
    monkeypatch.setattr(guard, "inventory", lambda: {"/existing": new})
    monkeypatch.setattr(guard.sys, "argv", ["guard", "compare", str(before)])
    with pytest.raises(RuntimeError, match="已有运行容器发生变化"):
        guard.main()


def test_preserves_preexisting_failure_boundary(monkeypatch, tmp_path):
    before = tmp_path / "before.json"
    before.write_text(json.dumps({"/preexisting-failure": {"status": "restarting"}}))
    monkeypatch.setattr(
        guard, "inventory", lambda: {"/preexisting-failure": {"status": "restarting"}}
    )
    monkeypatch.setattr(guard.sys, "argv", ["guard", "compare", str(before)])
    guard.main()


def test_capture_marks_already_restarting_container(monkeypatch, tmp_path):
    before = tmp_path / "before.json"
    samples = iter(
        [
            {"/unstable": {"id": "same", "status": "running", "started": "old"}},
            {"/unstable": {"id": "same", "status": "restarting", "started": "new"}},
        ]
    )
    monkeypatch.setattr(guard, "inventory", lambda: next(samples))
    monkeypatch.setattr(guard.time, "sleep", lambda seconds: None)
    monkeypatch.setattr(guard.sys, "argv", ["guard", "capture", str(before)])
    guard.main()
    assert json.loads(before.read_text())["/unstable"]["unstable"] is True
