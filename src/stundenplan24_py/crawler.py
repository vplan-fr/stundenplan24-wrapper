from __future__ import annotations

import asyncio
import dataclasses
import datetime
import os
import typing
from pathlib import Path


@dataclasses.dataclass
class Result:
    data: str
    timestamp: datetime.datetime
    from_cache: bool = False


class Crawler:
    def __init__(self,
                 folder: Path,
                 getter_coro: typing.Callable[[datetime.date], typing.Awaitable[Result]],
                 crawl_interval: float = 60 * 30,
                 look_back: int = 10,
                 look_forward: int = 10):
        self.folder = folder
        self.getter_coro = getter_coro

        self.crawl_interval = crawl_interval
        self.look_back = look_back
        self.look_forward = look_forward

    @staticmethod
    def _iterate_revisions(folder: Path) -> typing.Iterator[Result]:
        revisions = os.listdir(folder)

        for revision in sorted(revisions, key=int, reverse=True):
            with open(folder / revision, "r", encoding="utf-8") as f:
                yield Result(
                    data=f.read(),
                    timestamp=datetime.datetime.fromtimestamp(int(revision)),
                    from_cache=True
                )

    def store_result(self, date: datetime.date, result: Result | None):
        parent_folder = self.folder / date.strftime("%Y-%m-%d")
        parent_folder.mkdir(parents=True, exist_ok=True)

        if result is None:
            return

        file_path = parent_folder / str(int(result.timestamp.timestamp()))
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(result.data)

    async def fetch(self, date: datetime.date) -> Result:
        try:
            result = await self.getter_coro(date)
        except RuntimeError:
            self.store_result(date, None)
        else:
            self.store_result(date, result)
            return result

    async def get(self, date: datetime.date) -> typing.AsyncIterator[Result]:
        date_str = date.strftime("%Y-%m-%d")

        if (self.folder / date_str).exists():
            for revision in self._iterate_revisions(self.folder / date_str):
                yield revision
        else:
            yield await self.fetch(date)

    async def crawl(self):
        while True:
            await self.update_days()

            await asyncio.sleep(self.crawl_interval)

    async def update_days(self):
        day = datetime.date.today() - datetime.timedelta(days=self.look_back)
        end_day = datetime.date.today() + datetime.timedelta(days=self.look_forward)

        while day <= end_day:
            await self.fetch(day)

            day += datetime.timedelta(days=1)

    def all(self) -> typing.Iterator[Result]:
        for date in os.listdir(self.folder):
            yield from self._iterate_revisions(self.folder / date)
