import datetime
import re
from packaging.version import Version
from dataclasses import dataclass, field, fields, asdict, Field
from typing import Optional, Any, Type, TypeVar, get_type_hints, Protocol, TypeVar, Type, Mapping, Protocol, ClassVar, Literal


# --- type mapping ---
TYPE_MAP = {
    int: "INTEGER",
    datetime.datetime: "DATETIME",
    datetime.time: "REAL",
    float: "REAL",
    str: "TEXT",
    bytes: "BLOB",
    bool: "BOOLEAN",
    Version: "VERSION"
}

def single_value_table(cls):
    setattr(cls, "__single_value_table__", True)
    return cls

# --- A dataclass type that has an int id ---
class HasIdTable(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]
    id: int

# --- A dataclass type marked as single-value ---
class SingleValueTable(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]
    __single_value_table__: ClassVar[Literal[True]]

# --- Either one is acceptable ---
IsDatabaseTable = HasIdTable | SingleValueTable

T = TypeVar("T", bound=IsDatabaseTable)
U = TypeVar("U", bound=IsDatabaseTable)

def python_to_sql_type(py_type: Any) -> str:
    return TYPE_MAP.get(py_type, "TEXT")

def python_to_table_name(model: Type[T]) -> str:
    def pascal_to_snake(name: str) -> str:
        return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()
    return f"{pascal_to_snake(model.__name__)}{'' if getattr(model, '__single_value_table__', False) is True else 's'}"


def assert_field_exists(model: Type[Any], name: str) -> None:
    if name not in {f.name for f in fields(model)}:
        valid = ", ".join(f.name for f in fields(model))
        raise ValueError(f"{name!r} not in {model.__name__} fields: {valid}")

def foreign_key(model: Type[Any], column: str = "id", **extra):
    assert_field_exists(model, column)
    return field(metadata={
        "fk": {
            "table": python_to_table_name(model),
            "column": column
        },
        **extra
    })


@dataclass
class User:
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
class Purchase:
    id: int
    item_id: int
    cost: int
    user_id: int = foreign_key(User)
    used: bool = False

@dataclass
class AdminBet:
    id: int
    amount: float
    gamble_user_id: int = foreign_key(User)
    bet_user_id: int = foreign_key(User)
    used: bool = False

@dataclass
class GambleWin:
    id: int
    amount: float
    user_id: int = foreign_key(User)

@single_value_table
@dataclass
class AdminRollInfo:
    last_roll: datetime.datetime

@single_value_table
@dataclass
class DatabaseVersion:
    version: Version