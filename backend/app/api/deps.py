from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.config import settings
from app.db.session import get_async_session
from app.models.user import User
from app.schemas.token import TokenPayload

reusable_oauth2 = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_STR}/login/access-token",
)


async def get_current_user(
    db_session: AsyncSession = Depends(get_async_session),
    token: str = Depends(reusable_oauth2),
) -> User:
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.ALGORITHM],
        )
        token_data = TokenPayload(**payload)
        user_id = UUID(token_data.sub)
    except (JWTError, ValidationError) as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Could not validate credentials",
        ) from e
    user = await crud.user.get(db_session=db_session, id=user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_current_active_user(current_user: CurrentUser) -> User:
    if not crud.user.is_active(current_user):
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


CurrentActiveUser = Annotated[User, Depends(get_current_active_user)]


def get_current_active_superuser(current_user: CurrentActiveUser) -> User:
    if not crud.user.is_superuser(current_user):
        raise HTTPException(
            status_code=400,
            detail="The user doesn't have enough privileges",
        )
    return current_user


CurrentSuperuser = Annotated[User, Depends(get_current_active_superuser)]
