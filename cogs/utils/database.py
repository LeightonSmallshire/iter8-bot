import sqlite3
import datetime
from .model import Timeout, Log
from dataclasses import dataclass, fields, asdict, Field
from typing import Optional, Any, Type, TypeVar, get_type_hints, Protocol, TypeVar, Type, Mapping, Protocol, ClassVar

# Combined: a dataclass TYPE whose instances have id:int
class HasIdDataclass(Protocol):
    __dataclass_fields__: ClassVar[dict[str, Any]]
    id: int # required field

T = TypeVar("T", bound=HasIdDataclass)

@dataclass
class WhereParam:
    field: str
    value: Any
    
@dataclass
class OrderParam:
    field: str
    descending: bool

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

def python_to_sql_type(py_type: Any) -> str:
    return TYPE_MAP.get(py_type, "TEXT")

def python_to_table_name(model: Type[T]) -> str:
    return f"{model.__name__.lower()}s"

# --- core ORM ---
class Database:
    def __init__(self, path: str):
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        
    def close(self) -> None:
        self.con.close()

    def commit(self) -> None:
        self.con.commit()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            try: self.con.rollback()
            except sqlite3.Error: pass
        else:
            try: self.con.commit()
            except sqlite3.Error: pass
        self.con.close()

    def drop_table(self, model: Type[T]) -> None:
         sql = f"DROP TABLE IF EXISTS {python_to_table_name(model)}"
         self.con.execute(sql)

    def create_table(self, model: Type[T]) -> None:
        cols = []
        hints = get_type_hints(model)
        for f in fields(model):
            sql_type = python_to_sql_type(hints[f.name])
            col_def = f"{f.name} {sql_type}"
            if f.name == "id":
                col_def += " PRIMARY KEY"
            cols.append(col_def)
            
        sql = f"CREATE TABLE IF NOT EXISTS {python_to_table_name(model)} ({', '.join(cols)})"
        self.con.execute(sql)

    def insert(self, obj: T) -> int:
        data = asdict(obj)

        # Treat missing/None/0 as "no id provided"
        unset = ("id" not in data) or (data.get("id") is None) or (data.get("id") == 0)
        if unset and "id" in data:
            data.pop("id")

        keys = ", ".join(data.keys())
        qs = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {python_to_table_name(type(obj))} ({keys}) VALUES ({qs})"
        cur = self.con.execute(sql, tuple(data.values()))

        # If id was auto-generated, propagate it to the object and return it
        if unset:
            new_id = cur.lastrowid
            try:
                setattr(obj, "id", new_id)
            except Exception:
                pass
            return new_id # type: ignore[return-value]
        
        return data.get("id") # type: ignore[return-value]


    def select(self, model: Type[T], params: list[WhereParam] = [], order: list[OrderParam] = [], limit: Optional[int] = None) -> list[T]:
        # validate column name
        valid_fields = {f.name for f in fields(model)}

        sql = f"SELECT * FROM {python_to_table_name(model)}"

        for idx, param in enumerate(params):
            if param.field not in valid_fields:
                raise ValueError(f"{param.field!r} is not a field of {model.__name__}")
            
            sql += " AND " if idx > 0 else " WHERE "
            sql += f"{param.field} = ?"          

    

        for idx, param in enumerate(order):
            sql += " ORDER BY " if idx == 0 else ", "
            sql += f"{param.field} {"DESC" if param.descending else ""}"

        cur = self.con.execute(sql, [p.value for p in params])
        results = cur.fetchmany(limit) if limit else cur.fetchall()
        return [model(**dict(row)) for row in results]

    def update(self, obj: T, where: str, params: tuple[Any]) -> None:
        data = asdict(obj)
        assigns = ", ".join(f"{k}=?" for k in data.keys())
        sql = f"UPDATE {python_to_table_name(type(obj))} SET {assigns} WHERE {where}"
        self.con.execute(sql, tuple(data.values()) + params)

    def delete(self, model: Type[T], where: str, params: tuple[Any]) -> None:
        sql = f"DELETE FROM {python_to_table_name(model)} WHERE {where}"
        self.con.execute(sql, params)


DATABASE_NAME = "data/storage.db"


def init_database(timeout_data: list[Timeout]):
    with Database(DATABASE_NAME) as db:
        db.drop_table(Timeout)
        db.create_table(Timeout)

        db.drop_table(Log)
        db.create_table(Log)
        
        for timeout in timeout_data:
            db.insert(timeout)

def get_timeout_leaderboard() -> list[Timeout]:
    with Database(DATABASE_NAME) as db:
        return db.select(Timeout, order=[OrderParam("count", True), OrderParam("duration", True)])

def update_timeout_leaderboard(user: int, duration: float):
    with Database(DATABASE_NAME) as db:
        timeouts_for_user = db.select(Timeout, params=[WhereParam("id", user)])
        if (len(timeouts_for_user) > 0):
            timeout = timeouts_for_user[0]
            timeout.count += 1 if duration > 0 else 0
            timeout.duration += duration
            db.update(timeout, "id=?", (user,))
        else:
            timeout = Timeout(user, 1 if duration > 0 else 0, duration)
            db.insert(timeout)


def write_log(level: str, message: str) -> None:
    with Database(DATABASE_NAME) as db:
        log = Log(None, datetime.datetime.now(datetime.timezone.utc), level, message)
        db.insert(log)

def read_logs(limit: int=100, level: Optional[str]=None):
    with Database(DATABASE_NAME) as db:
        logs = db.select(Log, params=[WhereParam("level", level)], order=[OrderParam("id", True)], limit=limit)
        logs.reverse()
        return logs