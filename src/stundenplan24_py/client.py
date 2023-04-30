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
    username: str
    password: str


class Endpoints:
    # indiware mobil
    indiware_mobil_vpdir = "{school_number}/mobil/_phpmob/vpdir.php"  # POST with data
    indiware_mobil_vpinfok = "{school_number}/mobil/mobdaten/vpinfok.txt"

    # indiware mobil students
    indiware_mobil = "{school_number}/mobil/mobdaten/{filename}"  # date must not be "", use below
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


class NoPlanForDateError(Exception):
    pass


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

    async def fetch_url(self, url: str, session: aiohttp.ClientSession | None, method: str = "GET", **kwargs) -> str:
        if session is None:
            async with aiohttp.ClientSession() as session:
                return await self.fetch_url(url, session, method, **kwargs)

        auth = aiohttp.BasicAuth(self.credentials.username, self.credentials.password)

        async with session.request(method, url, auth=auth, **kwargs) as response:
            if response.status != 200:
                raise RuntimeError(f"Got status code {response.status} from {url!r}.", response.status)

            return await response.text()

    async def fetch_indiware_mobil(self,
                                   date_or_filename: str | datetime.date | None = None,
                                   session: aiohttp.ClientSession | None = None
                                   ) -> str:
        if date_or_filename is None:
            url = self.get_url(Endpoints.indiware_mobil2)

        elif isinstance(date_or_filename, str):
            url = self.get_url(Endpoints.indiware_mobil).format(filename=date_or_filename)

        elif isinstance(date_or_filename, datetime.date):
            url = self.get_url(Endpoints.indiware_mobil).format(
                filename=f"PlanKl{date_or_filename.strftime('%Y%m%d')}.xml"
            )

        else:
            raise TypeError(f"date_or_filename must be str, datetime.date or None, not {type(date_or_filename)}")

        try:
            return await self.fetch_url(url, session)
        except RuntimeError as e:
            if e.args[1] == 404:
                raise NoPlanForDateError(f"No plan for {date_or_filename!r} found.") from e
            raise

    async def fetch_dates_indiware_mobil(self,
                                         session: aiohttp.ClientSession | None = None
                                         ) -> dict[str, datetime.datetime]:
        url = self.get_url(Endpoints.indiware_mobil_vpdir)

        with aiohttp.MultipartWriter("form-data") as mpwriter:
            # noinspection PyTypeChecker
            mpwriter.append(
                "I N D I W A R E",
                {"Content-Disposition": 'form-data; name="pw"'}
            )
            # noinspection PyTypeChecker
            mpwriter.append(
                "mobk",
                {"Content-Disposition": 'form-data; name="art"'}
            )

        _out = (await self.fetch_url(url, session, method="POST", data=mpwriter)).split(";")

        out: dict[str, datetime.datetime] = {}
        for i in range(0, len(_out), 2):
            if not _out[i]:
                continue

            filename, date_str = _out[i:i + 2]

            out[filename] = datetime.datetime.strptime(date_str, "%d.%m.%Y %H:%M")

        return out

    async def fetch_substitution_plan(self,
                                      date: datetime.date | None = None,
                                      session: aiohttp.ClientSession | None = None
                                      ) -> str:
        if date is None:
            url = self.get_url(Endpoints.substitution_plan).format(date="")
        else:
            url = self.get_url(Endpoints.substitution_plan).format(date=date.strftime("%Y%m%d"))

        return await self.fetch_url(url, session)
