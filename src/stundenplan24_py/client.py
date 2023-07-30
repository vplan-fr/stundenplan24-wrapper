from __future__ import annotations

import abc
import dataclasses
import datetime
import urllib.parse
import email.utils
import typing
import asyncio

import aiohttp as aiohttp

from .endpoints import *

__all__ = [
    "Credentials",
    "Hosting",
    "PlanClientError",
    "PlanNotFoundError",
    "UnauthorizedError",
    "NotModifiedError",
    "PlanResponse",
    "PlanClient",
    "IndiwareMobilClient",
    "SubstitutionPlanClient",
    "IndiwareStundenplanerClient"
]

_DELAY_BETWEEN_REQUESTS = 0
REQUEST_LOCK = asyncio.Lock()


def set_min_delay_between_requests(delay_seconds: float):
    global _DELAY_BETWEEN_REQUESTS
    _DELAY_BETWEEN_REQUESTS = delay_seconds


def get_min_delay_between_requests() -> float:
    return _DELAY_BETWEEN_REQUESTS


@dataclasses.dataclass
class Credentials:
    username: str
    password: str


@dataclasses.dataclass
class Hosting:
    creds: dict[str, Credentials]

    indiware_mobil: IndiwareMobilEndpoints
    substitution_plan: SubstitutionPlanEndpoints
    week_plan: str | None
    timetable: str | None

    @classmethod
    def deserialize(cls, data: dict[str, typing.Any]):
        creds = {type_: Credentials(**creds) for type_, creds in data["creds"].items()}
        endpoints = data["endpoints"]

        if isinstance(endpoints, str):
            indiware_mobil = IndiwareMobilEndpoints.from_stundenplan24(endpoints)
            substitution_plan = SubstitutionPlanEndpoints.from_stundenplan24(endpoints)
            week_plan = urllib.parse.urljoin(endpoints, "wplan/")
            timetable = urllib.parse.urljoin(endpoints, "splan/")
        else:
            indiware_mobil = (
                IndiwareMobilEndpoints.deserialize(endpoints["indiware_mobil"])
                if "indiware_mobil" in endpoints else IndiwareMobilEndpoints()
            )
            substitution_plan = (
                SubstitutionPlanEndpoints.deserialize(endpoints["substitution_plan"])
                if "substitution_plan" in endpoints else SubstitutionPlanEndpoints()
            )
            week_plan = endpoints.get("week_plan")
            timetable = endpoints.get("timetable")

        return cls(
            creds=creds,
            indiware_mobil=indiware_mobil,
            substitution_plan=substitution_plan,
            week_plan=week_plan,
            timetable=timetable
        )


class PlanClientError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class PlanNotFoundError(PlanClientError):
    pass


class UnauthorizedError(PlanClientError):
    pass


class NotModifiedError(PlanClientError):
    pass


@dataclasses.dataclass
class PlanResponse:
    content: str
    response: aiohttp.ClientResponse

    @property
    def last_modified(self) -> datetime.datetime | None:
        if "Last-Modified" in self.response.headers:
            return email.utils.parsedate_to_datetime(self.response.headers["Last-Modified"])
        else:
            return None

    @property
    def etag(self) -> str | None:
        return self.response.headers.get("ETag", None)


class PlanClientRequestContextManager:
    def __init__(self, aiohttp_request_context_manager: aiohttp.client._RequestContextManager, no_delay: bool = False):
        self.context_manager = aiohttp_request_context_manager
        self.no_delay = no_delay

    async def __aenter__(self):
        if not self.no_delay:
            await REQUEST_LOCK.acquire()

        response = await self.context_manager.__aenter__()

        if not self.no_delay:
            async def release_lock():
                await asyncio.sleep(_DELAY_BETWEEN_REQUESTS)
                REQUEST_LOCK.release()

            asyncio.create_task(release_lock())

        if response.status == 401:
            raise UnauthorizedError(f"Invalid credentials for request to {response.url!r}.", response.status)
        elif response.status == 304:
            raise NotModifiedError(f"The requested ressource on {response.url!r} has not been modified since.",
                                   response.status)

        return response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.context_manager.__aexit__(exc_type, exc_val, exc_tb)


