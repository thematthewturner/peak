"""Bound buffered upload memory before reading a spooled file into Python."""

from functools import wraps
from threading import BoundedSemaphore

from fastapi import HTTPException

UPLOAD_SLOT = BoundedSemaphore(1)


def serial_upload(function):
    @wraps(function)
    def admitted(*args, **kwargs):
        if not UPLOAD_SLOT.acquire(blocking=False):
            raise HTTPException(
                429, "Another upload is processing. Try again shortly.", headers={"Retry-After": "2"}
            )
        try:
            return function(*args, **kwargs)
        finally:
            UPLOAD_SLOT.release()

    return admitted
