"""组织内记录共享：所有者查看任意组织成员记录，成员按双向规则互相可见。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError, forbidden
from ..common.page import MAX_PAGE_SIZE
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..db import get_db
from ..deps import UserContext, get_current_user, require_owner
from ..schemas.share import (
    MyShareEntriesRequest,
    ShareConfigRequest,
    ShareConfigSaveRequest,
    ShareEntriesRequest,
    ShareMembersRequest,
)
from ..services import share_service

router = APIRouter(
    prefix="/org-share",
    tags=["org-share"],
    dependencies=[Depends(xss_guard), Depends(get_current_user)],
)


def _org_id(value: str | None) -> int | None:
    if value is None or value == "" or value == "0":
        return None
    return int(value)


def _page_params(payload, page_data: dict | None) -> tuple[int, int]:
    data = page_data or {}
    try:
        page_number = max(int(data.get("pageNumber") or payload.page_number or 1), 1)
        page_size = min(
            max(int(data.get("pageSize") or payload.page_size or 20), 1),
            MAX_PAGE_SIZE,
        )
    except (TypeError, ValueError):
        raise ApiError(codes.BAD_REQUEST, "分页参数不正确") from None
    return page_number, page_size


@router.post("/members")
def members(
    payload: ShareMembersRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_owner),
):
    rows = share_service.org_members(
        db, _org_id(payload.org_id), payload.include_children
    )
    return ok(share_service.serialize_members(db, rows))


@router.post("/entries")
def entries(
    payload: ShareEntriesRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(require_owner),
):
    page_number, page_size = _page_params(payload, payload.page)
    members = share_service.org_members(
        db, _org_id(payload.org_id), payload.include_children
    )
    data = share_service.shared_entries(
        db,
        members,
        user_id=int(payload.user_id) if payload.user_id else None,
        start=payload.start,
        end=payload.end,
        keyword=payload.keyword,
        page_number=page_number,
        page_size=page_size,
    )
    return ok(data)


@router.post("/my/orgs")
def my_orgs(
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    return ok(share_service.my_orgs(db, user.id, user.is_owner))


@router.post("/my/config/get")
def my_config_get(
    payload: ShareConfigRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    org_id = _org_id(payload.org_id)
    if org_id is None:
        orgs = share_service.my_orgs(db, user.id, user.is_owner)
        if not orgs:
            return ok(None)
        org_id = int(orgs[0].id)
    if not user.is_owner and org_id not in share_service.user_org_ids(db, user.id):
        raise forbidden("你不在该组织中，无法查看共享配置")
    return ok(share_service.share_config(db, org_id, user.id, user.is_owner))


@router.post("/my/config/save")
def my_config_save(
    payload: ShareConfigSaveRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    if user.is_owner:
        raise forbidden("所有者不属于组织，无需配置共享")
    org_id = int(payload.org_id)
    share_service.save_share_config(
        db, org_id, user.id, payload.allow_ids, payload.watch_ids, user.userid
    )
    db.commit()
    return ok(share_service.share_config(db, org_id, user.id, False))


@router.post("/my/entries")
def my_entries(
    payload: MyShareEntriesRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    page_number, page_size = _page_params(payload, payload.page)
    data = share_service.my_shared_entries(
        db,
        user.id,
        is_owner=user.is_owner,
        org_id=_org_id(payload.org_id),
        start=payload.start,
        end=payload.end,
        keyword=payload.keyword,
        page_number=page_number,
        page_size=page_size,
    )
    return ok(data)
