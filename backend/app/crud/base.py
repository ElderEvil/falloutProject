from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from pydantic import UUID4
from sqlalchemy import Row, RowMapping
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.utils.exceptions import ResourceAlreadyExistsException, ResourceNotFoundException

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=SQLModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=SQLModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):  # noqa: UP046
    """
    Base class for CRUD (Create, Read, Update, Delete) operations on a SQLModel in a database session.

    :param model: A SQLModel type that represents the database table to perform CRUD operations on.
    """

    def __init__(self, model: type[ModelType]):
        self.model = model

    async def get(self, db_session: AsyncSession, id: int | UUID4) -> ModelType:
        """
        Gets a single item of the specified model type by ID.

        :param db_session: A database session.
        :param id: The ID of an object to retrieve.
        :returns: The retrieved item or `None` if it does not exist.
        :raises ResourceNotFoundException: If the item does not exist.
        """
        query = select(self.model).where(self.model.id == id)
        response = await db_session.execute(query)
        db_obj = response.scalar_one_or_none()
        if db_obj is None:
            raise ResourceNotFoundException(self.model, identifier=id)
        return db_obj

    async def get_by_ids(
        self, list_ids: list[UUID4 | str], db_session: AsyncSession
    ) -> Sequence[Row[Any] | RowMapping | Any]:
        """
        Gets a list of items of the specified model type by a list of IDs.

        :param list_ids: A list of IDs of objects to retrieve.
        :param db_session: A database session.
        :returns: list of items
        """
        response = await db_session.execute(select(self.model).where(self.model.id.in_(list_ids)))
        return response.scalars().all()

    async def get_count(self, db_session: AsyncSession) -> ModelType:
        """
        Gets the number of items of the specified model type in the database.

        :param db_session: A database session.
        :returns: The number of items.
        """
        response = await db_session.execute(select(func.count()).select_from(select(self.model).subquery()))
        return response.scalar_one()

    async def get_multi(
        self, db_session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Sequence[Row[Any] | RowMapping | Any]:
        """
        Gets a list of items of the specified model type, optionally skipping the first `skip` items and limiting the
        result to `limit` items.

        :param db_session: A database session.
        :param skip: The number of items to skip before returning results.
        :param limit: The maximum number of items to return.
        :returns: A list of retrieved items.
        """
        query = select(self.model).offset(skip).limit(limit).order_by(self.model.id)
        response = await db_session.execute(query)
        return response.scalars().all()

    async def create(self, db_session: AsyncSession, obj_in: CreateSchemaType) -> ModelType:
        """
        Creates a new item of the specified model type in the database.

        :param db_session: A database session.
        :param obj_in: The item to create.
        :returns: The created object, with any auto-generated fields populated by the database.
        :raises NameExistException: If the item already exists.
        """
        db_obj = self.model.model_validate(obj_in)
        try:
            db_session.add(db_obj)
            await db_session.commit()
        except IntegrityError as e:
            await db_session.rollback()
            raise ResourceAlreadyExistsException(self.model, obj_in.name, headers={"detail": str(e)}) from e
        await db_session.refresh(db_obj)
        return db_obj

    async def create_all(self, db_session: AsyncSession, objs_in: Sequence[CreateSchemaType]) -> Sequence[ModelType]:
        """
        Creates a list of new items of the specified model type in the database.

        :param db_session: A database session.
        :param objs_in: A list of items to create.
        :returns: The created objects, with any auto-generated fields populated by the database.
        :raises NameExistException: If any item already exists.
        """
        db_objs = [self.model.model_validate(obj_in) for obj_in in objs_in]
        try:
            db_session.add_all(db_objs)
            await db_session.commit()
        except IntegrityError as e:
            await db_session.rollback()
            raise ResourceAlreadyExistsException(self.model, objs_in[0].name, headers={"detail": str(e)}) from e
        return db_objs

    async def update(
        self,
        db_session: AsyncSession,
        id: int | UUID4,
        obj_in: UpdateSchemaType | dict[str, Any],
    ) -> ModelType:
        """
        Updates an existing item of the specified model type in the database.

        :param db_session: A database session.
        :param id: The ID of the object to update.
        :param obj_in: A new version of an object to update to, either as a SQLModel instance or a dictionary.
        :returns: The updated item, with any changes persisted to the database.
        """
        db_obj = await self.get(db_session=db_session, id=id)
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db_session.add(db_obj)
        await db_session.commit()
        await db_session.refresh(db_obj)
        return db_obj

    async def upsert(
        self, db_session: AsyncSession, obj_in: CreateSchemaType | UpdateSchemaType, id: int | UUID4 = None
    ) -> ModelType:
        """
        Inserts a new item or updates an existing one based on its ID.

        :param db_session: A database session.
        :param obj_in: The object to create or update.
        :param id: The ID to check if the object exists.
        :returns: The created or updated item.
        """
        if id:
            try:
                existing_obj = await self.get(db_session, id)
                update_data = obj_in.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    setattr(existing_obj, field, value)
                db_session.add(existing_obj)
            except ResourceNotFoundException:
                existing_obj = self.model.model_validate(obj_in)
                db_session.add(existing_obj)
        else:
            existing_obj = self.model.model_validate(obj_in)
            db_session.add(existing_obj)

        await db_session.commit()
        await db_session.refresh(existing_obj)
        return existing_obj

    async def exists(self, db_session: AsyncSession, **filters: Any) -> bool:
        """
        Checks if any record exists matching the given filters.

        :param db_session: A database session.
        :param filters: Key-value pairs to filter the records.
        :returns: True if a record exists, otherwise False.
        """
        query = select(func.count()).select_from(self.model).filter_by(**filters)
        result = await db_session.execute(query)
        return result.scalar() > 0

    async def delete(self, db_session: AsyncSession, id: int | UUID4) -> ModelType:
        """
        Remove a database object with the given ID.

        If the object exists, it is deleted from the database and returned.
        If the object does not exist, error is raised.

        :param db_session: A database session
        :param id: ID of the object to remove
        :returns: the removed object, or None if it does not exist
        :raises IDNotFoundException: if there is an error finding object in database
        """
        response = await db_session.execute(select(self.model).where(self.model.id == id))
        obj = response.scalar_one()
        if not obj:
            raise ResourceNotFoundException(self.model, identifier=id)
        await db_session.delete(obj)
        await db_session.commit()
        return obj
