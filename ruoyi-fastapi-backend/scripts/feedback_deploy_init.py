"""生成独立的部署密钥文件；拒绝覆盖已有目录，禁止隐式轮换生产密钥。"""

import argparse
import os
import secrets
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def initialize(directory: Path) -> None:
    private = rsa.generate_private_key(public_exponent=65537, key_size=4096)
    files = {
        'db_password': secrets.token_hex(32).encode(),
        'redis_password': secrets.token_hex(32).encode(),
        'jwt_secret': secrets.token_hex(48).encode(),
        'transport_private_key.pem': private.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        ),
        'transport_public_key.pem': private.public_key().public_bytes(
            serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
        ),
    }
    directory.mkdir(mode=0o700, parents=True, exist_ok=False)
    for name, content in files.items():
        descriptor = os.open(directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, 'wb') as stream:
            stream.write(content)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, default=Path(__file__).resolve().parents[2] / 'deploy/secrets')
    args = parser.parse_args()
    initialize(args.directory.resolve())
    print('部署密钥文件已生成，请安全保存；不需要打印或提交密钥内容。')
