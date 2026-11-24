from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..common.snowflake import next_id
from ..db import Base
from ..services.timeutil import now_shanghai


class ComUser(Base):
    """用户主档 com_userlist，沿用 BigTrans 字段并做设计文档 10.2 扩展。"""

    __tablename__ = "com_userlist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    userid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    username: Mapped[str | None] = mapped_column(String(64), nullable=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    password_algo: Mapped[str] = mapped_column(String(16), nullable=False, default="argon2id")
    user_active: Mapped[str] = mapped_column(String(1), nullable=False, default="Y")
    user_type: Mapped[str] = mapped_column(String(1), nullable=False, default="1")
    login_time: Mapped[str | None] = mapped_column(String(19), nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    token_version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Asia/Shanghai")
    mobile: Mapped[str | None] = mapped_column(String(30), nullable=True)
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    insert_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    update_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    org_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)


class Role(Base):
    __tablename__ = "t_um_role"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    code: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(32), nullable=False)
    enable: Mapped[str] = mapped_column(String(1), nullable=False, default="Y")
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    insert_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    update_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    org_id: Mapped[int] = mapped_column(BigInteger, default=1)


class UserRole(Base):
    __tablename__ = "t_um_user_role"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    insert_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    update_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    org_id: Mapped[int] = mapped_column(BigInteger, default=1)


class Org(Base):
    __tablename__ = "t_um_org"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    org_code: Mapped[str] = mapped_column(String(50), nullable=False, default="DEFAULT")
    org_name: Mapped[str] = mapped_column(String(50), nullable=False, default="默认组织")
    status: Mapped[str] = mapped_column(String(1), nullable=False, default="Y")
    pid: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    remark: Mapped[str | None] = mapped_column(String(200), nullable=True)
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    insert_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    update_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    org_id: Mapped[int] = mapped_column(BigInteger, default=1)


class UserOrg(Base):
    __tablename__ = "t_um_user_org"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    user_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    company_id: Mapped[str] = mapped_column(String(64), nullable=False, default="1")
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    insert_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    update_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    org_id: Mapped[int] = mapped_column(BigInteger, default=1)


class Resource(Base):
    __tablename__ = "t_um_resource"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    name: Mapped[str] = mapped_column(String(52), nullable=False)
    pid: Mapped[int] = mapped_column(BigInteger, nullable=False, default=0)
    sort: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    enable: Mapped[str] = mapped_column(String(1), nullable=False, default="Y")
    icon_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    web_url: Mapped[str | None] = mapped_column(String(255), nullable=True)
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    org_id: Mapped[int] = mapped_column(BigInteger, default=1)


class RoleResource(Base):
    __tablename__ = "t_um_role_resource"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    role_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    resource_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    org_id: Mapped[int] = mapped_column(BigInteger, default=1)


class GeneralCode(Base):
    __tablename__ = "cod_general_codes"
    __table_args__ = (UniqueConstraint("codeid", "code", name="uq_cod_general_codes_codeid_code"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    codeid: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(64), nullable=False)
    codename_c: Mapped[str] = mapped_column(String(300), nullable=False, default="")
    codename_e: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    filler1: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    filler2: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    insert_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    update_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    org_id: Mapped[int] = mapped_column(BigInteger, default=1)


class Switch(Base):
    __tablename__ = "t_switch"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, default=next_id)
    switch_key: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    switch_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    # BigTrans 原表为 varchar(4)，本项目注册模式需要存 CLOSED/OPEN/INVITE，故扩展为 varchar(16)
    enabled: Mapped[str] = mapped_column(String(16), nullable=False, default="0")
    insert_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai)
    update_time: Mapped[datetime] = mapped_column(DateTime, default=now_shanghai, onupdate=now_shanghai)
    insert_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    update_user: Mapped[str | None] = mapped_column(String(10), nullable=True)
    version: Mapped[int] = mapped_column(BigInteger, default=0)
    org_id: Mapped[int] = mapped_column(BigInteger, nullable=False, default=1)
