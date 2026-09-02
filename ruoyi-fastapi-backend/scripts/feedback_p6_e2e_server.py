"""只在隔离PostgreSQL测试库和Redis 3启动P6真实端到端后端。"""

import subprocess
import sys

from feedback_p0_database_precheck import build_command_env

if __name__ == '__main__':
    environment = build_command_env('ruoyi_feedback_test')
    environment.update(REDIS_DATABASE='3', APP_PORT='9097', APP_HOST='127.0.0.1')
    raise SystemExit(
        subprocess.call(
            [
                sys.executable,
                '-m',
                'uvicorn',
                'server:create_app',
                '--factory',
                '--host',
                '127.0.0.1',
                '--port',
                '9097',
            ],
            env=environment,
        )
    )
