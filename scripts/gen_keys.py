"""生成 RSA-2048 密钥对（Base64 单行），用于写入 .env。"""

import base64

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def main() -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_pem = key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    print("RSA_PRIVATE_KEY=" + base64.b64encode(private_pem).decode())
    print("RSA_PUBLIC_KEY=" + base64.b64encode(public_pem).decode())


if __name__ == "__main__":
    main()
