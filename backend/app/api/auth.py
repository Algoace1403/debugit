import httpx
from urllib.parse import urlencode
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse

from app.config import settings

auth_router = APIRouter(prefix="/api/v1/auth")

GITHUB_AUTHORIZE_URL = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN_URL = "https://github.com/login/oauth/access_token"
GITHUB_USER_URL = "https://api.github.com/user"


@auth_router.get("/github")
async def github_login():
    """Redirect user to GitHub OAuth authorization page."""
    if not settings.github_client_id:
        raise HTTPException(status_code=500, detail="GitHub OAuth not configured")

    params = {
        "client_id": settings.github_client_id,
        "scope": "read:user user:email",
    }
    return RedirectResponse(url=f"{GITHUB_AUTHORIZE_URL}?{urlencode(params)}")


@auth_router.get("/github/callback")
async def github_callback(code: str):
    """Exchange GitHub code for access token, fetch user profile, redirect to frontend."""
    if not code:
        raise HTTPException(status_code=400, detail="Missing code parameter")

    # Exchange code for access token
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            GITHUB_TOKEN_URL,
            json={
                "client_id": settings.github_client_id,
                "client_secret": settings.github_client_secret,
                "code": code,
            },
            headers={"Accept": "application/json"},
        )

    if token_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to get token from GitHub")

    token_data = token_resp.json()
    access_token = token_data.get("access_token")
    if not access_token:
        error = token_data.get("error_description", "Unknown error")
        raise HTTPException(status_code=400, detail=f"GitHub OAuth error: {error}")

    # Fetch user profile
    async with httpx.AsyncClient() as client:
        user_resp = await client.get(
            GITHUB_USER_URL,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/vnd.github.v3+json",
            },
        )

    if user_resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Failed to fetch GitHub profile")

    user = user_resp.json()

    # Redirect to frontend with user info as query params
    params = urlencode({
        "login": user.get("login", ""),
        "name": user.get("name", "") or user.get("login", ""),
        "avatar_url": user.get("avatar_url", ""),
        "github_id": user.get("id", ""),
    })
    return RedirectResponse(url=f"{settings.frontend_url}/auth/callback?{params}")
