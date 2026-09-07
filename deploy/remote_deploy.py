"""制作无密钥的版本包，通过 SSH 在独立目录发布；默认仅发布已提交 HEAD。"""

import argparse
import hashlib
import io
import json
import re
import subprocess
import tarfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[1]


def include_path(name):
    path = PurePosixPath(name)
    excluded = {
        ".git",
        "node_modules",
        ".venv",
        "__pycache__",
        ".tmp",
        "output",
        "backups",
        ".playwright-cli",
    }
    if excluded.intersection(path.parts) or path.is_absolute() or ".." in path.parts:
        return False
    if name.startswith("deploy/secrets/") or name == ".env.deploy":
        return False
    if name.startswith("ruoyi-fastapi-backend/.env"):
        return name == "ruoyi-fastapi-backend/.env.prod"
    if path.name.startswith(".env"):
        allowed = {".env.deploy.example"}
        for frontend in ("feedback-frontend", "ruoyi-fastapi-frontend"):
            allowed.update(
                f"{frontend}/.env.{mode}"
                for mode in ("development", "production", "staging", "docker")
            )
        return name in allowed
    return True


def validate_target(target):
    if not re.fullmatch(
        r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*@[a-zA-Z0-9][a-zA-Z0-9.-]*", target
    ):
        raise ValueError("SSH 目标必须是 user@hostname，不接受额外参数")


def run(args, **kwargs):
    return subprocess.run(args, cwd=ROOT, check=True, **kwargs)


def package(working_tree=False):
    head = run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True
    ).stdout.strip()
    files = {}
    if working_tree:
        names = run(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            capture_output=True,
        ).stdout
        for raw in names.split(b"\0"):
            if not raw:
                continue
            name = raw.decode("utf-8")
            path = ROOT / name
            if include_path(name) and path.is_file() and not path.is_symlink():
                files[name] = path.read_bytes()
    else:
        archive = run(
            ["git", "archive", "--format=tar", "HEAD"], capture_output=True
        ).stdout
        with tarfile.open(fileobj=io.BytesIO(archive)) as source:
            for item in source:
                if item.isfile() and include_path(item.name):
                    files[item.name] = source.extractfile(item).read()
    if "deploy/release.sh" not in files:
        raise ValueError("HEAD 尚未包含部署脚本；请先提交，或首次明确使用 -WorkingTree")
    for required in (
        "ruoyi-fastapi-frontend/package-lock.json",
        "feedback-frontend/package-lock.json",
    ):
        if required not in files:
            raise ValueError(f"发布包缺少 npm ci 所需锁文件：{required}")
    # 部署脚本在 Windows 工作区也必须保持 Linux 换行。
    for name, data in files.items():
        if name.startswith("deploy/") and name.endswith(".sh"):
            files[name] = data.replace(b"\r\n", b"\n")
    digest = hashlib.sha256()
    for name, data in sorted(files.items()):
        digest.update(name.encode() + b"\0" + hashlib.sha256(data).digest())
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    tag = f"{head[:12]}-{stamp}-{digest.hexdigest()[:10]}"
    manifest = {
        "release": tag,
        "commit": head,
        "working_tree": working_tree,
        "sha256": digest.hexdigest(),
        "files": len(files),
    }
    files["release-manifest.json"] = json.dumps(
        manifest, ensure_ascii=False, indent=2
    ).encode()
    target = ROOT / "output" / "deploy" / f"{tag}.tar.gz"
    target.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(target, "w:gz") as archive:
        for name, data in sorted(files.items()):
            item = tarfile.TarInfo(name)
            item.size = len(data)
            item.mode = 0o644
            archive.addfile(item, io.BytesIO(data))
    return tag, target


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--server", default="root@192.168.10.122")
    parser.add_argument("--working-tree", action="store_true")
    parser.add_argument("--package-only", action="store_true")
    args = parser.parse_args()
    validate_target(args.server)
    tag, archive = package(args.working_tree)
    print(
        f"发布版本：{tag}；工作区快照：{args.working_tree}；源码包：{archive}",
        flush=True,
    )
    if args.package_only:
        return
    ssh = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=15", args.server]
    run(
        [
            *ssh,
            "install -d -m 750 /opt/tongjian /opt/tongjian/incoming /opt/tongjian/releases",
        ]
    )
    run(
        [
            "scp",
            "-o",
            "BatchMode=yes",
            str(archive),
            f"{args.server}:/opt/tongjian/incoming/{tag}.tar.gz",
        ]
    )
    # tag 仅由提交号、UTC 时间和摘要组成，不包含用户输入。
    command = (
        f"set -eu; test ! -e /opt/tongjian/releases/{tag}; "
        f"mkdir /opt/tongjian/releases/{tag}; "
        f"tar -xzf /opt/tongjian/incoming/{tag}.tar.gz -C /opt/tongjian/releases/{tag}; "
        f"bash /opt/tongjian/releases/{tag}/deploy/release.sh"
    )
    run([*ssh, command])


if __name__ == "__main__":
    main()
