from __future__ import annotations

import abc
import dataclasses
import datetime
import urllib.parse
import typing

import aiohttp as aiohttp

__all__ = [
    "Credentials",
    "Endpoints",
    "IndiwareMobilEndpoint",
    "Stundenplan24FormsIndiwareMobilEndpoint",
    "Stundenplan24RoomsIndiwareMobilEndpoint",
    "Stundenplan24TeachersIndiwareMobilEndpoint",
    "SelfHostedIndiwareMobilEndpoint",
    "IndiwareMobilEndpoints",
    "Hosting",
    "PlanClientError",
    "UnauthorizedError",
    "NoPlanForDateError",
    "PlanClient",
    "IndiwareMobilClient",
    "SubstitutionPlanClient",
    "IndiwareStundenplanerClient"
]


@dataclasses.dataclass
class Credentials:
    username: str
    password: str


class Endpoints:
    # indiware mobil
    indiware_mobil_vpdir = "_phpmob/vpdir.php"  # POST with data
    indiware_mobil_file = "mobdaten/{filename}"

    # /mobil/
    indiware_mobil_forms = "mobdaten/PlanKl{date}.xml"  # date must not be "", use below
    indiware_mobil_forms2 = "mobdaten/Klassen.xml"
    indiware_mobil_forms_vpinfo = "mobdaten/vpinfok.txt"

    # /moble/
    indiware_mobil_teachers = "mobdaten/PlanLe{date}.xml"  # date must not be "", use below
    indiware_mobil_teachers2 = "mobdaten/Lehrer.xml"
    indiware_mobil_teachers_vpinfo = "mobdaten/vpinfol.txt"

    # /mobra/
    indiware_mobil_rooms = "mobdaten/PlanRa{date}.xml"  # date must not be "", use below
    indiware_mobil_rooms2 = "mobdaten/Raeume.xml"
    indiware_mobil_rooms_vpinfo = "mobdaten/vpinfor.txt"

    # substitution plan (/vplan/ or /vplanle/)
    substitution_plan = "vdaten/{filename}.xml"
    substitution_plan2 = "vdaten/VplanKl{date}.xml"  # date can be ""

    # week plan (/wplan/)
    week_plan_forms_timetable = "wdatenk/SPlanKl_Sw{school_week}.xml"
    week_plan_forms_timetable2 = "wdatenk/SPlanKl_Basis.xml"
    week_plan_forms = "wdatenk/WPlanKl_{date}.xml"  # date must not be ""

    week_plan_teachers_timetable = "wdatenr/SPlanLe_Sw{school_week}.xml"
    week_plan_teachers_timetable2 = "wdatenr/SPlanLe_Basis.xml"
    week_plan_teachers = "wdatenr/WPlanLe_{date}.xml"  # date must not be ""

    week_plan_rooms_timetable = "wdatenl/SPlanRa_Sw{school_week}.xml"
    week_plan_rooms_timetable2 = "wdatenl/SPlanRa_Basis.xml"
    week_plan_rooms = "wdatenl/WPlanRa_{date}.xml"  # date must not be ""

    # timetable (/splan/)
    timetable_forms = "sdaten/splank.xml"
    timetable_teachers = "sdaten/splanl.xml"
    timetable_rooms = "sdaten/splanr.xml"


class IndiwareMobilEndpoint(abc.ABC):
    url: str
    vpdir_password: str  # usually mob[k|l|r]

    plan_file_url: str
    plan_file_url2: str
    vpinfo_url: str


class FormsIndiwareMobilEndpoint(IndiwareMobilEndpoint):
    vpdir_password = "mobk"
    plan_file_url = Endpoints.indiware_mobil_forms
    plan_file_url2 = Endpoints.indiware_mobil_forms2
    vpinfo_url = Endpoints.indiware_mobil_forms_vpinfo


class TeachersIndiwareMobilEndpoint(IndiwareMobilEndpoint):
    vpdir_password = "mobl"
    plan_file_url = Endpoints.indiware_mobil_teachers
    plan_file_url2 = Endpoints.indiware_mobil_teachers2
    vpinfo_url = Endpoints.indiware_mobil_teachers_vpinfo


class RoomsIndiwareMobilEndpoint(IndiwareMobilEndpoint):
    vpdir_password = "mobr"
    plan_file_url = Endpoints.indiware_mobil_rooms
    plan_file_url2 = Endpoints.indiware_mobil_rooms2
    vpinfo_url = Endpoints.indiware_mobil_rooms_vpinfo


