"""Shared datetime serialization for API response schemas.

SQLite roundtrips DateTime(timezone=True) columns as naive Python datetimes
(it stores ISO text without offset and SQLAlchemy doesn't reconstruct tz on
read). Naive datetimes serialize as ISO without "Z", and JS `new Date(...)`
on those treats the string as local time — every readout drifts by the
client's UTC offset.

`utc_aware` tags naive datetimes as UTC so pydantic's default isoformat
serializer emits an explicit offset. All timestamps the backend writes are
UTC by convention (datetime.now(tz=timezone.utc) at write time).
"""

from datetime import datetime, timezone


def utc_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
