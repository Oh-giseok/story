"""Timestamp helpers for naive UTC values used by the database models."""

from datetime import datetime, timedelta, timezone

# Korea uses UTC+09:00 year-round; fixed-offset timezone avoids relying on an
# OS-installed IANA database (which is often absent on Windows deployments).
KST = timezone(timedelta(hours=9), name="KST")


def utc_now_naive():
    """Return current UTC as a naive datetime for existing DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def kst_now_naive():
    """Return current KST as naive for legacy Story timestamp columns."""
    return datetime.now(timezone.utc).astimezone(KST).replace(tzinfo=None)


def as_utc(value):
    """Interpret naive database datetimes as UTC and normalize aware values."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def utc_isoformat(value):
    return as_utc(value).isoformat(timespec="seconds").replace("+00:00", "Z")


def format_kst(value, fmt="%Y-%m-%d %H:%M"):
    if not value:
        return ""
    return as_utc(value).astimezone(KST).strftime(fmt)
