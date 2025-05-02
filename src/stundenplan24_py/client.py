from __future__ import annotations

import abc
import concurrent.futures
import dataclasses
import datetime
import urllib.parse
import email.utils
import typing
import asyncio
import logging

import curl_cffi.requests

import pipifax_proxy_manager

from .endpoints import *
from .errors import PlanClientError, PlanNotFoundError, UnauthorizedError, NotModifiedError

logging.getLogger("charset_normalizer").propagate = False

__all__ = [
    "Credentials",
    "Hosting",
    "PlanResponse",
    "PlanClient",
    "IndiwareMobilClient",
    "SubstitutionPlanClient",
    "IndiwareStundenplanerClient"
]


@dataclasses.dataclass
class Credentials:
    username: str
    password: str


@dataclasses.dataclass
class Hosting:
    creds: Credentials

    indiware_mobil: IndiwareMobilEndpoints
    substitution_plan: SubstitutionPlanEndpoints
    week_plan: str | None
    timetable: str | None

    @classmethod
    def deserialize(cls, data: dict[str, typing.Any]):
        creds = Credentials(**data["creds"]) if data.get("creds") else None
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


@dataclasses.dataclass
class PlanResponse:
    content: str
    response: curl_cffi.Response

    @property
    def last_modified(self) -> datetime.datetime | None:
        if "Last-Modified" in self.response.headers:
            return email.utils.parsedate_to_datetime(self.response.headers["Last-Modified"])
        else:
            return None

    @property
    def etag(self) -> str | None:
        return self.response.headers.get("ETag", None)


def _do_request(session, request_kwargs, proxy_url):
    return session.request(
        **request_kwargs,
        proxies={
            "http": proxy_url,
            "https": proxy_url
        } if proxy_url is not None else None,
        timeout=5,
    )


class PlanClient(abc.ABC):
    def __init__(self, credentials: Credentials | None,
                 proxied_session: pipifax_proxy_manager.ProxiedSession | None = None,
                 request_executor: concurrent.futures.Executor | None = None):
        self.credentials = credentials
        self.proxied_session = proxied_session
        self.request_executor = (
            concurrent.futures.ThreadPoolExecutor() if request_executor is None else request_executor
        )

    @abc.abstractmethod
    async def fetch_plan(self, date_or_filename: str | datetime.date | None = None,
                         if_modified_since: datetime.datetime | None = None) -> PlanResponse:
        ...

    async def make_request(
        self,
        url: str,
        method: str = "GET",
        if_modified_since: datetime.datetime | None = None,
        if_none_match: str | None = None,
        **kwargs
    ):
        kwargs = dict(
            method=method,
            url=url,
            auth=(self.credentials.username, self.credentials.password)
            if self.credentials is not None else None,
            timeout=8,
        ) | kwargs

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

        if self.proxied_session is None:
            response = await asyncio.get_event_loop().run_in_executor(
                self.request_executor,
                lambda: curl_cffi.requests.request(**kwargs)
            )
        else:
            def handler(fut, proxy, i):
                try:
                    response = fut.result()
                except curl_cffi.requests.exceptions.RequestException:
                    raise pipifax_proxy_manager.RetryError

                response._num_proxy_tries = i + 1
                # print(response.text)
                return response

            response = await asyncio.get_event_loop().run_in_executor(
                self.request_executor,
                lambda: self.proxied_session.request(
                    handler=handler,
                    anonymity_level="anonymous",
                    rotation_rate=60,
                    curl_kwargs=kwargs,
                    reason="https://stundenplan24.de"
                )
            )

        if response.status_code == 401:
            raise UnauthorizedError(
                f"Invalid credentials for request to {response.url!r}.",
                response.status_code
            )
        elif response.status_code == 304:
            raise NotModifiedError(
                f"The requested ressource at {response.url!r} has not been modified since.",
                response.status_code
            )
        else:
            return response


class IndiwareMobilClient(PlanClient):
    def __init__(self, endpoint: IndiwareMobilEndpoint, credentials: Credentials | None):
        super().__init__(credentials)

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

        response = await self.make_request(url, **kwargs)

        if response.status_code == 404:
            raise PlanNotFoundError(f"No plan for {date_or_filename=} found.", response.status_code)
        elif response.status_code != 200:
            raise PlanClientError(f"Unexpected status code {response.status_code} for request to {url=}.",
                                  response.status_code)

        return PlanResponse(
            content=response.text,
            response=response
        )

    async def fetch_dates(self, **kwargs) -> dict[str, datetime.datetime]:
        """Return a dictionary of available file names and their last modification date."""

        url = urllib.parse.urljoin(self.endpoint.url, Endpoints.indiware_mobil_vpdir)

        multipart_dict = curl_cffi.CurlMime.from_list(
            [
                {
                    "name": "pw",
                    "data": b"I N D I W A R E",

                },
                {
                    "name": "art",
                    "data": self.endpoint.vpdir_password.encode()
                }
            ]
        )

        response = await self.make_request(url, method="POST", multipart=multipart_dict, **kwargs)

        if response.status_code != 200:
            raise PlanClientError(f"Unexpected status code {response.status_code} for request to {url=}.",
                                  response.status_code)

        _out = response.text.split(";")

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
    def __init__(self, endpoint: SubstitutionPlanEndpoint, credentials: Credentials | None):
        super().__init__(credentials)

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

        response = await self.make_request(url, **kwargs)

        if response.status_code == 404:
            raise PlanNotFoundError(f"No plan for {date_or_filename=} found.", response.status_code)
        elif response.status_code != 200:
            raise PlanClientError(f"Unexpected status code {response.status_code} for request to {url=}.",
                                  response.status_code)

        return PlanResponse(
            content=response.text,
            response=response
        )

    async def get_metadata(self, date_or_filename: str | datetime.date | None = None) -> tuple[
        datetime.datetime, str]:
        url = self.get_url(date_or_filename)

        response = await self.make_request(url, method="HEAD")

        if response.status_code == 404:
            raise PlanNotFoundError(f"No plan for {date_or_filename=} found.", response.status_code)
        elif response.status_code != 200:
            raise PlanClientError(f"Unexpected status code {response.status_code} for request to {url=}.",
                                  response.status_code)

        plan_response = PlanResponse("", response)

        return plan_response.last_modified, plan_response.etag


class IndiwareStundenplanerClient:
    def __init__(self, hosting: Hosting):
        self.hosting = hosting

        self.form_plan_client = (
            IndiwareMobilClient(hosting.indiware_mobil.forms, hosting.creds)
            if hosting.indiware_mobil.forms is not None else None
        )
        self.teacher_plan_client = (
            IndiwareMobilClient(hosting.indiware_mobil.teachers, hosting.creds)
            if hosting.indiware_mobil.teachers is not None else None
        )
        self.room_plan_client = (
            IndiwareMobilClient(hosting.indiware_mobil.rooms, hosting.creds)
            if hosting.indiware_mobil.rooms is not None else None
        )

        self.students_substitution_plan_client = SubstitutionPlanClient(
            hosting.substitution_plan.students, hosting.creds
        ) if hosting.substitution_plan.students is not None else None
        self.teachers_substitution_plan_client = SubstitutionPlanClient(
            hosting.substitution_plan.teachers, hosting.creds
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
