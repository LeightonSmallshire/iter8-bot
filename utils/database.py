import aiosqlite
import sqlite3
import datetime
import random
from packaging.version import Version
from .model import *
from .shop import *
from collections import defaultdict
from dataclasses import dataclass, fields, asdict, Field
from typing import Optional, Any, Type, get_type_hints, Type, get_origin, get_args

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

def _is_nullable(tp) -> bool:
    # Directly NoneType
    if tp is type(None):
        return True

    origin = get_origin(tp)
    if origin is None:
        return False

    # Union[...] or X | Y
    return type(None) in get_args(tp)

# --- core ORM ---
class Database:
    def __init__(self, path: str, defer_commit: bool = False):
        self.path = path
        self.defer_commit = defer_commit

        aiosqlite.register_adapter(datetime.datetime, lambda d: d.isoformat(timespec="seconds"))
        aiosqlite.register_converter("DATETIME", lambda b: datetime.datetime.fromisoformat(b.decode()))
        
        aiosqlite.register_adapter(Version, lambda v: v.__str__())
        aiosqlite.register_converter("VERSION", lambda v: Version(v.decode()))
        
        aiosqlite.register_adapter(bool, int)  # True->1, False->0
        aiosqlite.register_converter(
            "BOOLEAN", lambda b: b.strip().lower() in (b"1", b"t", b"true", b"y", b"yes")
)

    async def connect(self):
        self.con = await aiosqlite.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.con.row_factory = aiosqlite.Row
        return self
        
    async def commit(self) -> None:
        await self.con.commit()
        await self.con.close()

    async def rollback(self) -> None:
        await self.con.rollback()
        await self.con.close()

    async def __aenter__(self):
        self.con = await aiosqlite.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.con.row_factory = aiosqlite.Row
        return self

    async def __aexit__(self, exc_type, exc, tb):
        if self.defer_commit:
            return

        if exc_type:
            try: await self.con.rollback()
            except aiosqlite.Error: pass
        else:
            try: await self.con.commit()
            except aiosqlite.Error: pass
        await self.con.close()

    async def execute(self, query: str) -> aiosqlite.Cursor:
        return await self.con.execute(query)

    async def drop_table_with_name(self, table: str) -> None:
        sql = f"DROP TABLE IF EXISTS {table}"
        await self.con.execute(sql)

    async def drop_table(self, model: Type[T]) -> None:
        await self.drop_table_with_name(python_to_table_name(model))

    async def table_exists(self, table_name: str) -> bool:
        cur = await self.con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        return (await cur.fetchone()) is not None

    async def create_single_value_table(self, model: Type[T]):
        cols = []
        hints = get_type_hints(model)
        for f in fields(model):
            if f.name == "__single_value_table__":
                continue
            typename = hints[f.name]
            sql_type = python_to_sql_type(typename)
            cols.append(f"{f.name} {sql_type}{'' if _is_nullable(typename) else ' NOT NULL'}")
        cols.append("guard INTEGER NOT NULL DEFAULT 0 CHECK (guard = 0)")
        sql = (
            f"CREATE TABLE IF NOT EXISTS {python_to_table_name(model)} "
            f"({', '.join(cols)}, UNIQUE(guard))"
        )
        await self.con.execute(sql)
        return
    
    async def create_id_table(self, model: Type[T]):
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

    async def create_table(self, model: Type[T]) -> bool:
        exists = await self.table_exists(python_to_table_name(model))
        if exists:
            return False

        is_single = getattr(model, "__single_value_table__", False)
        if is_single:
            await self.create_single_value_table(model)
        else:
            await self.create_id_table(model)

        return True

    async def insert(self, obj: T) -> int:
        is_single = getattr(type(obj), "__single_value_table__", False)
        data = asdict(obj)
        
        if is_single:
            # Insert once only. If a row already exists the UNIQUE(guard) constraint fires.
            table = python_to_table_name(type(obj))
            keys = ", ".join(data.keys())            # do NOT include `guard`; default 0 will be used
            qs   = ", ".join("?" for _ in data)
            sql  = f"INSERT INTO {table} ({keys}) VALUES ({qs})"
            try:
                await self.con.execute(sql, tuple(data.values()))
            except aiosqlite.IntegrityError as e:
                # Violates UNIQUE(guard) → singleton already exists
                raise ValueError(f"Insert refused: {table} already has a row") from e
            return 1

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
                if hasattr(obj, "id"):
                    setattr(obj, "id", new_id)
            except Exception:
                pass
            return new_id # type: ignore[return-value]
        
        return int(getattr(obj, "id")) if hasattr(obj, "id") else 1


    async def select(self, model: Type[T], where: Optional[list[WhereParam]] = None, order: list[OrderParam] = [], limit: Optional[int] = None) -> list[T]:
        if where is None:
            where = []

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

    async def update(self, obj: T, where: Optional[list[WhereParam]] = None) -> None:
        if where is None:
            where = []

        data = asdict(obj)
        data = {k: v for k, v in data.items() if v is not None}

        assigns = ", ".join(f"{k}=?" for k in data.keys())
        sql = f"UPDATE {python_to_table_name(type(obj))} SET {assigns}"
        
        actual_where: list[WhereParam] = where

        id_set = ("id" in data) or (data.get("id") is not None) or (data.get("id") != 0)
        if id_set:
            actual_where += [WhereParam("id", data.get("id"))]
        
        for idx, param in enumerate(where):            
            sql += " AND " if idx > 0 else " WHERE "
            sql += f"{param.field} = ?"        
            
        await self.con.execute(sql, list(data.values()) + [p.value for p in where])

    async def delete(self, model: Type[T], where: Optional[list[WhereParam]] = None) -> None:
        if where is None:
            where = []

        sql = f"DELETE FROM {python_to_table_name(model)}"
        
        for idx, param in enumerate(where):            
            sql += " AND " if idx > 0 else " WHERE "
            sql += f"{param.field} = ?"       

        await self.con.execute(sql, [p.value for p in where])

    async def insert_or_update(self, obj: T, where: Optional[list[WhereParam]] = None) -> int:
        """
        Insert a row. If a row with the same primary key exists, update it instead.
        Returns the object's id.
        """
        if where is None:
            where = []

        is_single = getattr(type(obj), "__single_value_table__", False)
        data = asdict(obj)
        table = python_to_table_name(type(obj))
        keys = list(data.keys())
        non_keys = keys.copy()

        if is_single:
            set_clause = ", ".join(f"{k}=excluded.{k}" for k in non_keys)
            sql = (
                f"INSERT INTO {table} ({', '.join(keys)}) VALUES ({', '.join('?' for _ in keys)}) "
                f"ON CONFLICT(guard) DO UPDATE SET {set_clause}"
            )
            await self.con.execute(sql, [data[k] for k in keys])
            return 1

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
        return int(getattr(obj, "id")) if hasattr(obj, "id") else 1


    async def join_select(
        self,
        left: Type[T],
        right: Type[U],
        where: Optional[list[WhereParam]] = None,
        order: list[OrderParam] = [],
        limit: int | None = None,
    ) -> list[tuple[T, U]]:
        if where is None:
            where = []

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
        
        await db.create_table(Purchase)

        await db.create_table(AdminBet)
        await db.create_table(GambleWin)

        await db.create_table(Gift)

        await db.create_table(AdminRollInfo)

        await db.create_table(DatabaseVersion)
        
        for timeout in timeout_data:
            await db.insert_or_update(timeout, where=[WhereParam("id", timeout.id)])



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

