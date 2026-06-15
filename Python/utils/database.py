import datetime
import sqlite3
from collections.abc import Sequence
from contextlib import suppress
from dataclasses import asdict, dataclass, fields
from typing import Any, TypeVar, cast, get_type_hints, overload

import aiosqlite
from packaging.version import Version

from .model import (
    AdminBet,
    DatabaseVersion,
    GambleWin,
    Gift,
    HasIdTable,
    IsDatabaseTable,
    Log,
    Purchase,
    SingleValueTable,
    Stock,
    Timestamps,
    Trade,
    User,
    is_nullable,
    python_to_sql_type,
    python_to_table_name,
)

_T = TypeVar("_T", bound=IsDatabaseTable)
_U = TypeVar("_U", bound=IsDatabaseTable)
_T_single = TypeVar("_T_single", bound=SingleValueTable)
_T_id = TypeVar("_T_id", bound=HasIdTable)


@dataclass
class WhereParam:
    field: str
    value: Any
    cmp: str = '=' # '=', 'IS', 'IS NOT'

WhereNode = WhereParam | list[WhereParam]
WhereClause = list[WhereNode]

def build_where_clause(where: WhereClause) -> tuple[str, list[object]]:
    """
    AND between top-level nodes.
    OR inside nested lists.
    """
    if not where:
        return "", []

    parts: list[str] = []
    params: list[object] = []

    for node in where:
        # Single condition
        if isinstance(node, WhereParam):
            fragment, frag_params = _render_param(node)
            parts.append(fragment)
            params.extend(frag_params)
            continue

        # OR-group: list[WhereParam]
        if not node:  # empty group, skip
            continue

        or_fragments: list[str] = []
        for p in node:
            fragment, frag_params = _render_param(p)
            or_fragments.append(fragment)
            params.extend(frag_params)

        parts.append(f"({' OR '.join(or_fragments)})")

    return " WHERE " + " AND ".join(parts), params

def _render_param(p: WhereParam) -> tuple[str, list[object]]:
    # Handle IS / IS NOT with NULL
    if p.value is None and p.cmp in ("=", "IS", "IS NOT"):
        if p.cmp == "=":
            return f"{p.field} IS NULL", []
        return f"{p.field} {p.cmp} NULL", []

    return f"{p.field} {p.cmp} ?", [p.value]

@dataclass
class OrderParam:
    field: str
    descending: bool

def _alias_cols(cls: type, alias: str) -> list[str]:
    return [f'{alias}.{f.name} AS "{alias}.{f.name}"' for f in fields(cls)]

