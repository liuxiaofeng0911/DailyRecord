from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..common import codes
from ..common.exceptions import ApiError
from ..common.result import ok
from ..common.xss import guard as xss_guard
from ..db import get_db
from ..deps import UserContext, get_current_user
from ..schemas.stats import CalendarRequest
from ..services import stats_service
from ..services.timeutil import today_shanghai

router = APIRouter(
    prefix="/stats",
    tags=["stats"],
    dependencies=[Depends(xss_guard), Depends(get_current_user)],
)


@router.post("/overview")
def overview(
    payload: CalendarRequest,
    db: Session = Depends(get_db),
    user: UserContext = Depends(get_current_user),
):
    if payload.start and payload.end:
        start, end = payload.start, payload.end
    else:
        year = payload.year or today_shanghai().year
        if year < 1970 or year > 2200:
            raise ApiError(codes.BAD_REQUEST, "年份超出范围")
        start, end = date(year, 1, 1), date(year, 12, 31)
    if start > end:
        raise ApiError(codes.BAD_REQUEST, "开始日期不能晚于结束日期")
    return ok(stats_service.overview(db, user.id, start, end))
