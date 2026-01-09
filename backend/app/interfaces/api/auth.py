"""
Authentication API routes and dependencies.
"""

from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from ...infrastructure.persistence.database import get_db
from ...application.services.auth_service import (
    AuthService,
    Token,
    UserCreate,
    UserLogin,
    UserResponse,
    TokenData,
)
from ...infrastructure.persistence.models import UserDB


# OAuth2 scheme for token extraction
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)


router = APIRouter(prefix="/api/auth", tags=["Authentication"])


async def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    """Dependency to get auth service"""
    return AuthService(db)


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> Optional[UserDB]:
    """
    Dependency to get the current authenticated user.
    Returns None if no valid token is provided (for optional auth).
    """
    if not token:
        return None

    auth_service = AuthService(db)
    token_data = auth_service.decode_token(token)
    if not token_data or not token_data.user_id:
        return None

    user = await auth_service.get_user_by_id(token_data.user_id)
    if not user or not user.is_active:
        return None

    return user


async def get_current_user_required(
    current_user: Optional[UserDB] = Depends(get_current_user),
) -> UserDB:
    """
    Dependency that requires authentication.
    Raises 401 if user is not authenticated.
    """
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


@router.post("/register", response_model=Token)
async def register(
    user_data: UserCreate,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Register a new user account"""
    try:
        token = await auth_service.register(user_data)
        return token
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.post("/login", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
):
    """Login with username/email and password (OAuth2 form)"""
    login_data = UserLogin(username=form_data.username, password=form_data.password)
    token = await auth_service.login(login_data)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@router.post("/login/json", response_model=Token)
async def login_json(
    login_data: UserLogin,
    auth_service: AuthService = Depends(get_auth_service),
):
    """Login with JSON body (alternative to OAuth2 form)"""
    token = await auth_service.login(login_data)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password",
        )
    return token


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(
    current_user: UserDB = Depends(get_current_user_required),
):
    """Get the current authenticated user's information"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
    )


@router.post("/verify", response_model=UserResponse)
async def verify_token(
    current_user: UserDB = Depends(get_current_user_required),
):
    """Verify that the current token is valid"""
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        is_active=current_user.is_active,
        is_admin=current_user.is_admin,
        created_at=current_user.created_at,
    )
