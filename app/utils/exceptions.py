from typing import Any, Generic, Type, TypeVar
from uuid import UUID

from fastapi import HTTPException, status
from sqlmodel import SQLModel

ModelType = TypeVar("ModelType", bound=SQLModel)


class ContentNoChangeException(HTTPException):
    def __init__(
        self,
        detail: Any = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(status_code=status.HTTP_400_BAD_REQUEST, detail=detail, headers=headers)


class IDNotFoundException(HTTPException, Generic[ModelType]):
    def __init__(
        self,
        model: Type[ModelType],
        id: UUID | str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        if id:
            super().__init__(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unable to find the {model.__name__} with id {id}.",
                headers=headers,
            )
            return

        super().__init__(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"{model.__name__} id not found.",
            headers=headers,
        )


class NameNotFoundException(HTTPException, Generic[ModelType]):
    def __init__(
        self,
        model: Type[ModelType],
        name: str | None = None,
        headers: dict[str, Any] | None = None,
    ) -> None:
        if name:
            super().__init__(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Unable to find the {model.__name__} named {name}.",
                headers=headers,
            )
        else:
            super().__init__(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"{model.__name__} name not found.",
                headers=headers,
            )


class NameExistException(HTTPException, Generic[ModelType]):
    def __init__(
        self,
        model: Type[ModelType],
        name: str,
        headers: dict[str, Any] | None = None,
    ) -> None:
        if name:
            super().__init__(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"The {model.__name__} name {name} already exists.",
                headers=headers,
            )
            return

        super().__init__(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"The {model.__name__} name already exists.",
            headers=headers,
        )
