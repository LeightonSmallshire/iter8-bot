import aiosqlite
import sqlite3
import datetime
from .model import *
from .bot import Users, filter_bots
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

def _alias_cols(cls: type, alias: str) -> list[str]:
    return [f'{alias}.{f.name} AS "{alias}.{f.name}"' for f in fields(cls)]

def _row_to(cls: type[T], row: aiosqlite.Row, alias: str) -> T:
    hints = get_type_hints(cls, include_extras=True)
    data = {f.name: row[f"{alias}.{f.name}"] for f in fields(cls)}
    return cls(**data)  # type: ignore[arg-type]

def _find_relationship(left: type, right: type) -> tuple[str, str, str]:
    """
    Returns (side_with_fk, fk_field, pk_field).
    side_with_fk is 'left' or 'right'.
    pk_field defaults to 'id' unless metadata overrides.
    """
    lt, rt = python_to_table_name(left), python_to_table_name(right)

    # left has FK → right
    for f in fields(left):
        fk = f.metadata.get("fk")
        if fk and fk["table"] == rt:
            return ("left", f.name, fk.get("column", "id"))

    # right has FK → left
    for f in fields(right):
        fk = f.metadata.get("fk")
        if fk and fk["table"] == lt:
            return ("right", f.name, fk.get("column", "id"))

    raise ValueError(f"No foreign-key relationship between {left.__name__} and {right.__name__}")

