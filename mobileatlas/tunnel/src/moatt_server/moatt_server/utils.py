import datetime

from typing import Any, Iterable

def now() -> datetime.datetime:
    return datetime.datetime.now(tz=datetime.timezone.utc)

def flatten(l: Iterable[Iterable[Any]]) -> list[Any]:
    return [elem for subl in l for elem in subl]
