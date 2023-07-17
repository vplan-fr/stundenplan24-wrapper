from __future__ import annotations

import abc
import dataclasses
import datetime

import aiohttp as aiohttp

__all__ = [
    "Credentials",
    "Endpoints",
    "EndpointCollection",
    "Stundenplan24StudentsEndpointCollection",
    "Stundenplan24TeachersEndpointCollection",
    "SelfHostedEndpointCollection",
    "NoPlanForDateError",
    "IndiwareStundenplanerClient"
]


@dataclasses.dataclass
class Credentials:
    username: str
    password: str


class Endpoints:
    # indiware mobil (/mobil/ or /moble/)
    indiware_mobil_vpdir = "_phpmob/vpdir.php"  # POST with data
    indiware_mobil_vpinfok = "mobdaten/vpinfok.txt"

    indiware_mobil = "mobdaten/{filename}"
    indiware_mobil2 = "mobdaten/PlanKl{date}.xml"  # date must not be "", use below
    indiware_mobil3 = "mobdaten/Klassen.xml"

    # substitution plan (/vplan/ or /vplanle/)
    substitution_plan = "vdaten/{filename}.xml"
    substitution_plan2 = "vdaten/VplanKl{date}.xml"  # date can be ""

    # week plan (/wplan/)
    week_plan_timetable_base = "wdatenk/SPlanKl_Basis.xml"
    week_plan_timetable = "wdatenk/SPlanKl_Sw{school_week}.xml"
    week_plan = "wdatenk/WPlanKl_{date}.xml"  # date must not be ""

    # timetable (/splan/)
    timetable = "sdaten/splank.xml"


class EndpointCollection(abc.ABC):
    indiware_mobil: str | None
    substitution_plan: str | None
    week_plan: str | None
    timetable: str | None


class Stundenplan24StudentsEndpointCollection(EndpointCollection):
    def __init__(self, school_number: str, sp24_url: str = "https://www.stundenplan24.de/"):
        self.indiware_mobil = f"{sp24_url}{school_number}/mobil/"
        self.substitution_plan = f"{sp24_url}{school_number}/vplan/"
        self.week_plan = f"{sp24_url}{school_number}/wplan/"
        self.timetable = f"{sp24_url}{school_number}/splan/"


class Stundenplan24TeachersEndpointCollection(EndpointCollection):
    def __init__(self, school_number: str, sp24_url: str = "https://www.stundenplan24.de/"):
        self.indiware_mobil = f"{sp24_url}{school_number}/moble/"
        self.substitution_plan = f"{sp24_url}{school_number}/vplanle/"
        self.week_plan = f"{sp24_url}{school_number}/wplan/"
        self.timetable = f"{sp24_url}{school_number}/splan/"


@dataclasses.dataclass
class SelfHostedEndpointCollection(EndpointCollection):
    indiware_mobil: str | None
    substitution_plan: str | None
    week_plan: str | None
    timetable: str | None


class NoPlanForDateError(Exception):
    pass


class IndiwareStundenplanerClient:
    def __init__(self,
                 endpoint_collection: EndpointCollection,
                 credentials: Credentials):
        self.endpoint_collection = endpoint_collection
        self.credentials = credentials

    async def fetch_url(self, url: str, method: str = "GET", **kwargs) -> str:
        auth = aiohttp.BasicAuth(self.credentials.username, self.credentials.password)

        async with aiohttp.ClientSession() as session:
            async with session.request(method, url, auth=auth, **kwargs) as response:
                if response.status != 200:
                    raise RuntimeError(f"Got status code {response.status} from {url!r}.", response.status)

                return await response.text(encoding="utf-8")

    async def fetch_indiware_mobil(self, date_or_filename: str | datetime.date | None = None) -> str:
        if date_or_filename is None:
            _url = Endpoints.indiware_mobil3
        elif isinstance(date_or_filename, str):
            _url = Endpoints.indiware_mobil.format(filename=date_or_filename)
        elif isinstance(date_or_filename, datetime.date):
            _url = Endpoints.indiware_mobil2.format(date=date_or_filename.strftime("%Y%m%d"))
        else:
            raise TypeError(f"date_or_filename must be str, datetime.date or None, not {type(date_or_filename)!r}.")

        url = self.endpoint_collection.indiware_mobil + _url

        try:
            return await self.fetch_url(url)
        except RuntimeError as e:
            if e.args[1] == 404:
                raise NoPlanForDateError(f"No plan for {date_or_filename!r} found.") from e
            else:
                raise

    async def fetch_dates_indiware_mobil(self) -> dict[str, datetime.datetime]:
        url = self.endpoint_collection.indiware_mobil + Endpoints.indiware_mobil_vpdir

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

        _out = (await self.fetch_url(url, method="POST", data=mpwriter)).split(";")

        out: dict[str, datetime.datetime] = {}
        for i in range(0, len(_out), 2):
            if not _out[i]:
                continue

            filename, date_str = _out[i:i + 2]

            out[filename] = datetime.datetime.strptime(date_str, "%d.%m.%Y %H:%M")

        return out

    async def fetch_substitution_plan(self, date_or_filename: datetime.date | str | None = None) -> str:
        if date_or_filename is None:
            _url = Endpoints.substitution_plan2.format(date="")
        elif isinstance(date_or_filename, str):
            _url = Endpoints.substitution_plan.format(filename=date_or_filename)
        else:
            _url = Endpoints.substitution_plan2.format(date=date_or_filename.strftime("%Y%m%d"))

        url = self.endpoint_collection.substitution_plan + _url

        try:
            return await self.fetch_url(url)
        except RuntimeError as e:
            if e.args[1] == 404:
                raise NoPlanForDateError(f"No plan for {date_or_filename!r} found.") from e
            else:
                raise
