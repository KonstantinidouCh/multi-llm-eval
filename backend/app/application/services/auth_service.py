"""
Authentication service for user management and JWT token handling.
"""

from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from ...config import get_settings
from ...infrastructure.persistence.models import UserDB


# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class Token(BaseModel):
    """Token response model"""
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    """Data extracted from JWT token"""
    user_id: Optional[str] = None
    username: Optional[str] = None
    email: Optional[str] = None


class UserCreate(BaseModel):
    """User registration model"""
    email: EmailStr
    username: str
    password: str


class UserLogin(BaseModel):
    """User login model"""
    username: str  # Can be username or email
    password: str


class UserResponse(BaseModel):
    """User response model (without password)"""
    id: str
    email: str
    username: str
    is_active: bool
    is_admin: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AuthService:
    """Service for handling authentication operations"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify a password against its hash"""
        return pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        """Hash a password"""
        return pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        """Create a JWT access token"""
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(
                minutes=self.settings.jwt_access_token_expire_minutes
            )
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(
            to_encode,
            self.settings.jwt_secret_key,
            algorithm=self.settings.jwt_algorithm
        )
        return encoded_jwt

    def decode_token(self, token: str) -> Optional[TokenData]:
        """Decode and validate a JWT token"""
        try:
            payload = jwt.decode(
                token,
                self.settings.jwt_secret_key,
                algorithms=[self.settings.jwt_algorithm]
            )
            user_id: str = payload.get("sub")
            username: str = payload.get("username")
            email: str = payload.get("email")
            if user_id is None:
                return None
            return TokenData(user_id=user_id, username=username, email=email)
        except JWTError:
            return None

    async def get_user_by_email(self, email: str) -> Optional[UserDB]:
        """Get a user by email"""
        result = await self.db.execute(
            select(UserDB).where(UserDB.email == email)
        )
        return result.scalar_one_or_none()

    async def get_user_by_username(self, username: str) -> Optional[UserDB]:
        """Get a user by username"""
        result = await self.db.execute(
            select(UserDB).where(UserDB.username == username)
        )
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: str) -> Optional[UserDB]:
        """Get a user by ID"""
        result = await self.db.execute(
            select(UserDB).where(UserDB.id == user_id)
        )
        return result.scalar_one_or_none()

    async def authenticate_user(self, username: str, password: str) -> Optional[UserDB]:
        """Authenticate a user by username/email and password"""
        # Try to find by username first, then by email
        user = await self.get_user_by_username(username)
        if not user:
            user = await self.get_user_by_email(username)
        if not user:
            return None
        if not self.verify_password(password, user.hashed_password):
            return None
        if not user.is_active:
            return None
        return user

    async def create_user(self, user_data: UserCreate) -> UserDB:
        """Create a new user"""
        # Check if email already exists
        existing_email = await self.get_user_by_email(user_data.email)
        if existing_email:
            raise ValueError("Email already registered")

        # Check if username already exists
        existing_username = await self.get_user_by_username(user_data.username)
        if existing_username:
            raise ValueError("Username already taken")

        # Create new user
        hashed_password = self.get_password_hash(user_data.password)
        db_user = UserDB(
            email=user_data.email,
            username=user_data.username,
            hashed_password=hashed_password,
        )
        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)
        return db_user

    async def login(self, login_data: UserLogin) -> Optional[Token]:
        """Login a user and return a token"""
        user = await self.authenticate_user(login_data.username, login_data.password)
        if not user:
            return None

        access_token = self.create_access_token(
            data={
                "sub": user.id,
                "username": user.username,
                "email": user.email,
            }
        )
        return Token(access_token=access_token)

    async def register(self, user_data: UserCreate) -> Token:
        """Register a new user and return a token"""
        user = await self.create_user(user_data)
        access_token = self.create_access_token(
            data={
                "sub": user.id,
                "username": user.username,
                "email": user.email,
            }
        )
        return Token(access_token=access_token)
