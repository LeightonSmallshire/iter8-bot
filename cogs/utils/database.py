import aiosqlite
import datetime
import aiosqlite
import asyncio
from .model import *
from dataclasses import dataclass, fields, asdict, Field
from typing import Optional, Any, Type, TypeVar, get_type_hints, Protocol, TypeVar, Type, Mapping, Protocol, ClassVar

@dataclass
class WhereParam:
    field: str
    value: Any
    
@dataclass
class OrderParam:
    field: str
    descending: bool

# --- core ORM ---
class Database:
    def __init__(self, path: str):
        self.path = path
        
    async def close(self) -> None:
        await self.con.close()

    async def commit(self) -> None:
        await self.con.commit()

    async def __aenter__(self):
        self.con = await aiosqlite.connect(self.path)
        self.con.row_factory = aiosqlite.Row
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if exc_type:
            try: await self.con.rollback()
            except aiosqlite.Error: pass
        else:
            try: await self.con.commit()
            except aiosqlite.Error: pass
        await self.con.close()

    async def drop_table(self, model: Type[T]) -> None:
         sql = f"DROP TABLE IF EXISTS {python_to_table_name(model)}"
         await self.con.execute(sql)

    async def create_table(self, model: Type[T]) -> None:
        cols = []
        hints = get_type_hints(model)
        for f in fields(model):
            meta = f.metadata
            sql_type = python_to_sql_type(hints[f.name])
            col_def = f"{f.name} {sql_type}"
            if f.name == "id":
                col_def += " PRIMARY KEY"
                
            if "fk" in meta:
                fk = meta["fk"]
                fk_table = fk["table"]
                fk_field = fk.get("column", "id")
                col_def += f" REFERENCES {fk_table}({fk_field})"

            cols.append(col_def)
            
        sql = f"CREATE TABLE IF NOT EXISTS {python_to_table_name(model)} ({', '.join(cols)})"
        await self.con.execute(sql)

    async def insert(self, obj: T) -> int:
        data = asdict(obj)

        # Treat missing/None/0 as "no id provided"
        unset = ("id" not in data) or (data.get("id") is None) or (data.get("id") == 0)
        if unset and "id" in data:
            data.pop("id")

        keys = ", ".join(data.keys())
        qs = ", ".join("?" for _ in data)
        sql = f"INSERT INTO {python_to_table_name(type(obj))} ({keys}) VALUES ({qs})"
        cur = await self.con.execute(sql, tuple(data.values()))

        # If id was auto-generated, propagate it to the object and return it
        if unset:
            new_id = cur.lastrowid
            try:
                setattr(obj, "id", new_id)
            except Exception:
                pass
            return new_id # type: ignore[return-value]
        
        return data.get("id") # type: ignore[return-value]


    async def select(self, model: Type[T], params: list[WhereParam] = [], order: list[OrderParam] = [], limit: Optional[int] = None) -> list[T]:
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

        cur = await self.con.execute(sql, [p.value for p in params])
        results = await cur.fetchmany(limit) if limit else await cur.fetchall()
        return [model(**dict(row)) for row in results]

    async def update(self, obj: T, where: str, params: tuple[Any]) -> None:
        data = asdict(obj)
        assigns = ", ".join(f"{k}=?" for k in data.keys())
        sql = f"UPDATE {python_to_table_name(type(obj))} SET {assigns} WHERE {where}"
        await self.con.execute(sql, tuple(data.values()) + params)

    async def delete(self, model: Type[T], where: str, params: tuple[Any]) -> None:
        sql = f"DELETE FROM {python_to_table_name(model)} WHERE {where}"
        await self.con.execute(sql, params)


DATABASE_NAME = "data/storage.db"

async def init_database(timeout_data: list[Timeout]):
    async with Database(DATABASE_NAME) as db:
        await db.drop_table(Timeout)
        await db.create_table(Timeout)

        await db.drop_table(Log)
        await db.create_table(Log)

        await db.drop_table(ShopItem)
        await db.create_table(ShopItem)
        
        await db.create_table(Purchase)
        
        for timeout in timeout_data:
            await db.insert(timeout)

        for item in PURCHASE_OPTIONS:
            await db.insert(item)

async def get_timeout_leaderboard() -> list[Timeout]:
    async with Database(DATABASE_NAME) as db:
        return await db.select(Timeout, order=[OrderParam("count", True), OrderParam("duration", True)])

async def update_timeout_leaderboard(user: int, duration: float):   
    async with Database(DATABASE_NAME) as db:
        timeouts_for_user = await db.select(Timeout, params=[WhereParam("id", user)])
        if (len(timeouts_for_user) > 0):
            timeout = timeouts_for_user[0]
            timeout.count += 1 if duration > 0 else 0
            timeout.duration += duration
            await db.update(timeout, "id=?", (user,))
        else:
            timeout = Timeout(user, 1 if duration > 0 else 0, duration)
            await db.insert(timeout)


async def write_log(level: str, message: str) -> None:
    async with Database(DATABASE_NAME) as db:
        log = Log(None, datetime.datetime.now(datetime.timezone.utc), level, message)
        await db.insert(log)

async def read_logs(limit: int=100, level: Optional[str]=None):
    async with Database(DATABASE_NAME) as db:
        logs = await db.select(Log, params=[WhereParam("level", level)], order=[OrderParam("id", True)], limit=limit)
        logs.reverse()
        return logs
    

async def get_shop_contents() -> list[ShopItem]:
    async with Database(DATABASE_NAME) as db:
        return await db.select(ShopItem)