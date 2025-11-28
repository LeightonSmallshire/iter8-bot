import asyncio
import io
from typing import AsyncGenerator


# class Broadcaster:
#     def __init__(self):
#         self._eof = object()
#         self._lock = asyncio.Lock()
#         self._subscribers: list[asyncio.Queue] = []
#
#     async def announce(self, obj: object) -> None:
#         async with self._lock:
#             for subscriber in self._subscribers:
#                 await subscriber.put(obj)
#
#     async def close(self):
#         await self.announce(self._eof)
#
#     async def subscribe(self):
#         queue = asyncio.Queue()
#         try:
#             while True:
#                 item = await queue.get()
#                 if item is self._eof:
#                     break
#                 yield item
#         finally:
#             async with self._lock:
#                 self._subscribers.remove(queue)


class SingletonBashRunner:
    def __init__(self, script_path: str):
        self._script_path = script_path
        self._lock = asyncio.Lock()
        self._task: asyncio.Task | None = None
        self._buffer = io.StringIO()
        self._waiters: list[asyncio.Queue[str | None]] = []

    async def run(self) -> AsyncGenerator[str, None]:
        async with self._lock:
            if self._task is None or self._task.done():
                self._buffer = io.StringIO()
                self._waiters = []
                self._task = asyncio.create_task(self._worker())
        return self._subscribe()

    async def _worker(self):
        print('Starting update')
        proc = await asyncio.create_subprocess_exec(
            self._script_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT
        )
        print('1')

        assert proc.stdout is not None
        print('2')

        async for block in proc.stdout:
            print('3')

            text = block.decode()
            self._buffer.write(text)
            print(text, end='')

            # tee to all waiters
            for q in self._waiters:
                await q.put(text)

        print('4')
        await proc.wait()

        # signal completion to all waiters
        for q in self._waiters:
            await q.put(None)

    async def _subscribe(self) -> AsyncGenerator[str, None]:
        if self._buffer is not None:
            yield self._buffer.getvalue()

        if self._task is None or self._task.done():
            return

        q: asyncio.Queue[str | None] = asyncio.Queue()
        self._waiters.append(q)

        try:
            while True:
                chunk = await q.get()
                if chunk is None:
                    break
                yield chunk
        finally:
            self._waiters.remove(q)
