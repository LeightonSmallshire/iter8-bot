from .database import Database, DATABASE_NAME, WhereParam, OrderParam
from .model import User

async def get_timeout_leaderboard() -> list[User]:
    async with Database(DATABASE_NAME) as db:
        result = await db.select(User, order=[OrderParam("count", True), OrderParam("duration", True)])
        return result if isinstance(result, list) else []

async def update_timeout_leaderboard(user: int, duration: float) -> None:   
    async with Database(DATABASE_NAME) as db:
        timeouts_for_user = await db.select(User, where=[WhereParam("id", user)])
        if timeouts_for_user:
            timeout = timeouts_for_user[0]  # type: ignore[index]
            timeout.count += 1 if duration > 0 else 0
            timeout.duration += duration
            await db.update(timeout, [WhereParam("id", user)])
        else:
            timeout = User(user, 1 if duration > 0 else 0, duration)
            await db.insert(timeout)


async def erase_timeout_user(user: int) -> None:
    async with Database(DATABASE_NAME) as db:
        await db.delete(User, [WhereParam("id", user), ])