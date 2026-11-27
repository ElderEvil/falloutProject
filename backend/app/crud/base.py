from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy import Row, RowMapping
from sqlalchemy.exc import IntegrityError
from sqlmodel import SQLModel, col, func, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.utils.exceptions import ResourceAlreadyExistsException, ResourceNotFoundException, ensure_found


class CRUDBase[ModelType: SQLModel, CreateSchemaType: (SQLModel | None), UpdateSchemaType: (SQLModel | None)]:
    """Base CRUD operations for a SQLModel type."""

    def __init__(self, model: type[ModelType]):
        self.model = model

    async def get(self, db_session: AsyncSession, id: int | UUID, include_deleted: bool = False) -> ModelType:
        """Get one item by ID; raises ResourceNotFoundException when absent. Soft-deleted rows are
        excluded unless include_deleted (models without is_deleted are unaffected).
        """
        query = select(self.model).where(self.model.id == id)

        if not include_deleted and hasattr(self.model, "is_deleted"):
            query = query.where(~col(self.model.is_deleted))

        response = await db_session.execute(query)
        db_obj = response.scalar_one_or_none()
        return ensure_found(db_obj, self.model, identifier=id)

    async def get_or_none(
        self, db_session: AsyncSession, id: int | UUID, include_deleted: bool = False
    ) -> ModelType | None:
        """Same as get() but returns None instead of raising when the row is absent."""
        query = select(self.model).where(self.model.id == id)

        if not include_deleted and hasattr(self.model, "is_deleted"):
            query = query.where(~col(self.model.is_deleted))

        response = await db_session.execute(query)
        return response.scalar_one_or_none()

    async def get_by_ids(
        self, list_ids: Sequence[UUID | str], db_session: AsyncSession, include_deleted: bool = False
    ) -> Sequence[ModelType]:
        query = select(self.model).where(self.model.id.in_(list_ids))

        if not include_deleted and hasattr(self.model, "is_deleted"):
            query = query.where(~col(self.model.is_deleted))

        response = await db_session.execute(query)
        return response.scalars().all()

    async def get_multi(
        self, db_session: AsyncSession, skip: int = 0, limit: int = 100, include_deleted: bool = False
    ) -> Sequence[ModelType]:
        """List items ordered by ID with skip/limit pagination."""
        query = select(self.model).offset(skip).limit(limit).order_by(self.model.id)

        if not include_deleted and hasattr(self.model, "is_deleted"):
            query = query.where(~col(self.model.is_deleted))

        response = await db_session.execute(query)
        return response.scalars().all()

    async def create(self, db_session: AsyncSession, obj_in: CreateSchemaType, *, commit: bool = True) -> ModelType:
        """Create a new item; raises ResourceAlreadyExistsException on unique-violation.

        commit=False gives the caller the transaction: the row is flushed and a conflict
        propagated, so keep earlier writes by opening a savepoint first.
        """
        db_obj = self.model.model_validate(obj_in)
        try:
            db_session.add(db_obj)
            if commit:
                await db_session.commit()
            else:
                await db_session.flush()
        except IntegrityError as e:
            if commit:
                # Standalone semantics: undo our own work before surfacing the conflict.
                await db_session.rollback()
            identifier = getattr(obj_in, "name", self.model.__name__)
            raise ResourceAlreadyExistsException(self.model, identifier, headers={"detail": str(e)}) from e
        if not commit:
            # The caller owns the transaction; flush already populated defaults.
            return db_obj
        await db_session.refresh(db_obj)
        return db_obj

    async def create_all(self, db_session: AsyncSession, objs_in: Sequence[CreateSchemaType]) -> Sequence[ModelType]:
        """Create multiple items; raises ResourceAlreadyExistsException if any already exists."""
        db_objs = [self.model.model_validate(obj_in) for obj_in in objs_in]
        try:
            db_session.add_all(db_objs)
            await db_session.commit()
        except IntegrityError as e:
            await db_session.rollback()
            identifier = getattr(objs_in[0], "name", self.model.__name__)
            raise ResourceAlreadyExistsException(self.model, identifier, headers={"detail": str(e)}) from e
        return db_objs

    async def update(
        self,
        db_session: AsyncSession,
        id: int | UUID,
        obj_in: UpdateSchemaType | dict[str, Any],
        *,
        commit: bool = True,
    ) -> ModelType:
        db_obj = await self.get(db_session=db_session, id=id)
        update_data = obj_in if isinstance(obj_in, dict) else obj_in.model_dump(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db_session.add(db_obj)
        if commit:
            await db_session.commit()
        else:
            # With commit=False the caller batches more writes into one transaction; flush now so refresh() (and later
            # commits) see the pending changes even under autoflush=False sessions.
            await db_session.flush()
        await db_session.refresh(db_obj)
        return db_obj

    async def upsert(
        self, db_session: AsyncSession, obj_in: CreateSchemaType | UpdateSchemaType, id: int | UUID | None = None
    ) -> ModelType:
        """Insert or update an item based on its ID."""
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
        query = select(func.count()).select_from(self.model).filter_by(**filters)
        result = await db_session.execute(query)
        return result.scalar() > 0

    async def delete(
        self, db_session: AsyncSession, id: int | UUID, soft: bool = True, *, commit: bool = True
    ) -> ModelType:
        """Remove an object by ID; soft delete when soft=True and the model supports it, otherwise
        hard delete. Raises when the object is missing.
        """
        response = await db_session.execute(select(self.model).where(self.model.id == id))
        obj = response.scalar_one_or_none()
        obj = ensure_found(obj, self.model, identifier=id)

        if soft and hasattr(obj, "soft_delete"):
            obj.soft_delete()
            db_session.add(obj)
            if commit:
                await db_session.commit()
                await db_session.refresh(obj)
            else:
                await db_session.flush()
        else:
            await db_session.delete(obj)
            if commit:
                await db_session.commit()
            else:
                await db_session.flush()

        return obj

    async def soft_delete(self, db_session: AsyncSession, id: int | UUID, *, commit: bool = True) -> ModelType:
        """Soft delete an object by ID; raises ResourceNotFoundException when missing and
        AttributeError when the model lacks soft-delete support.
        """
        obj = await self.get(db_session=db_session, id=id, include_deleted=False)

        if not hasattr(obj, "soft_delete"):
            raise AttributeError(f"{self.model.__name__} does not support soft delete")

        obj.soft_delete()
        db_session.add(obj)
        if commit:
            await db_session.commit()
            await db_session.refresh(obj)
        else:
            await db_session.flush()
        return obj

    async def restore(self, db_session: AsyncSession, id: int | UUID, *, commit: bool = True) -> ModelType:
        """Restore a soft-deleted object by ID; raises ResourceNotFoundException when missing and
        AttributeError when the model lacks soft-delete support.
        """
        obj = await self.get(db_session=db_session, id=id, include_deleted=True)

        if not hasattr(obj, "restore"):
            raise AttributeError(f"{self.model.__name__} does not support soft delete")

        obj.restore()
        db_session.add(obj)
        if commit:
            await db_session.commit()
            await db_session.refresh(obj)
        else:
            await db_session.flush()
        return obj

    async def get_deleted(
        self, db_session: AsyncSession, skip: int = 0, limit: int = 100
    ) -> Sequence[Row[Any] | RowMapping | Any]:
        if not hasattr(self.model, "is_deleted"):
            return []

        query = (
            select(self.model)
            .where(col(self.model.is_deleted))
            .offset(skip)
            .limit(limit)
            .order_by(col(self.model.deleted_at).desc())
        )
        response = await db_session.execute(query)
        return response.scalars().all()
