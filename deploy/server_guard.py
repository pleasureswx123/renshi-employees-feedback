"""发布前后只读核对其他容器、端口占用与本项目 HTTP 就绪状态。"""

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.request import urlopen


def inventory():
    ids = subprocess.check_output(["docker", "ps", "-aq"], text=True).split()
    if not ids:
        return {}
    containers = json.loads(
        subprocess.check_output(["docker", "inspect", *ids], text=True)
    )
    return {
        item["Name"]: {
            "id": item["Id"],
            "started": item["State"]["StartedAt"],
            "status": item["State"]["Status"],
            "health": item["State"].get("Health", {}).get("Status"),
        }
        for item in containers
        if item["Config"].get("Labels", {}).get("com.docker.compose.project")
        != "tongjian-prod"
    }


def main():
    action = sys.argv[1]
    if action == "capture":
        first = inventory()
        time.sleep(2)
        baseline = inventory()
        for name, state in baseline.items():
            if state["status"] == "restarting" or first.get(name) != state:
                state["unstable"] = True
                print(f"记录部署前已不稳定的容器：{name}")
        Path(sys.argv[2]).write_text(json.dumps(baseline, indent=2), encoding="utf-8")
    elif action == "compare":
        before = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
        after = inventory()
        failures = []
        for name, old in before.items():
            current = after.get(name)
            if current is None or current.get("id") != old.get("id"):
                failures.append(name)
            elif old.get("unstable"):
                print(f"保留部署前不稳定项：{name}，容器未替换")
            elif old["status"] == "running" and current != old:
                failures.append(name)
        if failures:
            raise RuntimeError(f"已有运行容器发生变化，需检查：{failures}")
        print(f"原有 {len(before)} 个容器基线核对通过；原有异常未计为本次健康证据。")
    elif action == "ports":
        project = sys.argv[2]
        for port in map(int, sys.argv[3:]):
            owners = subprocess.check_output(
                [
                    "docker",
                    "ps",
                    "--filter",
                    f"publish={port}",
                    "--format",
                    '{{.Label "com.docker.compose.project"}}',
                ],
                text=True,
            ).split()
            if owners:
                if any(owner != project for owner in owners):
                    raise RuntimeError(f"端口 {port} 已被其他项目占用")
            else:
                with socket.socket() as probe:
                    probe.bind(("192.168.10.122", port))
    elif action == "health":
        host = sys.argv[2]
        for port in sys.argv[3:]:
            for attempt in range(30):
                try:
                    for route in (
                        "/",
                        "/login",
                        "/prod-api/transport/crypto/frontend-config",
                    ):
                        with urlopen(
                            f"http://{host}:{port}{route}",
                            timeout=5,
                        ) as response:
                            data = response.read()
                            if response.status != 200:
                                raise ValueError("HTTP 未就绪")
                            if route.startswith("/prod-api/"):
                                payload = json.loads(data)
                                if payload.get("code") != 200:
                                    raise ValueError("API 未就绪")
                                policy = payload.get("data", {})
                                if (
                                    policy.get("transportCryptoEnabled") is not False
                                    or policy.get("transportCryptoMode") != "off"
                                ):
                                    raise ValueError(
                                        "HTTP 部署必须明确关闭应用层传输加密"
                                    )
                    break
                except Exception:
                    if attempt == 29:
                        raise
                    time.sleep(2)
            print(f"端口 {port} 页面、刷新路由、反向代理及加密配置 API 通过。")
    else:
        raise ValueError("未知检查动作")


if __name__ == "__main__":
    main()
