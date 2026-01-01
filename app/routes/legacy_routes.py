from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
import os

router = APIRouter(tags=["Legacy"])

@router.get("/connect/{platform}")
async def legacy_connect(platform: str, request: Request):
    """
    Redirect legacy /connect/{platform} requests to /auth/connect/{platform}
    """
    query_params = request.query_params
    new_url = f"/auth/connect/{platform}"
    if query_params:
        new_url += f"?{query_params}"
    return RedirectResponse(new_url)

@router.get("/connect/{platform}/callback")
async def legacy_callback(platform: str, request: Request):
    """
    Redirect legacy /connect/{platform}/callback requests to /auth/{platform}/callback
    """
    query_params = request.query_params
    new_url = f"/auth/{platform}/callback"
    if query_params:
        new_url += f"?{query_params}"
    return RedirectResponse(new_url)
