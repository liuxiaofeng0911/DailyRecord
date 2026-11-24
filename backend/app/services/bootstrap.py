"""种子数据初始化：角色、默认组织、字典、全局开关、管理菜单。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ComUser, GeneralCode, Org, Resource, Role, RoleResource, Switch

DICT_SEEDS: dict[str, list[tuple[str, str]]] = {
    "MOOD": [
        ("开心", "开心"),
        ("平静", "平静"),
        ("疲惫", "疲惫"),
        ("低落", "低落"),
        ("兴奋", "兴奋"),
    ],
    "MEDIA_TYPE": [("IMAGE", "图片"), ("VIDEO", "视频")],
    "TAG_KIND": [("tag", "标签"), ("event", "事件"), ("type", "类型"), ("person", "人物")],
    "PERIOD_TYPE": [("week", "周"), ("month", "月"), ("year", "年")],
    "REGISTER_MODE": [("CLOSED", "关闭"), ("OPEN", "开放"), ("INVITE", "邀请码")],
    "LOGIN_RESULT": [("SUCCESS", "成功"), ("FAILED", "失败"), ("LOCKED", "锁定")],
    "AI_STATE": [
        ("disabled", "未启用"),
        ("pending", "待处理"),
        ("processing", "处理中"),
        ("done", "完成"),
        ("failed", "失败"),
        ("unsupported", "不支持"),
        ("manual", "人工"),
    ],
}

SWITCH_SEEDS: dict[str, tuple[str, str]] = {
    "DAILYRECORD_REGISTER_MODE": ("注册模式", "CLOSED"),
    "DAILYRECORD_AI_ENABLED": ("AI 总开关", "N"),
    "DAILYRECORD_BOOTSTRAP_DONE": ("初始化完成", "N"),
}

MENU_SEEDS = [
    ("今天", "Today", "/Main/Today", 1),
    ("时间线", "Timeline", "/Main/Timeline", 2),
    ("统计", "Stats", "/Main/Stats", 3),
    ("系统管理", "System", "/System/User", 4),
]


def ensure_seed_data(db: Session) -> None:
    if db.scalar(select(Role).where(Role.code == "OWNER")) is None:
        db.add(Role(code="OWNER", name="所有者", description="系统所有者"))
    if db.scalar(select(Role).where(Role.code == "MEMBER")) is None:
        db.add(Role(code="MEMBER", name="成员", description="普通成员"))

    if db.get(Org, 1) is None:
        db.add(Org(id=1, org_code="DEFAULT", org_name="默认组织", org_id=1))

    for codeid, items in DICT_SEEDS.items():
        existing = {
            row.code
            for row in db.scalars(select(GeneralCode).where(GeneralCode.codeid == codeid)).all()
        }
        for code, label in items:
            if code not in existing:
                db.add(GeneralCode(codeid=codeid, code=code, codename_c=label))

    for key, (name, default) in SWITCH_SEEDS.items():
        row = db.scalar(select(Switch).where(Switch.switch_key == key))
        if row is None:
            db.add(Switch(switch_key=key, switch_name=name, enabled=default))

    if db.scalar(select(Resource)) is None:
        owner = db.scalar(select(Role).where(Role.code == "OWNER"))
        for name, icon, url, sort in MENU_SEEDS:
            resource = Resource(name=name, icon_name=icon, web_url=url, sort=sort)
            db.add(resource)
            db.flush()
            if owner is not None:
                db.add(RoleResource(role_id=owner.id, resource_id=resource.id))
    db.commit()


def has_users(db: Session) -> bool:
    return db.scalar(select(ComUser.id).limit(1)) is not None
