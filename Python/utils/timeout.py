from typing import cast
from .database import DATABASE_NAME, Database, OrderParam, WhereParam
from .model import User, IsDatabaseTable


async def get_timeout_leaderboard() -> list[User]:
    async with Database(DATABASE_NAME) as db:
        return cast(list[User], await db.select(User, order=[OrderParam("count", True), OrderParam("duration", True)]))


async def update_timeout_leaderboard(user: int, duration: float) -> None:
    async with Database(DATABASE_NAME) as db:
        timeouts_for_user = cast(list[User], await db.select(User, where=[WhereParam("id", user)]))
        if len(timeouts_for_user) > 0:
            timeout = timeouts_for_user[0]
            timeout.count += 1 if duration > 0 else 0
            timeout.duration += duration
            await db.update(cast(IsDatabaseTable, timeout), [WhereParam("id", user)])
        else:
            timeout = User(user, 1 if duration > 0 else 0, duration)
            await db.insert(cast(IsDatabaseTable, timeout))


async def erase_timeout_user(user: int) -> None:
    async with Database(DATABASE_NAME) as db:
        await db.delete(cast(type[IsDatabaseTable], User), [WhereParam("id", user)])