# --- core ORM ---
class Database:
    def __init__(self, path: str):
        self.path = path
        aiosqlite.register_adapter(datetime.datetime, lambda d: d.isoformat(timespec="seconds"))
        aiosqlite.register_converter("DATETIME", lambda b: datetime.datetime.fromisoformat(b.decode()))
        
    async def close(self) -> None:
        await self.con.close()

    async def commit(self) -> None:
        await self.con.commit()

    async def __aenter__(self):
        self.con = await aiosqlite.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
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

    async def drop_table_with_name(self, table: str) -> None:
        sql = f"DROP TABLE IF EXISTS {table}"
        await self.con.execute(sql)

    async def drop_table(self, model: Type[T]) -> None:
        await self.drop_table_with_name(python_to_table_name(model))

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


    async def select(self, model: Type[T], where: list[WhereParam] = [], order: list[OrderParam] = [], limit: Optional[int] = None) -> list[T]:
        # validate column name
        valid_fields = {f.name for f in fields(model)}

        sql = f"SELECT * FROM {python_to_table_name(model)}"

        for idx, param in enumerate(where):
            if param.field not in valid_fields:
                raise ValueError(f"{param.field!r} is not a field of {model.__name__}")
            
            sql += " AND " if idx > 0 else " WHERE "
            sql += f"{param.field} = ?"          

        for idx, param in enumerate(order):
            sql += " ORDER BY " if idx == 0 else ", "
            sql += f"{param.field} {'DESC' if param.descending else ''}"

        cur = await self.con.execute(sql, [p.value for p in where])
        results = await cur.fetchmany(limit) if limit else await cur.fetchall()
        return [model(**dict(row)) for row in results]

    async def update(self, obj: T, where: list[WhereParam] = []) -> None:
        data = asdict(obj)
        data = {k: v for k, v in data.items() if v is not None}

        assigns = ", ".join(f"{k}=?" for k in data.keys())
        sql = f"UPDATE {python_to_table_name(type(obj))} SET {assigns}"
        
        for idx, param in enumerate(where):            
            sql += " AND " if idx > 0 else " WHERE "
            sql += f"{param.field} = ?"        
            
        await self.con.execute(sql, list(data.values()) + [p.value for p in where])

    async def delete(self, model: Type[T], where: list[WhereParam] = []) -> None:
        sql = f"DELETE FROM {python_to_table_name(model)}"
        
        for idx, param in enumerate(where):            
            sql += " AND " if idx > 0 else " WHERE "
            sql += f"{param.field} = ?"       

        await self.con.execute(sql, [p.value for p in where])

    async def insert_or_update(self, obj: T, where: list[WhereParam] = []) -> int:
        """
        Insert a row. If a row with the same primary key exists, update it instead.
        Returns the object's id.
        """
        data = asdict(obj)
        table = python_to_table_name(type(obj))

        keys = list(data.keys())
        if "id" not in keys:
            raise ValueError("UPSERT requires 'id' primary key")

        non_id = [k for k in keys if k != "id"]
        columns = ", ".join(keys)
        placeholders = ", ".join("?" for _ in keys)

        # update to incoming values (excluded.*)
        set_clause = ", ".join(f"{k}=excluded.{k}" for k in non_id)

        where_sql = ""
        where_params: list[object] = []
        if where:
            where_sql = " WHERE " + " AND ".join(f"{p.field}=?" for p in where)
            where_params = [p.value for p in where]

        sql = (
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {set_clause}{where_sql}"
        )

        params = [data[k] for k in keys] + where_params
        cur = await self.con.execute(sql, params)
        # optional: await self.con.commit()
        return int(getattr(obj, "id"))


    async def join_select(
        self,
        left: Type[T],
        right: Type[U],
        where: list[WhereParam] = [],
        order: list[OrderParam] = [],
        limit: int | None = None,
    ) -> list[tuple[T, U]]:
        la, ra = "l", "r"
        lt, rt = python_to_table_name(left), python_to_table_name(right)

        # infer join
        side, fk_field, pk_field = _find_relationship(left, right)
        if side == "left":
            join_expr = f"{la}.{fk_field} = {ra}.{pk_field}"
        else:
            join_expr = f"{la}.{pk_field} = {ra}.{fk_field}"

        # alias-qualified columns
        select_cols = _alias_cols(left, la) + _alias_cols(right, ra)

        sql = [
            f"SELECT {', '.join(select_cols)}",
            f"FROM {lt} {la}",
            f"INNER JOIN {rt} {ra} ON {join_expr}",
        ]

        left_fields = {f.name for f in fields(left)}
        right_fields = {f.name for f in fields(right)}

        def qualify(name: str) -> str:
            # unqualified name → search both tables
            if "." in name:
                return name  # allow explicit l.field or r.field
            if name in left_fields:
                return f"{la}.{name}"
            if name in right_fields:
                return f"{ra}.{name}"
            raise ValueError(f"{name!r} is not a field of {left.__name__} or {right.__name__}")

        params: list[Any] = []

        if where:
            sql.append("WHERE")
            for i, p in enumerate(where):
                if i:
                    sql.append("AND")
                sql.append(f"{qualify(p.field)} = ?")
                params.append(p.value)

        if order:
            sql.append("ORDER BY")
            for i, p in enumerate(order):
                if i:
                    sql.append(", ")
                sql.append(f"{qualify(p.field)} {'DESC' if p.descending else 'ASC'}")

        if limit is not None:
            sql.append("LIMIT ?")
            params.append(limit)

        query = " ".join(sql)
        cur = await self.con.execute(query, params)
        rows = await cur.fetchall()

        out: list[tuple[T, U]] = []
        for row in rows:
            left_obj = _row_to(left, row, la)
            right_obj = _row_to(right, row, ra)
            out.append((left_obj, right_obj))
        return out



DATABASE_NAME = "data/storage.db"


#-----------------------------------------------------------------
#   Initialisation

async def init_database(timeout_data: list[User]):
    async with Database(DATABASE_NAME) as db:
        await db.drop_table(User)
        await db.create_table(User)

        await db.drop_table(Log)
        await db.create_table(Log)

        await db.drop_table(ShopItem)
        await db.create_table(ShopItem)
        
        await db.create_table(Purchase)
        
        await db.drop_table(PurchaseHandler)
        await db.create_table(PurchaseHandler)
        
        for timeout in timeout_data:
            await db.insert_or_update(timeout, where=[WhereParam("id", timeout.id)])

        for item in PURCHASE_OPTIONS:
            await db.insert(item)

        await db.insert(ChoiceHandlers.User)
        await db.insert(ChoiceHandlers.Duration)