async def get_shop_credit(user_id: int) -> datetime.timedelta:
    async with Database(DATABASE_NAME) as db:
        user = await db.select(User, [WhereParam("id", user_id)])
        if not user:
            return datetime.timedelta(seconds=0)
        
        user = user[0]

        purchases = await db.select(Purchase, where=[WhereParam("user_id", user_id)])
        winnings = await db.select(GambleWin, where=[WhereParam("user_id", user_id)])
        bets = await db.select(AdminBet, where=[WhereParam("gamble_user_id", user_id)])

        credit = user.duration
        credit -= sum([p.cost for p in purchases])
        credit -= sum([b.amount for b in bets])
        credit += sum([w.amount for w in winnings])

        credit = max(credit, 0)

        return datetime.timedelta(seconds=credit)

async def can_afford_purchase(user: int, cost: int) -> bool:
    credit = await get_shop_credit(user)
    credit = credit.total_seconds()

    return cost <= credit

async def is_ongoing_sale() -> tuple[bool, Optional[datetime.datetime]]:
    async with Database(DATABASE_NAME) as db:
        sale = await db.select(Purchase, where=[WhereParam("item_id", BlackFridaySaleItem.ITEM_ID)], order=[OrderParam("timestamp", True)])
        if not sale:
            return False, None
        
        end_time = sale[0].timestamp + datetime.timedelta(minutes=30)
        return datetime.datetime.now() < end_time, end_time