def _row_to[T: IsDatabaseTable](cls: type[T], row: aiosqlite.Row, alias: str) -> T:
    data = {f.name: row[f"{alias}.{f.name}"] for f in fields(cls)}
    return cast(T, cls(**data))

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
    def __init__(self, path: str, defer_commit: bool = False) -> None:
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

    async def connect(self) -> "Database":
        self.con = await aiosqlite.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.con.row_factory = aiosqlite.Row
        return self

    async def commit(self) -> None:
        await self.con.commit()
        await self.con.close()

    async def rollback(self) -> None:
        await self.con.rollback()
        await self.con.close()

    async def __aenter__(self) -> "Database":
        self.con = await aiosqlite.connect(self.path, detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
        self.con.row_factory = aiosqlite.Row
        return self

    async def __aexit__(self, exc_type: type[BaseException] | None, exc: BaseException | None, tb: Any) -> None:
        if self.defer_commit:
            return

        if exc_type:
            with suppress(aiosqlite.Error):
                await self.con.rollback()
        else:
            with suppress(aiosqlite.Error):
                await self.con.commit()
        await self.con.close()

    async def execute(self, query: str) -> aiosqlite.Cursor:
        return await self.con.execute(query)

    async def executescript(self, query: str) -> aiosqlite.Cursor:
        return await self.con.executescript(query)

    async def drop_table_with_name(self, table: str) -> None:
        sql = f"DROP TABLE IF EXISTS {table}"
        await self.con.execute(sql)

    async def drop_table(self, model: type[_T]) -> None:
        await self.drop_table_with_name(python_to_table_name(model))

    async def table_exists(self, table_name: str) -> bool:
        cur = await self.con.execute(
            "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?",
            (table_name,),
        )
        return (await cur.fetchone()) is not None

    async def create_single_value_table(self, model: type[_T]) -> None:
        cols = []
        hints = get_type_hints(model)
        for f in fields(model):
            if f.name == "__single_value_table__":
                continue
            typename = hints[f.name]
            sql_type = python_to_sql_type(typename)
            cols.append(f"{f.name} {sql_type}{'' if is_nullable(typename) else ' NOT NULL'}")
        cols.append("guard INTEGER NOT NULL DEFAULT 0 CHECK (guard = 0)")
        sql = (
            f"CREATE TABLE IF NOT EXISTS {python_to_table_name(model)} "
            f"({', '.join(cols)}, UNIQUE(guard))"
        )
        await self.con.execute(sql)
        return

    async def create_id_table(self, model: type[_T]) -> None:
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


    async def create_table(self, model: type[_T]) -> bool:
        exists = await self.table_exists(python_to_table_name(model))
        if exists:
            return False

        is_single = getattr(model, "__single_value_table__", False)
        if is_single:
            await self.create_single_value_table(model)
        else:
            await self.create_id_table(model)

        return True


    async def insert(self, obj: _T) -> int:
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
                if isinstance(obj, HasIdTable):
                    obj.id = new_id
            except Exception:
                pass
            if new_id is None:
                return 0
            return new_id

        if isinstance(obj, HasIdTable):
            val = obj.id
            return int(val) if val is not None else 0
        return 1



    @overload
    async def select(self, model: type[_T_single], where: WhereClause | None = None, order: list[OrderParam] | None = None, limit: int | None = None) -> _T_single: ...

    @overload
    async def select(self, model: type[_T_id], where: WhereClause | None = None, order: list[OrderParam] | None = None, limit: int | None = None) -> list[_T_id]: ...

    async def select(self, model: type[_T], where: WhereClause | None = None, order: list[OrderParam] | None = None, limit: int | None = None) -> _T | list[_T]:
        if where is None:
            where = []
        if order is None:
            order = []

        is_single = getattr(model, "__single_value_table__", False)

        sql = f"SELECT * FROM {python_to_table_name(model)}"

        where_sql, params = build_where_clause(where)
        sql += where_sql

        for idx, param in enumerate(order):
            sql += " ORDER BY " if idx == 0 else ", "
            sql += f"{param.field} {'DESC' if param.descending else ''}"

        cur = await self.con.execute(sql, params)
        rows = cast(list[aiosqlite.Row], await cur.fetchmany(limit) if limit else await cur.fetchall())
        data_rows: list[dict[str, Any]] = [dict(row) for row in rows]

        if is_single:
            for row in data_rows:
                row.pop("guard", None)

        results: list[_T] = [cast(_T, model(**row)) for row in data_rows]
        return results[0] if is_single else results


    async def update(self, obj: _T, where: WhereClause | None = None) -> None:
        if where is None:
            where = []

        data = asdict(obj)
        data = {k: v for k, v in data.items() if v is not None}

        assigns = ", ".join(f"{k}=?" for k in data)
        sql = f"UPDATE {python_to_table_name(type(obj))} SET {assigns}"

        id_set = ("id" in data) and (data.get("id") is not None) and (data.get("id") != 0)
        if id_set:
            where += [WhereParam("id", data.get("id"))]

        where_sql, where_params = build_where_clause(where)
        sql += where_sql

        await self.con.execute(sql, list(data.values()) + where_params)

    async def delete(self, model: type[_T], where: WhereClause | None = None) -> None:
        if where is None:
            where = []

        sql = f"DELETE FROM {python_to_table_name(model)}"

        where_sql, where_params = build_where_clause(where)
        sql += where_sql

        await self.con.execute(sql, where_params)

    async def insert_or_update(self, obj: _T, where: WhereClause | None = None) -> int:
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

        where_sql, where_params = build_where_clause(where)

        sql = (
            f"INSERT INTO {table} ({columns}) VALUES ({placeholders}) "
            f"ON CONFLICT(id) DO UPDATE SET {set_clause}{where_sql}"
        )

        params = [data[k] for k in keys] + where_params
        await self.con.execute(sql, params)
        if isinstance(obj, HasIdTable):
            val = obj.id
            return int(val) if val is not None else 0
        return 1



    async def join_select(
        self,
        left: type[_T],
        right: type[_U],
        where: WhereClause | None = None,
        order: list[OrderParam] | None = None,
        limit: int | None = None,
    ) -> list[tuple[_T, _U]]:
        if where is None:
            where = []
        if order is None:
            order = []

        la, ra = "l", "r"
        lt, rt = python_to_table_name(left), python_to_table_name(right)

        # infer join
        side, fk_field, pk_field = _find_relationship(left, right)
        join_expr = f"{la}.{fk_field} = {ra}.{pk_field}" if side == "left" else f"{la}.{pk_field} = {ra}.{fk_field}"

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

        where_sql, where_params = build_where_clause(where)
        sql.append(where_sql)
        params += where_params

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

        out: list[tuple[_T, _U]] = []
        for row in rows:
            left_obj = _row_to(left, row, la)
            right_obj = _row_to(right, row, ra)
            out.append((left_obj, right_obj))
        return out




DATABASE_NAME = "data/storage.db"


#-----------------------------------------------------------------
#   Initialisation

async def init_database(timeout_data: list[User], stock_list: list[Stock]) -> None:
    async with Database(DATABASE_NAME) as db:
        await db.create_table(cast(type[IsDatabaseTable], User))

        await db.create_table(cast(type[IsDatabaseTable], Log))

        await db.create_table(cast(type[IsDatabaseTable], Purchase))

        await db.create_table(cast(type[IsDatabaseTable], AdminBet))
        await db.create_table(cast(type[IsDatabaseTable], GambleWin))

        await db.create_table(cast(type[IsDatabaseTable], Gift))

        if await db.create_table(cast(type[IsDatabaseTable], Timestamps)):
            await db.insert(cast(IsDatabaseTable, Timestamps(datetime.datetime.now() - datetime.timedelta(days=31), datetime.datetime.now())))

        await db.create_table(cast(type[IsDatabaseTable], DatabaseVersion))

        if await db.create_table(cast(type[IsDatabaseTable], Stock)):
            for stock in stock_list:
                await db.insert(cast(IsDatabaseTable, stock))

        await db.create_table(cast(type[IsDatabaseTable], Trade))

        for timeout in timeout_data:
            await db.insert_or_update(cast(IsDatabaseTable, timeout), where=[WhereParam("id", timeout.id)])



#-----------------------------------------------------------------
#   Utility

async def execute_raw_query(query: str) -> tuple[list[str] | None, Sequence[aiosqlite.Row] | None]:
    async with Database(DATABASE_NAME) as db:
        cur = await db.execute(query)
        if cur.description is None:
            return None, None  # no result set
        headers = [d[0] for d in cur.description]
        rows = await cur.fetchall()
        return cast(tuple[list[str] | None, Sequence[aiosqlite.Row] | None], (headers, rows))


async def execute_raw_script(script: str) -> tuple[list[str] | None, Sequence[aiosqlite.Row] | None]:
    async with Database(DATABASE_NAME) as db:
        cur = await db.executescript(script)
        if cur.description is None:
            return None, None  # no result set
        headers = [d[0] for d in cur.description]
        rows = await cur.fetchall()
        return cast(tuple[list[str] | None, Sequence[aiosqlite.Row] | None], (headers, rows))
