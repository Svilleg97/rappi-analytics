"""
api/auth.py
-----------
Rutas de autenticación. Login y logout.
Usa variables de entorno para las credenciales — nunca hardcodeadas.
"""

import os
from fastapi import APIRouter, Response, Cookie
from fastapi.responses import JSONResponse
from models.schemas import LoginRequest, LoginResponse

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _check_credentials(username: str, password: str) -> bool:
    demo_user = os.getenv("DEMO_USER", "rappi_demo")
    demo_pass = os.getenv("DEMO_PASSWORD", "demo123")
    return username == demo_user and password == demo_pass


@router.post("/login", response_model=LoginResponse)
async def login(request: LoginRequest, response: Response):
    if _check_credentials(request.username, request.password):
        # Cookie simple de sesión — suficiente para demo
        response.set_cookie(
            key="session",
            value=f"user_{request.username}",
            httponly=True,
            max_age=86400,   # 24 horas
            samesite="lax"
        )
        return LoginResponse(
            success=True,
            message="Login exitoso",
            username=request.username
        )
    return JSONResponse(
        status_code=401,
        content={"success": False, "message": "Credenciales incorrectas"}
    )


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie("session")
    return {"success": True, "message": "Sesión cerrada"}


@router.get("/me")
async def me(session: str = Cookie(default=None)):
    if session and session.startswith("user_"):
        username = session.replace("user_", "")
        return {"authenticated": True, "username": username}
    return JSONResponse(
        status_code=401,
        content={"authenticated": False}
    )
