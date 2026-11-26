"""种子数据初始化：角色、默认组织、字典、全局开关、管理菜单。"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import ComUser, GeneralCode, Org, Resource, Role, RoleResource, Switch, UserOrg

DICT_SEEDS: dict[str, list[tuple[str, str]]] = {
    "MOOD": [
        ("开心", "开心"),
        ("兴奋", "兴奋"),
        ("愉悦", "愉悦"),
        ("平静", "平静"),
        ("复杂", "复杂"),
        ("放松", "放松"),
        ("疲惫", "疲惫"),
        ("麻木", "麻木"),
        ("低落", "低落"),
        ("怅然", "怅然"),
        ("委屈", "委屈"),
        ("烦躁", "烦躁"),
        ("焦虑", "焦虑"),
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
    {
        "key": "today",
        "name": "今天",
        "icon": "lucide:calendar-heart",
        "path": "/Main/Today",
        "sort": 1,
        "parent": None,
        "member": True,
    },
    {
        "key": "timeline",
        "name": "时间线",
        "icon": "lucide:history",
        "path": "/Main/Timeline",
        "sort": 2,
        "parent": None,
        "member": True,
    },
    {
        "key": "stats",
        "name": "统计",
        "icon": "lucide:chart-column",
        "path": "/Main/Stats",
        "sort": 3,
        "parent": None,
        "member": True,
    },
    {
        "key": "share",
        "name": "共享",
        "icon": "lucide:share-2",
        "path": "/Main/Share",
        "sort": 4,
        "parent": None,
        "member": True,
    },
    {
        "key": "system",
        "name": "系统管理",
        "icon": "lucide:settings",
        "path": "",
        "sort": 5,
        "parent": None,
        "member": True,
    },
    {
        "key": "account",
        "name": "账户设置",
        "icon": "lucide:user-round",
        "path": "/System/Account",
        "sort": 1,
        "parent": "system",
        "member": True,
    },
    {
        "key": "settings",
        "name": "系统设置",
        "icon": "lucide:settings-2",
        "path": "/System/Settings",
        "sort": 2,
        "parent": "system",
        "member": False,
    },
    {
        "key": "user",
        "name": "用户管理",
        "icon": "lucide:users",
        "path": "/System/User",
        "sort": 3,
        "parent": "system",
        "member": False,
    },
    {
        "key": "role",
        "name": "角色管理",
        "icon": "lucide:shield-check",
        "path": "/System/Role",
        "sort": 4,
        "parent": "system",
        "member": False,
    },
    {
        "key": "org",
        "name": "组织管理",
        "icon": "lucide:building-2",
        "path": "/System/Organization",
        "sort": 5,
        "parent": "system",
        "member": False,
    },
    {
        "key": "menu",
        "name": "菜单管理",
        "icon": "lucide:list-tree",
        "path": "/System/Menu",
        "sort": 6,
        "parent": "system",
        "member": False,
    },
    {
        "key": "dict",
        "name": "字典管理",
        "icon": "lucide:book-open",
        "path": "/System/BaseCode",
        "sort": 7,
        "parent": "system",
        "member": False,
    },
]


def _system_group(resources: list[Resource], child_paths: set[str]) -> Resource | None:
    """定位“系统管理”分组，兼容老库中分组被误当作“用户管理”页面的情况。"""
    for row in resources:
        if row.name == "系统管理":
            return row
    # 老数据 bug：分组行 pid 指向自身，导致整棵系统菜单不在根节点上
    for row in resources:
        if row.pid == row.id:
            return row
    parents = {row.pid for row in resources if row.web_url in child_paths}
    for row in resources:
        if row.id in parents:
            return row
    return None


def ensure_menu_data(db: Session) -> None:
    """菜单种子：兼容老库中“系统管理”分组被页面占用的历史数据。"""
    resources = list(db.scalars(select(Resource).order_by(Resource.id.asc())).all())
    by_path = {row.web_url: row for row in resources if row.web_url}
    by_key: dict[str, Resource] = {}
    claimed: set[int] = set()
    system_paths = {
        seed["path"]
        for seed in MENU_SEEDS
        if seed["parent"] == "system" and seed["path"]
    }

    for seed in MENU_SEEDS:
        parent = by_key.get(seed["parent"]) if seed["parent"] else None
        parent_id = parent.id if parent else 0
        entity = None
        if seed["key"] == "system":
            entity = _system_group(resources, system_paths)
        elif seed["path"]:
            entity = by_path.get(seed["path"])
            if entity is not None and entity.id in claimed:
                entity = None
        if entity is None and seed["parent"] is None:
            entity = next(
                (
                    row
                    for row in resources
                    if row.pid == 0 and row.name == seed["name"] and row.id not in claimed
                ),
                None,
            )
        if entity is None:
            entity = Resource(
                name=seed["name"],
                pid=parent_id,
                sort=seed["sort"],
                enable="Y",
                icon_name=seed["icon"],
                web_url=seed["path"],
            )
            db.add(entity)
            db.flush()
            resources.append(entity)
            if seed["path"]:
                by_path[seed["path"]] = entity
        else:
            entity.name = seed["name"]
            entity.pid = parent_id
            entity.sort = seed["sort"]
            entity.icon_name = seed["icon"]
            entity.web_url = seed["path"]
        claimed.add(entity.id)
        by_key[seed["key"]] = entity

    owner = db.scalar(select(Role).where(Role.code == "OWNER"))
    member = db.scalar(select(Role).where(Role.code == "MEMBER"))
    if owner is not None:
        assigned = {
            row.resource_id
            for row in db.scalars(
                select(RoleResource).where(RoleResource.role_id == owner.id)
            ).all()
        }
        for entity in by_key.values():
            if entity.id not in assigned:
                db.add(RoleResource(role_id=owner.id, resource_id=entity.id))

    if member is not None:
        assigned = {
            row.resource_id
            for row in db.scalars(
                select(RoleResource).where(RoleResource.role_id == member.id)
            ).all()
        }
        default_keys = {seed["key"] for seed in MENU_SEEDS if seed["member"]}
        for key, entity in by_key.items():
            if key in default_keys and entity.id not in assigned:
                db.add(RoleResource(role_id=member.id, resource_id=entity.id))

    db.commit()


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

    db.flush()
    ensure_menu_data(db)
    ensure_user_org_data(db)


def ensure_user_org_data(db: Session) -> None:
    """为缺少组织关系的用户补齐默认组织，保证多组织成员关系有统一来源。"""
    linked = set(db.scalars(select(UserOrg.user_id)).all())
    org_ids = set(db.scalars(select(Org.id)).all()) or {1}
    for user in db.scalars(select(ComUser).order_by(ComUser.id.asc())).all():
        if user.id in linked:
            continue
        org_id = int(user.org_id or 1)
        db.add(
            UserOrg(
                user_id=user.id,
                company_id=str(org_id if org_id in org_ids else 1),
                insert_user="system",
            )
        )
    db.commit()


def has_users(db: Session) -> bool:
    return db.scalar(select(ComUser.id).limit(1)) is not None
