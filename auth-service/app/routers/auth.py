from datetime import timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

try:
    from app.database import get_db
    from app.models import User
    from app.schemas import UserCreate, UserLogin, UserOut, Token
    from app.auth_utils import hash_password, verify_password, create_access_token
    from app.dependencies import get_current_user
except ImportError:
    from .database import get_db
    from .models import User
    from .schemas import UserCreate, UserLogin, UserOut, Token
    from .auth_utils import hash_password, verify_password, create_access_token
    from .dependencies import get_current_user

router = APIRouter(tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserOut,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user"
)
async def register(
    user_data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    # 1. Validate email not already taken
    existing_user = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    if existing_user.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email is already registered"
        )

    # 2. Hash password
    hashed_pwd = hash_password(user_data.password)

    # 3. Create and insert User
    new_user = User(
        email=user_data.email,
        hashed_password=hashed_pwd,
        is_active=True
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.post(
    "/login",
    response_model=Token,
    summary="Authenticate and receive access token"
)
async def login(
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    # 1. Look up user by email
    result = await db.execute(
        select(User).where(User.email == user_data.email)
    )
    user = result.scalar_one_or_none()

    # 2. Verify password
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Inactive user account"
        )

    # 3. Create access token
    access_token = create_access_token(
        data={"sub": str(user.id), "email": user.email}
    )

    return Token(access_token=access_token, token_type="bearer")


@router.get(
    "/me",
    response_model=UserOut,
    summary="Get current authenticated user"
)
async def get_me(
    current_user: User = Depends(get_current_user)
):
    return current_user
