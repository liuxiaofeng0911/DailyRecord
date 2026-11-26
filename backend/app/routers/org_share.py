"""组织管理内的记录共享：仅所有者可查看组织成员的每日记录。"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError
from ..common.page import MAX_PAGE_SIZE
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..db import get_db
from ..deps import UserContext, get_current_user, require_owner
from ..schemas.share import ShareEntriesRequest, ShareMembersRequest
from ..services import share_service

router = APIRouter(
    prefix="/org-share",
    tags=["org-share"],
    dependencies=[Depends(xss_guard), Depends(get_current_user), Depends(require_owner)],
)


def _org_id(value: str | None) -> int | None:
    if value is None or value == "" or value == "0":
        return None
    return int(value)


@router.post("/members")
def members(
    payload: ShareMembersRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    rows = share_service.org_members(
        db, _org_id(payload.org_id), payload.include_children
    )
    return ok(share_service.serialize_members(db, rows))


@router.post("/entries")
def entries(
    payload: ShareEntriesRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    page_data = payload.page or {}
    try:
        page_number = max(int(page_data.get("pageNumber") or payload.page_number or 1), 1)
        page_size = min(
            max(int(page_data.get("pageSize") or payload.page_size or 20), 1),
            MAX_PAGE_SIZE,
        )
    except (TypeError, ValueError):
        raise ApiError(codes.BAD_REQUEST, "分页参数不正确") from None

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
