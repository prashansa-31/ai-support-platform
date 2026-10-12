from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import UserRegister, UserResponse, UserLogin, TokenResponse
from app.security import hash_password, verify_password, create_access_token
from app.dependencies.auth import get_current_user, require_admin, require_support_agent

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register_user(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    # Check whether this email is already registered.
    result = await db.execute(select(User).where(User.email == str(user_data.email)))
    existing_user = result.scalar_one_or_none()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    # Never store a plain-text password.
    user = User(
        email=str(user_data.email),
        hashed_password=hash_password(user_data.password),
        full_name=user_data.full_name,
    )

    db.add(user)

    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError:
        # Also handle concurrent registration attempts.
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login_user(
    user_data: UserLogin,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    result = await db.execute(select(User).where(User.email == str(user_data.email)))
    user = result.scalar_one_or_none()

    # Use the same response for unknown emails and incorrect passwords.
    if not user or not verify_password(
        user_data.password,
        user.hashed_password if user else "",
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is inactive",
        )

    access_token = create_access_token(
        user.id
    )  # Returns a signed JWT for successful login

    return TokenResponse(access_token=access_token)


@router.get("/me", response_model=UserResponse)
async def read_current_user(
    current_user: User = Depends(get_current_user),
) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.get("/admin-check")
async def admin_check(
    current_user: User = Depends(require_admin),
):
    return {
        "message": "Admin access granted",
        "user_id": current_user.id,
        "role": current_user.role,
    }


@router.get("/support-check")
async def support_check(
    current_user: User = Depends(require_support_agent),
):
    return {
        "message": "Support access granted",
        "user_id": current_user.id,
        "role": current_user.role,
    }
