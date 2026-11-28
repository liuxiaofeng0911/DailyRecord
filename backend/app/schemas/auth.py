from pydantic import Field

from .common import CamelModel, DateTimeStr, StrId


class RegisterRequest(CamelModel):
    userid: str = Field(min_length=2, max_length=32)
    username: str = Field(min_length=1, max_length=64)
    email: str = Field(max_length=255)
    password: str
    confirm_password: str
    invite_code: str = ""


class LoginRequest(CamelModel):
    identifier: str = Field(min_length=1, max_length=255)
    password: str
    remember_me: bool = False


class ChangePasswordRequest(CamelModel):
    old_password: str
    new_password: str
    confirm_password: str


class SessionRevokeRequest(CamelModel):
    id: StrId


class UserInfo(CamelModel):
    id: StrId
    userid: str
    username: str
    email: str | None = None
    user_type: str = "1"
    role_code: str = "MEMBER"
    create_time: DateTimeStr | None = None
    ai_caption_enabled: bool = True


class LoginData(CamelModel):
    token: str
    user_info: UserInfo


class SessionOut(CamelModel):
    id: StrId
    user_agent: str | None = None
    ip: str | None = None
    created_at: DateTimeStr
    last_seen_at: DateTimeStr
    expires_at: DateTimeStr
    current: bool = False


class SiteSettings(CamelModel):
    upload_max_mb: int = 200
    trash_keep_days: int = 30
    ai_enabled: bool = False


class MeData(CamelModel):
    user_info: UserInfo
    switches: dict[str, str] = Field(default_factory=dict)
    menus: list[dict] = Field(default_factory=list)
    settings: SiteSettings = Field(default_factory=SiteSettings)


class AiCaptionRequest(CamelModel):
    enabled: bool