class Stundenplan24FormsIndiwareMobilEndpoint(FormsIndiwareMobilEndpoint):
    def __init__(self, sp24_url: str):
        self.url = urllib.parse.urljoin(sp24_url, "mobil/")


class Stundenplan24TeachersIndiwareMobilEndpoint(TeachersIndiwareMobilEndpoint):
    def __init__(self, sp24_url: str):
        self.url = urllib.parse.urljoin(sp24_url, "moble/")


class Stundenplan24RoomsIndiwareMobilEndpoint(RoomsIndiwareMobilEndpoint):
    def __init__(self, sp24_url: str):
        self.url = urllib.parse.urljoin(sp24_url, "mobra/")


class SelfHostedIndiwareMobilEndpoint(IndiwareMobilEndpoint):
    @classmethod
    def create_forms_endpoint(cls, url: str):
        endpoint = FormsIndiwareMobilEndpoint()
        endpoint.url = url
        return endpoint

    @classmethod
    def create_teachers_endpoint(cls, url: str):
        endpoint = TeachersIndiwareMobilEndpoint()
        endpoint.url = url
        return endpoint

    @classmethod
    def create_rooms_endpoint(cls, url: str):
        endpoint = RoomsIndiwareMobilEndpoint()
        endpoint.url = url
        return endpoint


@dataclasses.dataclass
class IndiwareMobilEndpoints:
    forms: IndiwareMobilEndpoint | None
    teachers: IndiwareMobilEndpoint | None
    rooms: IndiwareMobilEndpoint | None

    @classmethod
    def from_stundenplan24(cls, sp24_url: str) -> IndiwareMobilEndpoints:
        return cls(
            forms=Stundenplan24FormsIndiwareMobilEndpoint(sp24_url),
            teachers=Stundenplan24TeachersIndiwareMobilEndpoint(sp24_url),
            rooms=Stundenplan24RoomsIndiwareMobilEndpoint(sp24_url)
        )

    @classmethod
    def deserialize(cls, data: dict[str, typing.Any] | str) -> IndiwareMobilEndpoints:
        if isinstance(data, str):
            return cls.from_stundenplan24(data)
        else:
            return cls(
                forms=SelfHostedIndiwareMobilEndpoint.create_forms_endpoint(url=data["students"]),
                teachers=SelfHostedIndiwareMobilEndpoint.create_teachers_endpoint(url=data["teachers"]),
                rooms=SelfHostedIndiwareMobilEndpoint.create_rooms_endpoint(url=data["rooms"])
            )


@dataclasses.dataclass
class Hosting:
    creds: dict[str, Credentials]

    indiware_mobil: IndiwareMobilEndpoints | None
    substitution_plan_students: str | None
    substitution_plan_teachers: str | None
    week_plan: str | None
    timetable: str | None

    @classmethod
    def deserialize(cls, data: dict[str, typing.Any]):
        creds = {type_: Credentials(**creds) for type_, creds in data["creds"].items()}
        endpoints = data["endpoints"]

        if isinstance(endpoints, str):
            indiware_mobil = IndiwareMobilEndpoints.deserialize(endpoints)
            substitution_plan_students = urllib.parse.urljoin(endpoints, "vplan/")
            substitution_plan_teachers = urllib.parse.urljoin(endpoints, "vplanle/")
            week_plan = urllib.parse.urljoin(endpoints, "wplan/")
            timetable = urllib.parse.urljoin(endpoints, "splan/")
        else:
            indiware_mobil = (
                IndiwareMobilEndpoints.deserialize(endpoints["indiware_mobil"])
                if "indiware_mobil" in endpoints else None
            )
            substitution_plan_students = endpoints.get("substitution_plan_students")
            substitution_plan_teachers = endpoints.get("substitution_plan_teachers")
            week_plan = endpoints.get("week_plan")
            timetable = endpoints.get("timetable")

        return cls(
            creds=creds,
            indiware_mobil=indiware_mobil,
            substitution_plan_students=substitution_plan_students,
            substitution_plan_teachers=substitution_plan_teachers,
            week_plan=week_plan,
            timetable=timetable
        )


class PlanClientError(Exception):
    pass


class NoPlanForDateError(PlanClientError):
    pass


class UnauthorizedError(PlanClientError):
    pass


class PlanClient(abc.ABC):
    def __init__(self, credentials: Credentials | None):
        self.credentials = credentials

    @abc.abstractmethod
    async def fetch_plan(self, date_or_filename: str | datetime.date | None = None) -> str:
        pass

    async def make_request(self, url: str, method: str = "GET", **kwargs) -> str:
        return await IndiwareStundenplanerClient.make_request(self.credentials, url, method, **kwargs)