#-----------------------------------------------------------------
#   Admin Roll

async def get_extra_admin_rolls(consume: bool) -> list[int]:
    async with Database(DATABASE_NAME) as db:
        bonus_tickets = await db.select(Purchase, where=[WhereParam("item_id", AdminTicketItem.ITEM_ID), WhereParam("used", False)])

        if consume:
            await db.update(Purchase(None, None, None, None, True), where=[WhereParam("item_id", AdminTicketItem.ITEM_ID)])

        return [t.user_id for t in bonus_tickets]
    

async def get_last_admin_roll() -> Optional[AdminRollInfo]:
    async with Database(DATABASE_NAME) as db:
        roll_info = await db.select(AdminRollInfo, limit=1)
        return roll_info[0] if roll_info else None
    
async def update_last_admin_roll():
    async with Database(DATABASE_NAME) as db:
        roll_info = AdminRollInfo(datetime.datetime.now())
        await db.insert_or_update(roll_info)
    
    
async def use_admin_reroll_token(user: int) -> tuple[bool, Optional[str]]:
    async with Database(DATABASE_NAME) as db:
        tokens = await db.select(Purchase, where=[WhereParam("item_id", AdminRerollItem.ITEM_ID), WhereParam("used", False)])
        if not tokens:
            return False, "Naughty naughty, you haven't purchased a reroll token."
        
        token = tokens[0]
        await db.update(Purchase(None, None, None, None, True), where=[WhereParam("id", token.id)])

        return True, None


#-----------------------------------------------------------------
#   Gamble
async def record_gamble(gamble_user: int, bet_user: int, amount: float) -> int:
    async with Database(DATABASE_NAME) as db:
        gamble = AdminBet(None, amount, gamble_user, bet_user, False)
        return await db.insert(gamble)
    
async def get_bets(user_id: int) -> dict[int, float]:
    async with Database(DATABASE_NAME) as db:
        bets = await db.select(AdminBet, where=[WhereParam("bet_user_id", user_id), WhereParam("used", False)])
        groups: dict[int, float] = { x.gamble_user_id: 0 for x in bets}
        for x in bets:
            groups[x.gamble_user_id] += x.amount

        return groups
    
def compute_betting_odds(bets: list[AdminBet]):
    # aggregation structure
    targets = defaultdict(lambda: {
        "total": 0.0,
        "bettors": defaultdict(lambda: {"amount": 0.0})
    })

    # accumulate amounts
    for b in bets:
        t = targets[b.bet_user_id]
        t["total"] += b.amount
        t["bettors"][b.gamble_user_id]["amount"] += b.amount

    # compute total across all targets
    grand_total = sum(t["total"] for t in targets.values())
    if grand_total == 0:
        grand_total = 1  # avoid division by zero

    # compute odds for each target and each bettor
    for target_id, info in targets.items():
        # odds of this target winning = total bet on them / total bet overall
        info["odds"] = info["total"] / grand_total

        # odds per bettor inside this target
        total_on_target = info["total"] or 1
        for bettor_id, binfo in info["bettors"].items():
            binfo["odds"] = binfo["amount"] / total_on_target

    return targets

async def get_gamble_odds(consume_bets: bool):
    async with Database(DATABASE_NAME) as db:
        all_bets = await db.select(AdminBet, where=[WhereParam("used", False)])

        if consume_bets:
            await db.update(AdminBet(None, None, None, None, True))

        return compute_betting_odds(bets=all_bets)
    
async def payout_gamble(user: int, value: float):
    async with Database(DATABASE_NAME) as db:
        await db.insert(GambleWin(None, amount=value, user_id=user))



#-----------------------------------------------------------------
#   Gifts

async def add_gift(gifter: int, receiver: int, value: int):
    async with Database(DATABASE_NAME) as db:
        await db.insert(Gift(None, value, gifter, receiver))


async def did_gift(gifter: int, receiver: int, value: int) -> bool:
    async with Database(DATABASE_NAME) as db:
        gifts = await db.select(Gift, where=[WhereParam("giver", gifter), WhereParam("receiver", receiver), WhereParam("amount", value)])
        return bool(gifts)

#-----------------------------------------------------------------
#   Utility

async def execute_raw_query(query: str):
    async with Database(DATABASE_NAME) as db:
        cur = await db.execute(query)
        if cur.description is None:
            return None, None  # no result set
        headers = [d[0] for d in cur.description]
        rows = await cur.fetchall()
        return headers, rows