class PlanClient(abc.ABC):
    def __init__(self, credentials: Credentials | None, session: aiohttp.ClientSession | None = None,
                 no_delay: bool = False):
        self.credentials = credentials
        self.session = aiohttp.ClientSession() if session is None else session
        self.no_delay = no_delay

    @abc.abstractmethod
    async def fetch_plan(self, date_or_filename: str | datetime.date | None = None,
                         if_modified_since: datetime.datetime | None = None) -> PlanResponse:
        ...

    def make_request(
            self,
            url: str,
            method: str = "GET",
            if_modified_since: datetime.datetime | None = None,
            if_none_match: str | None = None,
            **kwargs
    ) -> PlanClientRequestContextManager:
        auth = (
            aiohttp.BasicAuth(self.credentials.username, self.credentials.password)
            if self.credentials is not None else None
        )

        kwargs = dict(
            method=method,
            url=url,
            auth=auth,
            **kwargs
        )

        if_modified_since_header = {"If-Modified-Since": (
            if_modified_since.astimezone(datetime.timezone.utc).strftime("%a, %d %b %Y %H:%M:%S GMT")
        )} if if_modified_since is not None else {}

        if_none_match_header = {"If-None-Match": if_none_match} if if_none_match is not None else {}

        kwargs["headers"] = (
                {"User-Agent": "Indiware"}
                | if_modified_since_header
                | if_none_match_header
                | kwargs.get("headers", {})
        )

        return PlanClientRequestContextManager(self.session.request(**kwargs), no_delay=self.no_delay)

    async def close(self):
        await self.session.close()


class IndiwareMobilClient(PlanClient):
    def __init__(self, endpoint: IndiwareMobilEndpoint, credentials: Credentials | None,
                 session: aiohttp.ClientSession | None = None, no_delay=True):
        super().__init__(credentials, session, no_delay)

        self.endpoint = endpoint

    async def fetch_plan(
            self,
            date_or_filename: str | datetime.date | None = None,
            **kwargs
    ) -> PlanResponse:
        if date_or_filename is None:
            _url = self.endpoint.plan_file_url2
        elif isinstance(date_or_filename, str):
            _url = Endpoints.indiware_mobil_file.format(filename=date_or_filename)
        elif isinstance(date_or_filename, datetime.date):
            _url = self.endpoint.plan_file_url.format(date=date_or_filename.strftime("%Y%m%d"))
        else:
            raise TypeError(f"date_or_filename must be str, datetime.date or None, not {type(date_or_filename)!r}.")

        url = urllib.parse.urljoin(self.endpoint.url, _url)

        async with self.make_request(url, **kwargs) as response:
            if response.status == 404:
                raise PlanNotFoundError(f"No plan for {date_or_filename=} found.", response.status)
            elif response.status != 200:
                raise PlanClientError(f"Unexpected status code {response.status} for request to {url=}.",
                                      response.status)

            return PlanResponse(
                content=await response.text(encoding="utf-8"),
                response=response
            )

    async def fetch_dates(self, **kwargs) -> dict[str, datetime.datetime]:
        """Return a dictionary of available file names and their last modification date."""

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

        async with self.make_request(url, method="POST", data=mpwriter, **kwargs) as response:
            if response.status != 200:
                raise PlanClientError(f"Unexpected status code {response.status} for request to {url=}.",
                                      response.status)

            _out = (await response.text(encoding="utf-8")).split(";")

        out: dict[str, datetime.datetime] = {}
        for i in range(0, len(_out), 2):
            if not _out[i]:
                continue

            filename, date_str = _out[i:i + 2]

            out[filename] = (
                datetime.datetime.strptime(date_str, "%d.%m.%Y %H:%M")
                .replace(tzinfo=datetime.timezone.utc)
            )

        return out


