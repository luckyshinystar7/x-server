from typing import Optional

from datetime import datetime, timedelta

import jwt
from fastapi import APIRouter, HTTPException, Response, Request, Depends, status
from sqlalchemy.exc import IntegrityError
from pydantic import BaseModel, constr
from loguru import logger

from src.db.dal import DAL
from src.db.models import User, Session
from src.utils.password import hash_password

from src.utils.password import verify_password
from src.token.token_maker import JWTTokenManager, get_current_user, UserPayload

from settings import REFRESH_TOKEN_DURATION_MINUTES

users_router = APIRouter(prefix="/users")


class CreateUserRequest(BaseModel):
    username: str
    password: str
    fullname: str
    email: str


class CreateUserResponse(BaseModel):
    username: str
    fullname: str
    email: str
    role: str


@users_router.post(
    "/", response_model=CreateUserResponse, status_code=status.HTTP_201_CREATED
)
async def create_user(user_request: CreateUserRequest):
    hashed_password = hash_password(password=user_request.password)

    user = User(
        email=user_request.email,
        full_name=user_request.fullname,
        username=user_request.username,
        hashed_password=hashed_password,
    )

    try:
        user = await DAL().create_user(user=user)
    except Exception as ex:
        if isinstance(ex, IntegrityError):
            logger.warning(f"create user exception ex: {ex}")
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="unable to create user due to conflict",
            )
        if "Connect call failed" in ex.strerror:
            logger.critical(f"db connection failed: {ex}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)

    user_response = CreateUserResponse(
        username=user.username,
        fullname=user.full_name,
        email=user.email,
        role=user.role,
    )

    return user_response


@users_router.get("/{username}", response_model=CreateUserResponse)
async def get_user(
    username: str, current_user: UserPayload = Depends(get_current_user)
):
    if username != current_user.username and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Not allowed")
    try:
        user = await DAL().get_user(username=username)
    except Exception as ex:
        ex_msg = "Failed to fetch user"
        logger.warning(ex_msg + f": {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ex_msg,
        )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return CreateUserResponse(
        username=user.username,
        fullname=user.full_name,
        email=user.email,
        role=user.role,
    )


class UpdateUserRequest(BaseModel):
    current_password: Optional[str] = None
    password: Optional[str] = None
    fullname: Optional[str] = None
    email: Optional[str] = None


@users_router.put("/{username}", response_model=CreateUserResponse)
async def update_user(
    username: str,
    update_request: UpdateUserRequest,
    current_user: UserPayload = Depends(get_current_user),
):
    if username != current_user.username and current_user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not allowed")

    try:
        user = await DAL().get_user(username=username)
    except Exception as ex:
        ex_msg = "Failed to fetch user"
        logger.warning(ex_msg + f": {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ex_msg,
        )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if update_request.fullname:
        user.full_name = update_request.fullname
    if update_request.email:
        user.email = update_request.email
    if update_request.password:

        if not update_request.current_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="current password not provided",
            )

        if update_request.current_password == update_request.password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="current and new password must be different",
            )

        if not verify_password(
            plain_password=update_request.current_password,
            hashed_password=user.hashed_password,
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="current password doesn't match",
            )

        user.hashed_password = hash_password(password=update_request.password)
        user.password_changed_at = datetime.utcnow()

    await DAL().update_user(username=username, user=user)

    return CreateUserResponse(
        username=user.username,
        fullname=user.full_name,
        email=user.email,
        role=user.role,
    )


class LoginUserRequest(BaseModel):
    username: constr(pattern="^[a-zA-Z0-9]+$")
    password: constr(min_length=6)


@users_router.post("/login")
async def login_user(login_request: LoginUserRequest, response: Response):
    try:
        user = await DAL().get_user(username=login_request.username)
    except Exception as ex:
        ex_msg = "unable to get user"
        logger.warning(ex_msg + f": {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=ex_msg
        )

    if not user:
        logger.warning("user not found")
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    if not verify_password(
        plain_password=login_request.password, hashed_password=user.hashed_password
    ):
        ex_msg = "invalid password"
        logger.warning(ex_msg)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=ex_msg)

    try:
        access_token, access_payload = JWTTokenManager.create_token(
            username=user.username, role=user.role
        )
    except Exception as ex:
        ex_msg = "unable to create access_token for user"
        logger.warning(ex_msg + f": {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=ex_msg,
        )

    try:
        refresh_token, refresh_payload = JWTTokenManager.create_token(
            username=user.username,
            role=user.role,
            expires_delta=timedelta(minutes=int(REFRESH_TOKEN_DURATION_MINUTES)),
        )
    except Exception as ex:
        ex_msg = "unable to create refresh_token for user"
        logger.warning(ex_msg + f": {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=ex_msg
        )

    session = Session(
        id=refresh_payload.id,
        username=user.username,
        refresh_token=refresh_token,
        user_agent="",
        client_ip="",
        expires_at=refresh_payload.exp,
    )
    try:
        _ = await DAL().create_session(new_session=session)
    except Exception as ex:
        if isinstance(ex, IntegrityError):
            ex_msg = "unable to create user due to conflict"
            logger.warning(ex_msg + f": {ex}")

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=ex_msg,
            )
        ex_msg = "unable to create session"
        logger.warning(ex_msg + f": {ex}")

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=ex_msg
        )

    response.set_cookie(
        key="access_token", value=access_token, httponly=True, secure=True, path="/"
    )
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=True,
        max_age=REFRESH_TOKEN_DURATION_MINUTES * 60,
        path="/",
    )


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class RefreshTokenResponse(BaseModel):
    access_token: str
    access_token_expires_at: datetime
    refresh_token: str
    refresh_token_expires_at: datetime
    user: CreateUserResponse


@users_router.post("/refresh_token")
async def refresh_token_endpoint(request: Request, response: Response):
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token missing"
        )
    try:
        payload = JWTTokenManager.verify_token(refresh_token)
        access_token, access_payload = JWTTokenManager.create_token(
            username=payload.username, role=payload.role
        )
        response.set_cookie(
            key="access_token", value=access_token, httponly=True, secure=True
        )
        return {"message": "Access token refreshed"}
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token has expired.",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification error: {e}",
        )

    except JWTTokenManager.TokenVerificationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    except Exception as ex:
        logger.error(f"Failed to refresh token: {ex}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to refresh token",
        )


@users_router.get("/session/check", response_model=CreateUserResponse)
async def check_user_session(request: Request):
    access_token = request.cookies.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token missing"
        )
    try:
        payload = JWTTokenManager.verify_token(access_token)
        user = await DAL().get_user(username=payload.username)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
            )
        return CreateUserResponse(
            username=user.username,
            fullname=user.full_name,
            email=user.email,
            role=user.role,
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired.",
        )
    except jwt.PyJWTError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Token verification error: {e}",
        )


@users_router.post("/logout")
async def logout_user(response: Response):
    response.delete_cookie(key="access_token", path="/")
    response.delete_cookie(key="refresh_token", path="/")
    return {"message": "Logged out successfully."}
