import datetime
import re
from dataclasses import dataclass, field, fields, asdict, Field
from typing import Optional, Any, Type, TypeVar, get_type_hints, Protocol, TypeVar, Type, Mapping, Protocol, ClassVar


# --- type mapping ---
TYPE_MAP = {
    int: "INTEGER",
    datetime.datetime: "DATETIME",
    datetime.time: "REAL",
    float: "REAL",
    str: "TEXT",
    bytes: "BLOB",
    bool: "INTEGER",
}

# Combined: a dataclass TYPE whose instances have id:int
class HasIdDataclass(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]
    id: int # required field

T = TypeVar("T", bound=HasIdDataclass)

def python_to_sql_type(py_type: Any) -> str:
    return TYPE_MAP.get(py_type, "TEXT")

def python_to_table_name(model: Type[T]) -> str:
    def pascal_to_snake(name: str) -> str:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    return f"{pascal_to_snake(model.__name__)}s"


def assert_field_exists(model: Type[Any], name: str) -> None:
    if name not in {f.name for f in fields(model)}:
        valid = ", ".join(f.name for f in fields(model))
        raise ValueError(f"{name!r} not in {model.__name__} fields: {valid}")

def ForeignKey(model: Type[Any], column: str = "id", **extra):
    assert_field_exists(model, column)
    return field(metadata={
        "fk": {
            "table": python_to_table_name(model),
            "column": column
        },
        **extra
    })





@dataclass
class Timeout:
    id: int
    count: int
    duration: float

@dataclass
class Log:
    id: int
    timestamp: datetime.datetime
    level: str
    message: str

@dataclass
class ShopItem:
    id: int
    cost: int
    description: str

@dataclass
class Purchase:
    id: int
    item_id: int = ForeignKey(ShopItem)




PURCHASE_OPTIONS = [
    ShopItem(0, 3600, "⏱️ Timeout admin"),
    ShopItem(0, 1800, "⏱️ Timeout a person"),
    ShopItem(0, 1800, "🎲 Reroll bully target"),
    ShopItem(0, 600, "⏱️ Timeout the bully target"),

    ShopItem(0, 18000, "👑 Make yourself admin"),
    ShopItem(0, 3600, "🎟️ Add an extra ticket in the admin dice roll"),
    ShopItem(0, 3600, "🎲 Reroll the admin dice roll"),
]