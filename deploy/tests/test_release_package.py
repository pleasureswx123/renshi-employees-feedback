"""发布包必须排除本地配置，且目标参数不能注入远程命令。"""

import importlib.util
import subprocess
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "remote_deploy", Path(__file__).parents[1] / "remote_deploy.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


@pytest.mark.parametrize(
    "path",
    [
        "ruoyi-fastapi-backend/.env.dev",
        "ruoyi-fastapi-backend/.env.dockerpg",
        "deploy/secrets/jwt_secret",
        ".env.deploy",
        "output/log.txt",
        "feedback-frontend/node_modules/foo.js",
        ".git/config",
        "backups/database.dump",
    ],
)
def test_excludes_private_files(path):
    assert not module.include_path(path)


@pytest.mark.parametrize(
    "path",
    [
        "docker-compose.pg.yml",
        "deploy/release.sh",
        "ruoyi-fastapi-backend/.env.prod",
        "feedback-frontend/.env.production",
        "ruoyi-fastapi-frontend/.env.docker",
        "ruoyi-fastapi-backend/module_feedback/service/project_service.py",
    ],
)
def test_includes_runtime_files(path):
    assert module.include_path(path)


@pytest.mark.parametrize(
    "target", ["root@host;reboot", "-oProxyCommand=sh", "host name"]
)
def test_rejects_invalid_ssh_target(target):
    with pytest.raises(ValueError):
        module.validate_target(target)


def test_accepts_server():
    module.validate_target("root@192.168.10.122")


def test_admin_lockfile_is_deliverable():
    result = subprocess.run(
        ["git", "check-ignore", "-q", "ruoyi-fastapi-frontend/package-lock.json"],
        cwd=Path(__file__).parents[2],
        check=False,
    )
    assert result.returncode == 1, "npm ci 依赖的锁文件不能被 Git 排除"


@pytest.mark.parametrize(
    "path",
    [
        ".env",
        "feedback-frontend/.env.local",
        "ruoyi-fastapi-frontend/.env.production.local",
    ],
)
def test_excludes_unrecognized_local_environment(path):
    assert not module.include_path(path)
