from typing import Any, Generic, TypeVar

from fastapi import HTTPException
from pydantic import UUID4
from sqlmodel import Session, SQLModel, select

ModelType = TypeVar("ModelType", bound=SQLModel)
CreateSchemaType = TypeVar("CreateSchemaType", bound=SQLModel)
UpdateSchemaType = TypeVar("UpdateSchemaType", bound=SQLModel)


class CRUDBase(Generic[ModelType, CreateSchemaType, UpdateSchemaType]):
    """
    Base class for CRUD (Create, Read, Update, Delete) operations on a SQLModel in a database session.

    :param model: A SQLModel type that represents the database table to perform CRUD operations on.
    """

    def __init__(self, model: type[ModelType]):
        """
        Initializes a new instance of the `CRUDBase` class.

        :param model: A SQLModel type that represents the database table to perform CRUD operations on.
        """
        self.model = model

    def get(self, db: Session, id: int | UUID4) -> ModelType | None:
        """
        Gets a single item of the specified model type by ID.

        :param db: A database session.
        :param id: The ID of an object to retrieve.
        :returns: The retrieved item or `None` if it does not exist.
        """
        return db.get(self.model, id)

    def get_by_name(self, db: Session, name: str) -> ModelType | None:
        """
        Gets a single item of the specified model type by name.

        :param db: A database session.
        :param name: The name of an object to retrieve.
        :returns: The retrieved item.
        :raises HTTPException: if there is an error accessing the database or object doesn't exist
        """
        result = db.exec(select(self.model).where(self.model.name == name)).first()
        if not result:
            raise HTTPException(status_code=404, detail=f"{self.model.__name__} not found")
        return result

    def get_multi(self, db: Session, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """
        Gets a list of items of the specified model type, optionally skipping the first `skip` items and limiting the
        result to `limit` items.

        :param db: A database session.
        :param skip: The number of items to skip before returning results.
        :param limit: The maximum number of items to return.
        :returns: A list of retrieved items.
        """
        return db.exec(select(self.model).offset(skip).limit(limit)).all()

    def create(self, db: Session, obj_in: CreateSchemaType) -> ModelType:
        """
        Creates a new item of the specified model type in the database.

        :param db: A database session.
        :param obj_in: The item to create.
        :returns: The created object, with any auto-generated fields populated by the database.
        """
        db_obj = self.model.from_orm(obj_in)
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def update(self, db: Session, id: int | UUID4, obj_in: UpdateSchemaType | dict[str, Any]) -> ModelType:
        """
        Updates an existing item of the specified model type in the database.

        :param db: A database session.
        :param id: The ID of the object to update.
        :param obj_in: A new version of an object to update to, either as a SQLModel instance or a dictionary.
        :returns: The updated item, with any changes persisted to the database.
        """
        db_obj = self.get(db=db, id=id)
        if db_obj is None:
            raise HTTPException(status_code=404, detail=f"{self.model.__name__} not found")

        update_data = obj_in if isinstance(obj_in, dict) else obj_in.dict(exclude_unset=True)

        for field, value in update_data.items():
            setattr(db_obj, field, value)

        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj

    def delete(self, db: Session, id: int | UUID4) -> ModelType:
        """
        Remove a database object with the given ID.

        If the object exists, it is deleted from the database and returned.
        If the object does not exist, None is returned instead.

        :param db: A database session
        :param id: ID of the object to remove
        :return: the removed object, or None if it does not exist
        :raises HTTPException: if there is an error finding object in database
        """
        obj = db.get(self.model, id)
        if not obj:
            raise HTTPException(status_code=404, detail=f"{self.model.__name__} not found")
        db.delete(obj)
        db.commit()
        return obj