class SubstitutionPlanClient(PlanClient):
    def __init__(self, endpoint: SubstitutionPlanEndpoint, credentials: Credentials | None,
                 session: aiohttp.ClientSession | None = None, no_delay=False):
        super().__init__(credentials, session, no_delay)

        self.endpoint = endpoint

    def get_url(self, date_or_filename: str | datetime.date | None = None) -> str:
        if date_or_filename is None:
            _url = self.endpoint.plan_file_url2.format(date="")
        elif isinstance(date_or_filename, str):
            _url = Endpoints.substitution_plan.format(filename=date_or_filename)
        else:
            _url = self.endpoint.plan_file_url2.format(date=date_or_filename.strftime("%Y%m%d"))

        return urllib.parse.urljoin(self.endpoint.url, _url)

    async def fetch_plan(
            self,
            date_or_filename: str | datetime.date | None = None,
            **kwargs
    ) -> PlanResponse:
        url = self.get_url(date_or_filename)

        async with self.make_request(url, **kwargs) as response:
            if response.status == 404:
                raise PlanNotFoundError(f"No plan for {date_or_filename=} found.", response.status)
            elif response.status != 200:
                raise PlanClientError(f"Unexpected status code {response.status} for request to {url=}.",
                                      response.status)

            return PlanResponse(
                content=await response.text(encoding="utf-8"),
                response=response
            )

    async def get_metadata(self, date_or_filename: str | datetime.date | None = None) -> tuple[datetime.datetime, str]:
        url = self.get_url(date_or_filename)

        async with self.make_request(url, method="HEAD") as response:
            if response.status == 404:
                raise PlanNotFoundError(f"No plan for {date_or_filename=} found.", response.status)
            elif response.status != 200:
                raise PlanClientError(f"Unexpected status code {response.status} for request to {url=}.",
                                      response.status)

            plan_response = PlanResponse("", response)

            return plan_response.last_modified, plan_response.etag


class IndiwareStundenplanerClient:
    def __init__(self, hosting: Hosting, session: aiohttp.ClientSession | None = None):
        self.hosting = hosting

        self.form_plan_client = (
            IndiwareMobilClient(hosting.indiware_mobil.forms, hosting.creds.get("students"), session=session)
            if hosting.indiware_mobil.forms is not None else None
        )
        self.teacher_plan_client = (
            IndiwareMobilClient(hosting.indiware_mobil.teachers, hosting.creds.get("teachers"), session=session)
            if hosting.indiware_mobil.teachers is not None else None
        )
        self.room_plan_client = (
            IndiwareMobilClient(hosting.indiware_mobil.rooms, hosting.creds.get("teachers"), session=session)
            if hosting.indiware_mobil.rooms is not None else None
        )

        self.students_substitution_plan_client = SubstitutionPlanClient(
            hosting.substitution_plan.students, hosting.creds.get("students"), session=session
        ) if hosting.substitution_plan.students is not None else None
        self.teachers_substitution_plan_client = SubstitutionPlanClient(
            hosting.substitution_plan.teachers, hosting.creds.get("teachers"), session=session
        ) if hosting.substitution_plan.teachers is not None else None

    @property
    def indiware_mobil_clients(self):
        return filter(
            lambda x: x is not None,
            (self.form_plan_client, self.teacher_plan_client, self.room_plan_client)
        )

    @property
    def substitution_plan_clients(self):
        return filter(
            lambda x: x is not None,
            (self.students_substitution_plan_client, self.teachers_substitution_plan_client)
        )

    async def close(self):
        await asyncio.gather(*(
                [client.close() for client in self.indiware_mobil_clients]
                + [client.close() for client in self.substitution_plan_clients]
        ))
