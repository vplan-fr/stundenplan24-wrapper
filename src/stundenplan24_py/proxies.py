from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import typing
from pathlib import Path

from .client import PlanClientError

import aiohttp
import pubproxpy.errors


@dataclasses.dataclass
class _Proxy:
    auth: aiohttp.BasicAuth | None = None
    functionality_score: int = 1

    last_worked: datetime.datetime | None = None
    last_blocked: datetime.datetime | None = None
    last_broken: datetime.datetime | None = None

    def serialize(self) -> dict:
        return {
            "auth": self.auth.encode() if self.auth is not None else None,
            "functionality_score": self.functionality_score,
            "last_worked": self.last_worked.isoformat() if self.last_worked is not None else None,
            "last_blocked": self.last_blocked.isoformat() if self.last_blocked is not None else None,
            "last_broken": self.last_broken.isoformat() if self.last_broken is not None else None
        }

    @classmethod
    def deserialize(cls, data: dict) -> typing.Self:
        return cls(
            auth=aiohttp.BasicAuth.decode(data["auth"]) if data["auth"] is not None else None,
            functionality_score=data["functionality_score"],
            last_worked=datetime.datetime.fromisoformat(data["last_worked"]) if data["last_worked"] else None,
            last_blocked=datetime.datetime.fromisoformat(data["last_blocked"]) if data["last_blocked"] else None,
            last_broken=datetime.datetime.fromisoformat(data["last_broken"]) if data["last_broken"] else None,
        )


@dataclasses.dataclass
class Proxy:
    url: str
    port: int
    auth: aiohttp.BasicAuth | None = None


@dataclasses.dataclass
class Proxies:
    proxies: dict[tuple[str, int], _Proxy]

    def serialize(self) -> dict:
        return {
            "proxies": {f"{url}:{port}": proxy.serialize() for (url, port), proxy in self.proxies.items()}
        }

    @classmethod
    def deserialize(cls, data: dict) -> Proxies:
        return cls(
            proxies={
                tuple(map(str.strip, key.rsplit(":", 1))): _Proxy.deserialize(value)
                for key, value in data["proxies"].items()
            }
        )

    def _get_proxy(self, url: str, port: int) -> _Proxy:
        return self.proxies[url, port]

    @staticmethod
    def _proxy_to_proxy(url: str, port: int, proxy: _Proxy) -> Proxy:
        return Proxy(url, port, proxy.auth)

    def get_proxy(self, url: str, port: int) -> Proxy:
        return self._proxy_to_proxy(url, port, self._get_proxy(url, port))

    def add_proxy(self, proxy: Proxy):
        self.proxies[proxy.url, proxy.port] = _Proxy(proxy.auth)

    def __len__(self):
        return len(self.proxies)


class NoProxyAvailableError(PlanClientError):
    pass


class ProxyProvider:
    def __init__(self, cache_file: Path):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.cache_file = cache_file

        self.proxies: Proxies = Proxies(proxies={})

        self._i = 0

        self.load_proxies()

    def load_proxies(self):
        self._logger.info("* Loading proxies.")
        try:
            data = json.loads(self.cache_file.read_text("utf-8"))
        except FileNotFoundError:
            self._logger.info("=> No proxies cached yet.")
        except json.JSONDecodeError:
            self._logger.warning("=> Invalid proxy cache file.")
        else:
            self.proxies = Proxies.deserialize(data)

            self._logger.info(f"=> Loaded {len(self.proxies)} proxies.")

    def store_proxies(self):
        self._logger.info(f"* Storing proxies at {str(self.cache_file)!r}.")
        self.cache_file.write_text(json.dumps(self.proxies.serialize()), "utf-8")

    def _fetch_proxies(self, proxy_fetcher: pubproxpy.ProxyFetcher) -> typing.Generator[Proxy, None, None]:
        while True:
            try:
                _proxies = proxy_fetcher.get() + proxy_fetcher.drain()
                _proxies: list[str]
            except pubproxpy.errors.DailyLimitError:
                self._logger.info("=> Daily request limit reached.")
                break
            except pubproxpy.errors.RateLimitError:
                self._logger.info("=> Rate limit reached. :(")
                break
            else:
                new = []
                for _proxy in _proxies:
                    url, port = _proxy.rsplit(":", 1)

                    if (url, port) in self.proxies.proxies:
                        self._logger.info(f"=> Fetched proxy {url!r}:{port!r} is already in the pool.")
                        continue

                    self._logger.info(f"=> Adding {url!r}:{port!r} to proxy pool.")

                    proxy = Proxy(
                        url=url,
                        port=port,
                        auth=None
                    )

                    self.proxies.add_proxy(proxy)
                    new.append(proxy)

                self.store_proxies()
                yield from new

    def fetch_proxies(self) -> typing.Generator[Proxy, None, None]:
        self._logger.info(f"* Fetching proxies from {getattr(pubproxpy.ProxyFetcher, '_BASE_URI', 'PubProxy')!r}.")

        if len(self.proxies) > 200:
            self._logger.info("=> More than 200 proxies, filtering.")
            for (url, port), proxy in self.proxies.proxies.copy().items():
                if proxy.functionality_score <= -5:
                    self._logger.info(f"=> Removing {url!r}:{port!r} from proxy pool.")
                    del self.proxies.proxies[url, port]

        proxy_fetcher = pubproxpy.ProxyFetcher(
            https=True,
            post=True,
            protocol=pubproxpy.Protocol.HTTP,
            time_to_connect=5
        )

        yield from self._fetch_proxies(proxy_fetcher)

    def iterate_proxies(self) -> typing.Generator[Proxy, None, None]:
        all_proxies = list(self.proxies.proxies.items())

        all_proxies.sort(key=lambda proxy: proxy[1].last_blocked or datetime.datetime.min)

        working = filter(lambda proxy: proxy[1].functionality_score > 0, all_proxies)
        not_working = filter(lambda proxy: proxy[1].functionality_score <= 0, all_proxies)

        yield from map(lambda p: Proxies._proxy_to_proxy(*p[0], p[1]), working)
        yield from map(lambda p: Proxies._proxy_to_proxy(*p[0], p[1]), not_working)

        try:
            yield from self.fetch_proxies()
        except pubproxpy.errors.ProxyError as e:
            raise NoProxyAvailableError from e

    def _update_save(self):
        n = 10
        self._i += 1

        if self._i > n:
            self.store_proxies()

        self._i %= n

    def mark_blocked(self, proxy: Proxy):
        self.proxies._get_proxy(proxy.url, proxy.port).last_blocked = datetime.datetime.now()
        self._update_save()

    def mark_working(self, proxy: Proxy):
        self.proxies._get_proxy(proxy.url, proxy.port).last_worked = datetime.datetime.now()
        self.proxies._get_proxy(proxy.url, proxy.port).functionality_score += 1
        self._update_save()

    def mark_broken(self, proxy: Proxy):
        self.proxies._get_proxy(proxy.url, proxy.port).last_broken = datetime.datetime.now()
        self.proxies._get_proxy(proxy.url, proxy.port).functionality_score -= 1
        self._update_save()
