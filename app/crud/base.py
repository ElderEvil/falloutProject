from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from pydantic import UUID4
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=SQLModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=SQLModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base class for CRUD (Create, Read, Update, Delete) operations on a SQLModel in a database session.

    :param model: A SQLModel type that represents the database table to perform CRUD operations on.
    """

    def __init__(self, model: type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: int | UUID4) -> ModelType | None:
        """
        Gets a single item of the specified model type by ID.

        :param db: A database session.
        :param id: The ID of an object to retrieve.
        :returns: The retrieved item or `None` if it does not exist.
        """
        query = select(self.model).where(self.model.id == id)
        response = await db.execute(query)
        return response.scalar_one_or_none()

    async def get_by_ids(self, list_ids: list[UUID4 | str], db: AsyncSession) -> list[ModelType] | None:
        """
        Gets a list of items of the specified model type by a list of IDs.

        :param list_ids: A list of IDs of objects to retrieve.
        :param db: A database session.
        :returns: list of items
        """
        response = await db.execute(select(self.model).where(self.model.id.in_(list_ids)))
        return response.scalars().all()

    async def get_count(self, db: AsyncSession) -> ModelType:
        """
        Gets the number of items of the specified model type in the database.

        :param db: A database session.
        :returns: The number of items.
        """
        response = await db.execute(select(func.count()).select_from(select(self.model).subquery()))
        return response.scalar_one()

    async def get_multi(self, db: AsyncSession, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """
        Gets a list of items of the specified model type, optionally skipping the first `skip` items and limiting the
        result to `limit` items.

        :param db: A database session.
        :param skip: The number of items to skip before returning results.
        :param limit: The maximum number of items to return.
        :returns: A list of retrieved items.
        """
        query = select(self.model).offset(skip).limit(limit).order_by(self.model.id)
        response = await db.execute(query)
        return response.scalars().all()

    async def create(self, db: AsyncSession, obj_in: CreateSchemaType) -> ModelType:
        """
        Creates a new item of the specified model type in the database.

        :param db: A database session.
        :param obj_in: The item to create.
        :returns: The created object, with any auto-generated fields populated by the database.
        :raises HTTPException: If the item already exists.
        """
        db_obj = self.model.from_orm(obj_in)
        try:
            db.add(db_obj)
            await db.commit()
        except IntegrityError as e:
            await db.rollback()
            raise HTTPException(
                status_code=409,
                detail="Resource already exists",
            ) from e
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, id: int | UUID4, obj_in: UpdateSchemaType | dict[str, Any]) -> ModelType:
        """
        Updates an existing item of the specified model type in the database.

        :param db: A database session.
        :param id: The ID of the object to update.
        :param obj_in: A new version of an object to update to, either as a SQLModel instance or a dictionary.
        :returns: The updated item, with any changes persisted to the database.
        """
        db_obj = await self.get(db=db, id=id)
        if db_obj is None:
            raise HTTPException(status_code=404, detail=f"{self.model.__name__} not found")

        update_data = obj_in if isinstance(obj_in, dict) else obj_in.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, id: int | UUID4) -> ModelType:
        """
        Remove a database object with the given ID.

        If the object exists, it is deleted from the database and returned.
        If the object does not exist, None is returned instead.

        :param db: A database session
        :param id: ID of the object to remove
        :returns: the removed object, or None if it does not exist
        :raises HTTPException: if there is an error finding object in database
        """
        response = await db.execute(select(self.model).where(self.model.id == id))
        obj = response.scalar_one()
        if not obj:
            raise HTTPException(status_code=404, detail=f"{self.model.__name__} not found")
        await db.delete(obj)
        await db.commit()
        return obj
