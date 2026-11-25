"""
EBRAINS IAM / Keycloak login for curators (authorization-code flow),
distinct from the wizard's service-account (client_credentials) flow —
here we need to know WHICH curator is doing the validation, so a real
user login is required.

The session itself is a signed HTTP-only cookie (itsdangerous), matching
the wizard's move away from storing tokens in React state.
"""
from typing import Optional
import time
import httpx
from fastapi import APIRouter, Request, Response, HTTPException
from itsdangerous import URLSafeTimedSerializer, BadSignature

from .config import settings

router = APIRouter(prefix="/auth", tags=["auth"])

_serializer = URLSafeTimedSerializer(
    settings.SESSION_SECRET, salt="curation-validator-session")
SESSION_COOKIE = "cv_session"
SESSION_MAX_AGE = 60 * 60 * 8  # 8h workday


def _set_session(response: Response, payload: dict) -> None:
    token = _serializer.dumps(payload)
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=SESSION_MAX_AGE,
        httponly=True,
        # Browsers drop a `secure` cookie on a plain http://localhost origin,
        # which is exactly how this app is run locally, so only require it
        # once DEV_MODE is off (i.e. in a real, HTTPS-served deployment).
        secure=not settings.DEV_MODE,
        samesite="lax",
    )


def get_current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(status_code=401, detail="Not logged in")
    try:
        payload = _serializer.loads(token, max_age=SESSION_MAX_AGE)
    except BadSignature:
        raise HTTPException(status_code=401, detail="Invalid session")
    return payload


@router.get("/login")
async def login():
    """Redirect the curator to EBRAINS IAM for login — unless DEV_MODE is
    on, in which case there is no real OIDC client to redirect to yet, so
    we log in a fake local curator instead (see /auth/dev-login)."""
    from fastapi.responses import RedirectResponse

    if settings.DEV_MODE:
        return RedirectResponse("/auth/dev-login")

    from urllib.parse import urlencode

    params = {
        "client_id": settings.OIDC_CLIENT_ID,
        "redirect_uri": settings.OIDC_REDIRECT_URI,
        "response_type": "code",
        "scope": settings.OIDC_SCOPE,
    }
    return RedirectResponse(f"{settings.iam_auth_endpoint}?{urlencode(params)}")


@router.get("/dev-login")
async def dev_login():
    """
    LOCAL DEVELOPMENT ONLY. Logs in a fake curator with no real EBRAINS IAM
    token, so the UI (dashboard, new-validation form, checklist, export
    buttons) can be clicked through before an OIDC client exists for this
    app. Anything that actually calls the KG (pulling a real dataset
    version) will still fail without a genuine kg_access_token — that part
    can only be tested once IAM is wired up.
    """
    from fastapi.responses import RedirectResponse

    if not settings.DEV_MODE:
        raise HTTPException(status_code=404, detail="Not found")

    response = RedirectResponse(settings.FRONTEND_ORIGIN)
    _set_session(
        response,
        {
            "sub": "dev-user",
            "name": "Dev Curator",
            "email": "dev-curator@example.org",
            "kg_access_token": "dev-mode-fake-token",
            "kg_token_expires_at": time.time() + 3600,
        },
    )
    return response


@router.get("/callback")
async def callback(code: Optional[str] = None, error: Optional[str] = None):
    if error or not code:
        raise HTTPException(
            status_code=400, detail=f"IAM login failed: {error}")

    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            settings.iam_token_endpoint,
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.OIDC_REDIRECT_URI,
                "client_id": settings.OIDC_CLIENT_ID,
                "client_secret": settings.OIDC_CLIENT_SECRET,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        if token_resp.status_code != 200:
            raise HTTPException(
                status_code=401, detail="IAM token exchange failed")
        tokens = token_resp.json()

        userinfo_resp = await client.get(
            settings.iam_userinfo_endpoint,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        userinfo = userinfo_resp.json() if userinfo_resp.status_code == 200 else {}

    from fastapi.responses import RedirectResponse

    response = RedirectResponse(settings.FRONTEND_ORIGIN)
    _set_session(
        response,
        {
            "sub": userinfo.get("sub"),
            "name": userinfo.get("name") or userinfo.get("preferred_username"),
            "email": userinfo.get("email"),
            # The KG access token itself — needed so curators only ever see
            # data they themselves are allowed to see in the KG (vs. the
            # wizard's service-account approach which has its own broad scope).
            "kg_access_token": tokens["access_token"],
            "kg_token_expires_at": time.time() + tokens.get("expires_in", 300),
        },
    )
    return response


@router.get("/me")
async def me(request: Request):
    user = get_current_user(request)
    return {"name": user.get("name"), "email": user.get("email")}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(SESSION_COOKIE)
    return {"ok": True}
