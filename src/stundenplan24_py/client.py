from __future__ import annotations

import dataclasses
import datetime
import urllib.parse

import aiohttp as aiohttp

__all__ = [
    "Stundenplan24Credentials",
    "Endpoints",
    "Stundenplan24Client"
]


@dataclasses.dataclass
class Stundenplan24Credentials:
    user_name: str
    password: str


class Endpoints:
    # indiware mobil students
    indiware_mobil = "{school_number}/mobil/mobdaten/PlanKl{date}.xml"  # date must not be "", use below
    indiware_mobil2 = "{school_number}/mobil/mobdaten/Klassen.xml"

    # indiware mobil teachers
    indiware_mobil_teachers = "{school_number}/moble/mobdaten/PlanLe{date}.xml"  # date must not be "", use below
    indiware_mobil_teachers2 = "{school_number}/moble/mobdaten/Lehrer.xml"

    # substitution plan students
    substitution_plan = "{school_number}/vplan/vdaten/VplanKl{date}.xml"

    # substitution plan teachers
    substitution_plan_teachers = "{school_number}/vplanle/vdaten/VplanLe{date}.xml"

    # week plan
    week_plan_timetable_base = "{school_number}/wplan/wdatenk/SPlanKl_Basis.xml"
    week_plan_timetable = "{school_number}/wplan/wdatenk/SPlanKl_Sw{school_week}.xml"
    week_plan = "{school_number}/wplan/wdatenk/WPlanKl_{date}.xml"  # date must not be ""

    # timetable
    timetable = "{school_number}/splan/sdaten/splank.xml"


class Stundenplan24Client:
    def __init__(self,
                 school_number: int,
                 credentials: Stundenplan24Credentials,
                 base_url: str = "https://www.stundenplan24.de/"):
        self.school_number = school_number
        self.credentials = credentials
        self.base_url = base_url

    def get_url(self, endpoint: str) -> str:
        this_endpoint = endpoint.replace(
            "{school_number}", str(self.school_number)
        )

        return urllib.parse.urljoin(self.base_url, this_endpoint)

    async def fetch_url(self, url: str, session: aiohttp.ClientSession | None) -> str:
        if session is None:
            async with aiohttp.ClientSession() as session:
                return await self.fetch_url(url, session)

        auth = aiohttp.BasicAuth(self.credentials.user_name, self.credentials.password)

        async with session.get(url, auth=auth) as response:
            if response.status != 200:
                raise RuntimeError(f"Got status code {response.status} from {url!r}.")

            return await response.text()

    async def fetch_indiware_mobil(self,
                                   date: datetime.date | None = None,
                                   session: aiohttp.ClientSession | None = None
                                   ) -> str:
        if date is None:
            url = self.get_url(Endpoints.indiware_mobil2)
        else:
            url = self.get_url(Endpoints.indiware_mobil).format(date=date.strftime("%Y%m%d"))

        return await self.fetch_url(url, session)

    async def fetch_substitution_plan(self,
                                      date: datetime.date | None = None,
                                      session: aiohttp.ClientSession | None = None
                                      ) -> str:
        if date is None:
            url = self.get_url(Endpoints.substitution_plan).format(date="")
        else:
            url = self.get_url(Endpoints.substitution_plan).format(date=date.strftime("%Y%m%d"))

        return await self.fetch_url(url, session)