#-----------------------------------------------------------------
#   Timeouts

async def get_timeout_leaderboard() -> list[User]:
    async with Database(DATABASE_NAME) as db:
        return await db.select(User, order=[OrderParam("count", True), OrderParam("duration", True)])

async def update_timeout_leaderboard(user: int, duration: float):   
    async with Database(DATABASE_NAME) as db:
        timeouts_for_user = await db.select(User, where=[WhereParam("id", user)])
        if (len(timeouts_for_user) > 0):
            timeout = timeouts_for_user[0]
            timeout.count += 1 if duration > 0 else 0
            timeout.duration += duration
            await db.update(timeout, [WhereParam("id", user)])
        else:
            timeout = User(user, 1 if duration > 0 else 0, duration)
            await db.insert(timeout)


async def erase_timeout_user(user: int):
    async with Database(DATABASE_NAME) as db:
        await db.delete(User, [WhereParam("id", user), ])


#-----------------------------------------------------------------
#   Logs

async def write_log(level: str, message: str) -> None:
    async with Database(DATABASE_NAME) as db:
        log = Log(None, datetime.datetime.now(datetime.timezone.utc), level, message)
        await db.insert(log)

async def read_logs(limit: int=100, level: Optional[str]=None):
    async with Database(DATABASE_NAME) as db:
        where = [WhereParam("level", level)] if level is not None else []
        logs = await db.select(Log, where=where, order=[OrderParam("id", True)], limit=limit)
        logs.reverse()
        return logs
    



#-----------------------------------------------------------------
#   Purchases

async def get_shop_contents() -> list[ShopItem]:
    async with Database(DATABASE_NAME) as db:
        return await db.select(ShopItem)
    

async def get_shop_credit(user_id: int) -> datetime.timedelta:
    async with Database(DATABASE_NAME) as db:
        user = await db.select(User, [WhereParam("id", user_id)])
        if not user:
            return datetime.timedelta(seconds=0)
        
        user = user[0]
        purchases = await db.select(Purchase, where=[WhereParam("user_id", user_id)])
        
        credit = user.duration - sum([p.cost for p in purchases])

        return datetime.timedelta(seconds=credit)
    
async def purchase(user_id: int, item: ShopItem, count: int = 1):
    async with Database(DATABASE_NAME) as db:
        for _ in range(count):
            await db.insert(Purchase(None, item.id, item.cost, user_id, item.auto_use))

async def get_handlers(item_id: int) -> list[str]:
    async with Database(DATABASE_NAME) as db:
        items = await db.select(ShopItem, where=[WhereParam("id", item_id)], limit=1)
        if not items:
            return []
        
        item = items[0]
        handlers = await db.select(PurchaseHandler)
        return [h.handler for h in handlers if item.handlers & h.id]
    

async def can_afford_purchase(user: int, cost: int) -> bool:
    async with Database(DATABASE_NAME) as db:
        credit = await get_shop_credit(user)
        credit = credit.total_seconds()

        return cost <= credit




#-----------------------------------------------------------------
#   Admin Roll

async def get_admin_roll_table() -> list[int]:
    async with Database(DATABASE_NAME) as db:
        users = await db.select(User)
        bonus_tickets = await db.select(Purchase, where=[WhereParam("item_id", ShopOptions.AdminTicket.id), WhereParam("used", False)])
        await db.update(Purchase(None, None, None, None, True), where=[WhereParam("item_id", ShopOptions.AdminTicket.id)])

        return [u.id for u in users] + [t.user_id for t in bonus_tickets]
    
async def use_admin_reroll_token(user: int) -> bool:
    async with Database(DATABASE_NAME) as db:
        tokens = await db.select(Purchase, where=[WhereParam("item_id", ShopOptions.AdminReroll.id), WhereParam("used", False)])
        if not tokens:
            return False
        
        token = tokens[0]
        await db.update(Purchase(None, None, None, None, True), where=[WhereParam("id", token.id)])

        return True