class IndiwareMobilClient(PlanClient):
    def __init__(self, endpoint: IndiwareMobilEndpoint, credentials: Credentials | None):
        super().__init__(credentials)

        self.endpoint = endpoint

    async def fetch_plan(self, date_or_filename: str | datetime.date | None = None) -> str:
        if date_or_filename is None:
            _url = self.endpoint.plan_file_url2
        elif isinstance(date_or_filename, str):
            _url = Endpoints.indiware_mobil_file.format(filename=date_or_filename)
        elif isinstance(date_or_filename, datetime.date):
            _url = self.endpoint.plan_file_url.format(date=date_or_filename.strftime("%Y%m%d"))
        else:
            raise TypeError(f"date_or_filename must be str, datetime.date or None, not {type(date_or_filename)!r}.")

        url = urllib.parse.urljoin(self.endpoint.url, _url)

        try:
            return await self.make_request(url)
        except PlanClientError as e:
            if e.args[1] == 404:
                raise NoPlanForDateError(f"No plan for {date_or_filename=} found.") from e
            else:
                raise

    async def fetch_dates(self) -> dict[str, datetime.datetime]:
        url = urllib.parse.urljoin(self.endpoint.url, Endpoints.indiware_mobil_vpdir)

        with aiohttp.MultipartWriter("form-data") as mpwriter:
            # noinspection PyTypeChecker
            mpwriter.append(
                "I N D I W A R E",
                {"Content-Disposition": 'form-data; name="pw"'}
            )
            # noinspection PyTypeChecker
            mpwriter.append(
                self.endpoint.vpdir_password,
                {"Content-Disposition": 'form-data; name="art"'}
            )

        _out = (await self.make_request(url, method="POST", data=mpwriter)).split(";")

        out: dict[str, datetime.datetime] = {}
        for i in range(0, len(_out), 2):
            if not _out[i]:
                continue

            filename, date_str = _out[i:i + 2]

            out[filename] = datetime.datetime.strptime(date_str, "%d.%m.%Y %H:%M")

        return out


class SubstitutionPlanClient(PlanClient):
    def __init__(self, base_url: str, credentials: Credentials | None):
        super().__init__(credentials)

        self.base_url = base_url

    async def fetch_plan(self, date_or_filename: str | datetime.date | None = None) -> str:
        if date_or_filename is None:
            _url = Endpoints.substitution_plan2.format(date="")
        elif isinstance(date_or_filename, str):
            _url = Endpoints.substitution_plan.format(filename=date_or_filename)
        else:
            _url = Endpoints.substitution_plan2.format(date=date_or_filename.strftime("%Y%m%d"))

        url = urllib.parse.urljoin(self.base_url, _url)

        try:
            return await self.make_request(url)
        except PlanClientError as e:
            if e.args[1] == 404:
                raise NoPlanForDateError(f"No plan for {date_or_filename=} found.") from e
            else:
                raise


class IndiwareStundenplanerClient:
    def __init__(self, hosting: Hosting):
        self.hosting = hosting

        self.form_plan_client = IndiwareMobilClient(hosting.indiware_mobil.forms, hosting.creds.get("students"))
        self.teacher_plan_client = IndiwareMobilClient(hosting.indiware_mobil.teachers, hosting.creds.get("teachers"))
        self.room_plan_client = IndiwareMobilClient(hosting.indiware_mobil.rooms, hosting.creds.get("teachers"))

        self.students_substitution_plan_client = SubstitutionPlanClient(
            hosting.substitution_plan_students, hosting.creds.get("students")
        )
        self.teachers_substitution_plan_client = SubstitutionPlanClient(
            hosting.substitution_plan_teachers, hosting.creds.get("teachers")
        )

    @staticmethod
    async def make_request(creds: Credentials | None, url: str, method: str = "GET", **kwargs) -> str:
        auth = (
            aiohttp.BasicAuth(creds.username, creds.password)
            if creds is not None else None
        )

        async with aiohttp.ClientSession(headers={"User-Agent": "Indiware"}) as session:
            async with session.request(method, url, auth=auth, **kwargs) as response:
                if response.status == 401:
                    raise UnauthorizedError(f"Invalid credentials for request to {url=}.", response.status)
                if response.status != 200:
                    raise PlanClientError(f"Got status code {response.status} from {url!r}.", response.status)

                return await response.text(encoding="utf-8")

    @property
    def indiware_mobil_clients(self):
        return self.form_plan_client, self.teacher_plan_client, self.room_plan_client

    @property
    def substitution_plan_clients(self):
        return self.students_substitution_plan_client, self.teachers_substitution_plan_client
