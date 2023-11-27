from __future__ import annotations

import abc
import concurrent.futures
import dataclasses
import datetime
import http.client
import urllib.parse
import email.utils
import typing
import asyncio
import logging

import requests.auth
import urllib3.fields
import urllib3.exceptions
import urllib3.connection

from .endpoints import *
from .errors import PlanClientError, PlanNotFoundError, UnauthorizedError, NotModifiedError
from . import proxies

logging.getLogger("urllib3").setLevel(logging.CRITICAL)
logging.getLogger("urllib3").propagate = False
logging.getLogger("charset_normalizer").setLevel(logging.CRITICAL)
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
    response: requests.Response

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


class PlanClientRequestContextManager:
    def __init__(self, session: requests.Session, request_kwargs: dict[str, typing.Any], no_delay: bool = False,
                 proxy_provider: proxies.ProxyProvider | None = None):
        self.session = session
        self.request_kwargs = request_kwargs
        self.no_delay = no_delay
        self.proxy_provider = proxy_provider

    async def __aenter__(self):
        if not self.no_delay:
            await REQUEST_LOCK.acquire()

        try:
            _num_proxy_tries = 0

            for proxy in self.proxy_provider.iterate_proxies() if self.proxy_provider is not None else [None]:
                _num_proxy_tries += 1

                proxy_url = str(urllib3.util.Url(
                    host=proxy.url,
                    auth=f"{proxy.auth.login}:{proxy.auth.password}" if proxy.auth is not None else None,
                    port=proxy.port,
                    scheme="http"
                )) if proxy is not None else None

                try:
                    response = await asyncio.get_running_loop().run_in_executor(
                        _thread_pool_executor,
                        _do_request, self.session, self.request_kwargs, proxy_url
                    )
                except (TimeoutError, requests.exceptions.ReadTimeout, requests.exceptions.ProxyError,
                        requests.exceptions.SSLError) as e:
                    if self.proxy_provider:
                        self.proxy_provider.mark_broken(proxy)
                        continue
                    else:
                        raise
                except requests.ConnectionError as e:
                    if not self.proxy_provider:
                        raise
                    match e:
                        # @formatter:off
                        case (
                            requests.ConnectTimeout(
                                args=(urllib3.exceptions.MaxRetryError(
                                    reason=urllib3.exceptions.ConnectTimeoutError(
                                        args=(urllib3.connection.HTTPSConnection(host=proxy.url), _))), ))
                        ):
                            # @formatter:on
                            self.proxy_provider.mark_broken(proxy)
                            continue
                        # @formatter:off
                        case (
                            requests.ConnectionError(
                                args=(urllib3.exceptions.ProtocolError(
                                    args=(_, http.client.RemoteDisconnected())),))
                        ):
                            # @formatter:on
                            self.proxy_provider.mark_broken(proxy)
                            continue
                        case (
                            requests.ConnectionError(
                                args=(urllib3.exceptions.ProtocolError(
                                    args=(_, ConnectionResetError())),))
                        ):
                            # @formatter:on
                            self.proxy_provider.mark_broken(proxy)
                            continue

                        case _:
                            raise

                else:
                    if self.proxy_provider:
                        self.proxy_provider.mark_working(proxy)

                    if response.status_code == 401:
                        raise UnauthorizedError(f"Invalid credentials for request to {response.url!r}.",
                                                response.status_code)
                    elif response.status_code == 304:
                        raise NotModifiedError(
                            f"The requested ressource at {response.url!r} has not been modified since.",
                            response.status_code)

                    response.encoding = "utf-8"  # who thought it's a good idea to g
                    response._num_proxy_tries = _num_proxy_tries
                    return response
        finally:
            if not self.no_delay:
                async def release_lock():
                    await asyncio.sleep(_DELAY_BETWEEN_REQUESTS)
                    REQUEST_LOCK.release()

                asyncio.create_task(release_lock())

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


_thread_pool_executor = concurrent.futures.ProcessPoolExecutor()


class PlanClient(abc.ABC):
    def __init__(self, credentials: Credentials | None, session: requests.Session | None = None,
                 no_delay: bool = False, proxy_provider: proxies.ProxyProvider | None = None):
        self.credentials = credentials
        self.session = requests.Session() if session is None else session
        self.no_delay = no_delay
        self.proxy_provider = proxy_provider

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
        kwargs = dict(
            method=method,
            url=url,
            auth=requests.auth.HTTPBasicAuth(self.credentials.username, self.credentials.password)
            if self.credentials is not None else None,
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

        return PlanClientRequestContextManager(
            self.session,
            kwargs,
            no_delay=self.no_delay,
            proxy_provider=self.proxy_provider
        )

    async def close(self):
        self.session.close()


class IndiwareMobilClient(PlanClient):
    def __init__(self, endpoint: IndiwareMobilEndpoint, credentials: Credentials | None,
                 session: requests.Session | None = None, no_delay=True):
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

        multipart_dict = {
            "pw": (None, "I N D I W A R E"),
            "art": (None, self.endpoint.vpdir_password)
        }

        async with self.make_request(url, method="POST", files=multipart_dict, **kwargs) as response:
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
    def __init__(self, endpoint: SubstitutionPlanEndpoint, credentials: Credentials | None,
                 session: requests.Session | None = None, no_delay=False):
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
            if response.status_code == 404:
                raise PlanNotFoundError(f"No plan for {date_or_filename=} found.", response.status_code)
            elif response.status_code != 200:
                raise PlanClientError(f"Unexpected status code {response.status_code} for request to {url=}.",
                                      response.status_code)

            return PlanResponse(
                content=response.text,
                response=response
            )

    async def get_metadata(self, date_or_filename: str | datetime.date | None = None) -> tuple[datetime.datetime, str]:
        url = self.get_url(date_or_filename)

        async with self.make_request(url, method="HEAD") as response:
            if response.status_code == 404:
                raise PlanNotFoundError(f"No plan for {date_or_filename=} found.", response.status_code)
            elif response.status_code != 200:
                raise PlanClientError(f"Unexpected status code {response.status_code} for request to {url=}.",
                                      response.status_code)

            plan_response = PlanResponse("", response)

            return plan_response.last_modified, plan_response.etag


class IndiwareStundenplanerClient:
    def __init__(self, hosting: Hosting, session: requests.Session | None = None):
        self.hosting = hosting

        self.form_plan_client = (
            IndiwareMobilClient(hosting.indiware_mobil.forms, hosting.creds, session=session)
            if hosting.indiware_mobil.forms is not None else None
        )
        self.teacher_plan_client = (
            IndiwareMobilClient(hosting.indiware_mobil.teachers, hosting.creds, session=session)
            if hosting.indiware_mobil.teachers is not None else None
        )
        self.room_plan_client = (
            IndiwareMobilClient(hosting.indiware_mobil.rooms, hosting.creds, session=session)
            if hosting.indiware_mobil.rooms is not None else None
        )

        self.students_substitution_plan_client = SubstitutionPlanClient(
            hosting.substitution_plan.students, hosting.creds, session=session
        ) if hosting.substitution_plan.students is not None else None
        self.teachers_substitution_plan_client = SubstitutionPlanClient(
            hosting.substitution_plan.teachers, hosting.creds, session=session
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
