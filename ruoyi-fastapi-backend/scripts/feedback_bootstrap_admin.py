"""仅全新部署使用：随机化管理员密码，停用系统基线演示账号。"""

import os
import secrets
from contextlib import closing
from pathlib import Path

import bcrypt

from config.env import DataBaseConfig
from scripts.feedback_p0_database_precheck import connect_database


def main() -> None:
    marker = Path('/bootstrap/bootstrap-complete')
    if marker.exists():
        print('首次初始化已完成，不重置管理员密码。')
        return
    target = Path('/bootstrap/initial-admin-password')
    if not target.exists():
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            stream.write(secrets.token_urlsafe(24))
    password = target.read_text(encoding='utf-8').strip()
    hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    with closing(connect_database(DataBaseConfig.default_source.db_database)) as connection:
        with connection.cursor() as cursor:
            cursor.execute('SELECT count(*) FROM sys_user')
            if cursor.fetchone()[0] != 2:  # noqa: PLR2004
                raise RuntimeError('只允许对全新系统基线初始化管理员')
            cursor.execute(
                "UPDATE sys_user SET password=%s, update_time=now() WHERE user_id=1 AND user_name='admin'", (hashed,)
            )
            if cursor.rowcount != 1:
                raise RuntimeError('系统管理员基线不匹配')
            cursor.execute("UPDATE sys_user SET status='1', update_time=now() WHERE user_id<>1")
        connection.commit()
    marker.touch(mode=0o600)
    print('管理员随机密码已初始化；演示账号已停用。凭据仅保存在服务器 shared/initial-admin-password。')


if __name__ == '__main__':
    main()
