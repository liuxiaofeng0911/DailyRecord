"""上海时区统一时间工具。

数据库存上海本地时间（naive），接口输出 yyyy-MM-dd HH:mm:ss。
业务代码禁止直接调用 datetime.now()。
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from ..config import settings

TZ = ZoneInfo(settings.app_timezone)
DATE_FMT = "%Y-%m-%d"
DATETIME_FMT = "%Y-%m-%d %H:%M:%S"


def now_shanghai() -> datetime:
    """当前上海时间（naive，便于写入 timestamp 列）。"""
    return datetime.now(TZ).replace(tzinfo=None, microsecond=0)


def today_shanghai() -> date:
    return datetime.now(TZ).date()


def to_shanghai(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(TZ).replace(tzinfo=None)


def parse_date(value: str | date | None) -> date:
    if value is None:
        return today_shanghai()
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return to_shanghai(value).date()
    return datetime.strptime(value[:10], DATE_FMT).date()


def parse_datetime(value: str | datetime | None) -> datetime | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return to_shanghai(value)
    raw = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(raw)
    except ValueError:
        return None
    return to_shanghai(parsed)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    return datetime.combine(day, time.min), datetime.combine(day, time.max)


def week_range(anchor: date) -> tuple[date, date]:
    """周一为每周第一天。"""
    start = anchor - timedelta(days=anchor.weekday())
    return start, start + timedelta(days=6)


def month_range(anchor: date) -> tuple[date, date]:
    start = anchor.replace(day=1)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1) - timedelta(days=1)
    else:
        end = start.replace(month=start.month + 1) - timedelta(days=1)
    return start, end


def year_range(year: int) -> tuple[date, date]:
    return date(year, 1, 1), date(year, 12, 31)


def fmt_datetime(value: datetime | None) -> str | None:
    return value.strftime(DATETIME_FMT) if value else None


def fmt_date(value: date | None) -> str | None:
    return value.strftime(DATE_FMT) if value else None
