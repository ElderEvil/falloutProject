# https://github.com/pydantic/pydantic/issues/1223
# https://github.com/pydantic/pydantic/pull/3179
# https://github.com/pydantic/pydantic/issues/1673

from collections.abc import Callable
from copy import deepcopy
from typing import Any, TypeVar, cast

from pydantic import BaseModel, create_model
from pydantic.fields import FieldInfo

Model = TypeVar("Model", bound=type[BaseModel])


def optional(without_fields: list[str] | None = None) -> Callable[[Model], Model]:
    """A decorator that create a partial model.

    params: without_fields: list[str] | None: List of fields to exclude from the model.
    return: type[BaseModel]: ModelBase partial model.
    """
    excluded = without_fields or []

    def wrapper(model: Model) -> Model:
        def make_field_optional(field: FieldInfo, default: Any = None) -> tuple[Any, FieldInfo]:
            new = deepcopy(field)
            new.default = default
            new.default_factory = None  # Pydantic rejects a factory alongside a None default.
            new.annotation = cast("Any", field.annotation) | None
            return new.annotation, new

        field_definitions: dict[str, Any] = {
            name: make_field_optional(info) for name, info in model.model_fields.items() if name not in excluded
        }
        base: type[BaseModel] = BaseModel if excluded else model
        return cast(
            "Model",
            create_model(model.__name__, __base__=base, __module__=model.__module__, **field_definitions),
        )

    return wrapper
