from __future__ import annotations

import asyncio
import dataclasses
import datetime
import os
import typing
import xml.etree.ElementTree as ET
from pathlib import Path

__all__ = [
    "Result",
    "IndiwareMobilCrawler",
]

from .client import Stundenplan24Client
from .indiware_mobil import FormPlan

T = typing.TypeVar("T")
T_Interpreted = typing.TypeVar("T_Interpreted", str, typing.Any)


@dataclasses.dataclass
class Result(typing.Generic[T]):
    data: T
    timestamp: datetime.datetime

    def interpret(self, interpreter: typing.Callable[[T], T_Interpreted]) -> Result[T_Interpreted]:
        return Result(
            data=interpreter(self.data),
            timestamp=self.timestamp,
        )


class NotInCacheError(Exception):
    pass


class IndiwareMobilCrawler:
    _interpreter = staticmethod(lambda data: FormPlan.from_xml(ET.fromstring(data)))

    def __init__(self,
                 client: Stundenplan24Client,
                 folder: Path):
        self.client = client
        self.folder = folder

    @staticmethod
    def _iterate_revisions(folder: Path) -> typing.Iterator[Result[str]]:
        revisions = os.listdir(folder)

        for revision in sorted(revisions, key=int, reverse=True):
            with open(folder / revision, "r", encoding="utf-8") as f:
                yield Result(
                    data=f.read(),
                    timestamp=datetime.datetime.fromtimestamp(int(revision)),
                )

    def store_result(self, date: datetime.date, result: Result[str] | None):
        parent_folder = self.folder / date.strftime("%Y-%m-%d")
        parent_folder.mkdir(parents=True, exist_ok=True)

        if result is None:
            return

        file_path = parent_folder / str(int(result.timestamp.timestamp()))
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(result.data)

    def get_latest_timestamp(self, date: datetime.date) -> datetime.datetime | None:
        parent_folder = self.folder / date.strftime("%Y-%m-%d")
        try:
            revisions = sorted(os.listdir(parent_folder), key=int, reverse=True)
        except FileNotFoundError:
            return None

        return datetime.datetime.fromtimestamp(int(revisions[0]))

    async def fetch(self, date: datetime.date, timestamp: datetime.datetime) -> Result[str]:
        """Return the plan file for the given date and store it in the cache using the given timestamp."""

        try:
            data = await self.client.fetch_indiware_mobil(date)
            result = Result(data=data, timestamp=timestamp)
        except RuntimeError:
            # no plan available for this day
            self.store_result(date, None)
        else:
            self.store_result(date, result)
            return result

    def get_raw(self, date: datetime.date) -> typing.Iterator[Result[str]]:
        date_str = date.strftime("%Y-%m-%d")

        if (self.folder / date_str).exists():
            for revision in self._iterate_revisions(self.folder / date_str):
                yield revision
        else:
            raise NotInCacheError(f"Date {date_str!r} was not crawled.")

    def get(self, date: datetime.date) -> typing.Iterator[Result[FormPlan]]:
        for revision in self.get_raw(date):
            yield revision.interpret(self._interpreter)

    def all_raw(self) -> typing.Iterator[Result[str]]:
        for date in os.listdir(self.folder):
            yield from self._iterate_revisions(self.folder / date)

    def all(self) -> typing.Iterator[Result[FormPlan]]:
        for revision in self.all_raw():
            yield revision.interpret(self._interpreter)

    async def crawl(self, interval: float = 60):
        while True:
            await self.update_days()

            await asyncio.sleep(interval)

    async def update_days(self):
        day_filenames = await self.client.fetch_dates_indiware_mobil()

        for day, latest_timestamp in day_filenames.items():
            if day == "Klassen.xml":
                # this is always the latest available plan, it also exists as a file with a date
                continue

            date = datetime.datetime.strptime(day, "PlanKl%Y%m%d.xml").date()

            latest_cached = self.get_latest_timestamp(date)
            if latest_cached is not None and latest_timestamp <= latest_cached:
                continue

            await self.fetch(date, latest_timestamp)
