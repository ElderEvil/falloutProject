from typing import Type

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.crud.base import ModelType, CRUDBase, CreateSchemaType, UpdateSchemaType


class CRUDRouterBase:
    """
    Base class for CRUD (Create, Read, Update, Delete) operations on a SQLModel in a database session.
    """

    def __init__(
            self,
            model: Type[ModelType],
            create_schema: Type[CreateSchemaType],
            update_schema: Type[UpdateSchemaType],
            prefix: str,
            tags: list[str] | None = None
    ):
        """
        Initializes a new instance of the `CRUDRouterBase` class.

        :param model: A SQLModel type that represents the database table to perform CRUD operations on.
        :param prefix: The prefix to use for all routes in this router.
        """
        self.model = model
        self.crud = CRUDBase(model)
        self.create_schema = create_schema
        self.update_schema = update_schema
        self.prefix = prefix
        self.tags = tags

    def get_router(self) -> APIRouter:
        """
        Creates a new instance of `APIRouter` with all CRUD routes for this model.

        :returns: A new `APIRouter` instance.
        """

        router = APIRouter(prefix=self.prefix, tags=self.tags)

        @router.get("/", response_model=list[self.model])
        def read_multi(skip: int = 0, limit: int = 100, db: Session = Depends()):
            items = self.crud.get_multi(db, skip=skip, limit=limit)
            return items

        @router.get("/{item_id}", response_model=self.model)
        def read(item_id: int, db: Session = Depends()):
            item = self.crud.get(db, item_id)
            return item

        @router.post("/", response_model=self.model)
        def create(*, db: Session = Depends(), item_in: self.create_schema):
            item = self.crud.create(db, item_in)
            return item

        @router.put("/{item_id}", response_model=self.model)
        def update(*, db: Session = Depends(), item_id: int, item_in: self.update_schema):
            item = self.crud.get(db, item_id)
            return item

        @router.delete("/{item_id}", response_model=self.model)
        def delete(*, db: Session = Depends(), item_id: int):
            item = self.crud.remove(db, item_id)
            return item

        return router
