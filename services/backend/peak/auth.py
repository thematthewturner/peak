import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from .db import Login, User, get_db
from .config import PRODUCTION

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash(secrets.token_urlsafe(32))


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


def authenticate(request: Request, db=Depends(get_db)):
    token = request.cookies.get("peak_session", "")
    login = db.get(Login, digest(token)) if token else None
    if not login or login.expires <= datetime.now(timezone.utc).isoformat():
        raise HTTPException(401, "Please sign in")
    user = db.get(User, login.user_id)
    if not user:
        raise HTTPException(401, "Account unavailable")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        csrf = request.headers.get("x-csrf-token", "")
        if not secrets.compare_digest(csrf, login.csrf):
            raise HTTPException(403, "Invalid session token; refresh and try again")
    request.state.login = login
    return user


def require_parent(user=Depends(authenticate)):
    if user.role != "parent":
        raise HTTPException(403, "Parent access required")
    return user


# Parents can open answer keys and change settings, so their sessions stay short.
# Students cannot see keys before feedback or change settings, so a phone stays
# signed in for 30 days, renewed whenever they use the app (see slide_session).
PARENT_SESSION = timedelta(hours=12)
STUDENT_SESSION = timedelta(days=30)
STUDENT_RENEW_BELOW = timedelta(days=23)


def session_length(user):
    return STUDENT_SESSION if user.role == "student" else PARENT_SESSION


def set_session_cookie(response, token, length):
    response.set_cookie(
        "peak_session",
        token,
        httponly=True,
        secure=PRODUCTION,
        samesite="strict",
        max_age=int(length.total_seconds()),
        path="/",
    )


def create_login(db, user, response):
    token, csrf = secrets.token_urlsafe(48), secrets.token_urlsafe(32)
    length = session_length(user)
    db.add(
        Login(
            token_hash=digest(token),
            user_id=user.id,
            csrf=csrf,
            expires=(datetime.now(timezone.utc) + length).isoformat(),
        )
    )
    set_session_cookie(response, token, length)
    return csrf


def slide_session(db, request, response, user):
    """Extend a student session to a full 30 days once under 23 days remain. Parents never slide."""
    login = request.state.login
    if user.role != "student":
        return
    now = datetime.now(timezone.utc)
    if datetime.fromisoformat(login.expires) - now < STUDENT_RENEW_BELOW:
        login.expires = (now + STUDENT_SESSION).isoformat()
        db.commit()
        set_session_cookie(response, request.cookies["peak_session"], STUDENT_SESSION)
