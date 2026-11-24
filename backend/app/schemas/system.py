from pydantic import Field

from .common import CamelModel, DateTimeStr, OptDateTimeStr, StrId


class SystemUserOut(CamelModel):
    id: StrId
    userid: str
    username: str | None = None
    email: str | None = None
    user_active: str
    user_type: str
    role_code: str
    login_time: str | None = None
    insert_time: DateTimeStr | None = None
    locked_until: OptDateTimeStr = None


class UserSaveRequest(CamelModel):
    id: StrId | None = None
    userid: str = Field(min_length=3, max_length=32)
    username: str = Field(min_length=1, max_length=64)
    email: str = Field(max_length=255)
    password: str | None = None
    user_active: str = "Y"
    role_code: str = "MEMBER"


class UserIdRequest(CamelModel):
    id: StrId


class ResetPasswordRequest(CamelModel):
    id: StrId
    password: str


class RoleOut(CamelModel):
    id: StrId
    code: str
    name: str
    enable: str
    description: str | None = None


class RoleSaveRequest(CamelModel):
    id: StrId | None = None
    code: str = Field(min_length=1, max_length=32)
    name: str = Field(min_length=1, max_length=32)
    enable: str = "Y"
    description: str | None = None


class DictOut(CamelModel):
    id: StrId
    codeid: str
    code: str
    name: str
    remark: str | None = None


class DictSaveRequest(CamelModel):
    id: StrId | None = None
    codeid: str = Field(min_length=1, max_length=64)
    code: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=300)
    remark: str | None = None


class DictListRequest(CamelModel):
    codeid: str | None = None


class SwitchSaveRequest(CamelModel):
    key: str
    enabled: str


class OrgOut(CamelModel):
    id: StrId
    org_code: str
    org_name: str
    status: str
    pid: StrId | None = None
    remark: str | None = None


class OrgSaveRequest(CamelModel):
    id: StrId | None = None
    org_code: str = Field(min_length=1, max_length=50)
    org_name: str = Field(min_length=1, max_length=50)
    status: str = "Y"
    pid: StrId | None = "0"
    remark: str | None = None


class OrgIdRequest(CamelModel):
    id: StrId


class MenuSaveRequest(CamelModel):
    id: StrId | None = None
    name: str = Field(min_length=1, max_length=52)
    path: str = ""
    icon: str | None = None
    pid: StrId | None = "0"
    sort: int = 0
    enable: str = "Y"


class MenuIdRequest(CamelModel):
    id: StrId


class RoleMenusRequest(CamelModel):
    role_id: StrId


class RoleMenusSaveRequest(CamelModel):
    role_id: StrId
    menu_ids: list[StrId] = Field(default_factory=list)
