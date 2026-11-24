"""运维命令行：重置密码、创建邀请码。

用法：
  python -m app.cli reset-password --userid me --password 'NewStrongPass123'
  python -m app.cli create-invite --days 7
"""

import argparse
import hashlib
import secrets
from datetime import timedelta

from sqlalchemy import func, select

from .db import SessionLocal
from .models import ComUser, InviteCode
from .security.password import hash_password, validate_password_strength
from .services.auth_service import revoke_all_sessions
from .services.timeutil import now_shanghai


def reset_password(userid: str, password: str) -> None:
    validate_password_strength(password)
    with SessionLocal() as db:
        user = db.scalars(
            select(ComUser).where(func.lower(ComUser.userid) == userid.lower())
        ).first()
        if user is None:
            raise SystemExit(f"用户不存在: {userid}")
        user.password = hash_password(password)
        user.password_algo = "argon2id"
        user.failed_login_attempts = 0
        user.locked_until = None
        revoke_all_sessions(db, user)
        db.commit()
        print(f"已重置 {user.userid} 的密码，并撤销全部会话")


def create_invite(created_by: int, days: int) -> str:
    code = secrets.token_urlsafe(12)
    with SessionLocal() as db:
        db.add(
            InviteCode(
                code_hash=hashlib.sha256(code.encode()).hexdigest(),
                created_by=created_by,
                expires_at=now_shanghai() + timedelta(days=days),
            )
        )
        db.commit()
    return code


def main() -> None:
    parser = argparse.ArgumentParser(description="DailyRecord 运维工具")
    sub = parser.add_subparsers(dest="command", required=True)

    pwd = sub.add_parser("reset-password", help="重置用户密码")
    pwd.add_argument("--userid", required=True)
    pwd.add_argument("--password", required=True)

    invite = sub.add_parser("create-invite", help="创建邀请码")
    invite.add_argument("--created-by", type=int, default=1)
    invite.add_argument("--days", type=int, default=7)

    args = parser.parse_args()
    if args.command == "reset-password":
        reset_password(args.userid, args.password)
    elif args.command == "create-invite":
        print(create_invite(args.created_by, args.days))


if __name__ == "__main__":
    main()
