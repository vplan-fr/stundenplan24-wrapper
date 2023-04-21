from __future__ import annotations

import dataclasses
import datetime
import urllib.parse

import aiohttp as aiohttp


@dataclasses.dataclass
class Stundenplan24Credentials:
    user_name: str
    password: str


class Endpoints:
    indiware_mobil = "{school_number}/mobil/mobdaten/Klassen{date}.xml"
    substitution_plan = "{school_number}/vplan/vdaten/VplanKl{date}.xml"


class Stundenplan24Client:
    def __init__(self,
                 school_number: int,
                 credentials: Stundenplan24Credentials,
                 base_url: str = "https://www.stundenplan24.de/"):
        self.school_number = school_number
        self.credentials = credentials
        self.base_url = base_url

    def get_url(self, endpoint: str, date: datetime.date | None = None) -> str:
        date = date.strftime("%Y%m%d") if date is not None else ""

        this_endpoint = endpoint.format(
            school_number=self.school_number,
            date=date
        )

        return urllib.parse.urljoin(self.base_url, this_endpoint)

    async def fetch_url(self, url: str, session: aiohttp.ClientSession | None) -> str:
        if session is None:
            async with aiohttp.ClientSession() as session:
                return await self.fetch_url(url, session)

        auth = aiohttp.BasicAuth(self.credentials.user_name, self.credentials.password)

        async with session.get(url, auth=auth) as response:
            return await response.text()

    async def fetch_indiware_mobile(self, session: aiohttp.ClientSession, date: datetime.date | None = None) -> str:
        url = self.get_url(Endpoints.indiware_mobil, date)
        return await self.fetch_url(url, session)

    async def fetch_substitution_plan(self, session: aiohttp.ClientSession, date: datetime.date | None = None) -> str:
        url = self.get_url(Endpoints.substitution_plan, date)
        return await self.fetch_url(url, session)
