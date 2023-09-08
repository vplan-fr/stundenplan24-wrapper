from __future__ import annotations

import dataclasses
import datetime
import json
import logging
import random
import typing
from pathlib import Path

import requests.exceptions

from .errors import NoProxyAvailableError

import aiohttp
import pubproxpy.errors


@dataclasses.dataclass
class _Proxy:
    auth: aiohttp.BasicAuth | None = None
    score: float = 1
    tries: int = 0

    last_worked: datetime.datetime | None = None
    last_blocked: datetime.datetime | None = None
    last_broken: datetime.datetime | None = None

    _last_outputted: datetime.datetime | None = None

    def serialize(self) -> dict:
        return {
            "auth": self.auth.encode() if self.auth is not None else None,
            "score": self.score,
            "tries": self.tries,
            "last_worked": self.last_worked.isoformat() if self.last_worked is not None else None,
            "last_blocked": self.last_blocked.isoformat() if self.last_blocked is not None else None,
            "last_broken": self.last_broken.isoformat() if self.last_broken is not None else None
        }

    @classmethod
    def deserialize(cls, data: dict) -> typing.Self:
        return cls(
            auth=aiohttp.BasicAuth.decode(data["auth"]) if data["auth"] is not None else None,
            score=data["score"],
            tries=data["tries"],
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
                ((s := key.rsplit(":", 1))[0], int(s[1])): _Proxy.deserialize(value)
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
        self._logger.debug(f"* Storing proxies at {str(self.cache_file)!r}.")
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
            except requests.exceptions.HTTPError as e:
                self._logger.warning(f"=> HTTP error: {e}")
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

        # if len(self.proxies) > 200:
        #     self._logger.info("=> More than 200 proxies, filtering.")
        #     for (url, port), proxy in self.proxies.proxies.copy().items():
        #         if proxy.functionality_score <= -5:
        #             self._logger.info(f"=> Removing {url!r}:{port!r} from proxy pool.")
        #             del self.proxies.proxies[url, port]

        proxy_fetcher = pubproxpy.ProxyFetcher(
            https=True,
            post=True,
            protocol=pubproxpy.Protocol.HTTP,
            time_to_connect=5
        )

        yield from self._fetch_proxies(proxy_fetcher)

    def iterate_proxies(self) -> typing.Generator[Proxy, None, None]:
        for _ in range(3):
            proxies = self.proxies.proxies.copy()

            while proxies:
                try:
                    [p_addr, _p], = random.choices(
                        population=list(proxies.items()),
                        weights=[p.score for addr, p in proxies.items()],
                        k=1
                    )
                except ValueError:
                    # total weight == 0
                    break
                del proxies[p_addr]

                # breakpoint()
                if _p.last_blocked and (datetime.datetime.now() - _p.last_blocked < datetime.timedelta(minutes=1)):
                    continue

                self._logger.log(logging.DEBUG - 2, f"Providing proxy {p_addr!r}. Score: {_p.score:.2f}.")
                yield Proxies._proxy_to_proxy(*p_addr, _p)

        self._logger.warning("Ran out of good proxies. Trying proxies marked as broken...")

        for p_addr, _p in self.proxies.proxies.items():
            if _p.score != 0:
                continue

            self._logger.log(logging.DEBUG - 2, f"Providing proxy {p_addr!r}. Score: {_p.score:.2f}.")
            yield Proxies._proxy_to_proxy(*p_addr, _p)

        yield from self.fetch_proxies()

        raise NoProxyAvailableError("No more proxies available.", None)

    def _update_save(self):
        n = 50
        self._i += 1

        if self._i == n:
            self.store_proxies()

        self._i %= n

    def mark_blocked(self, proxy: Proxy):
        self._logger.log(logging.DEBUG - 1, f"* Marking proxy {proxy!r} as blocked.")
        self.proxies._get_proxy(proxy.url, proxy.port).last_blocked = datetime.datetime.now()
        self._update_save()

    def mark_working(self, proxy: Proxy):
        self._logger.log(logging.DEBUG - 1, f"* Marking proxy {proxy!r} as working.")

        _proxy = self.proxies._get_proxy(proxy.url, proxy.port)
        _proxy.last_worked = datetime.datetime.now()
        effective_tries = min(_proxy.tries, 200)
        _proxy.score = (_proxy.score * effective_tries + 1) / (effective_tries + 1)
        _proxy.tries += 1

        self._update_save()

    def mark_broken(self, proxy: Proxy):
        self._logger.log(logging.DEBUG - 1, f"* Marking proxy {proxy!r} as broken.")

        _proxy = self.proxies._get_proxy(proxy.url, proxy.port)
        _proxy.last_broken = datetime.datetime.now()
        effective_tries = min(_proxy.tries, 200)
        _proxy.score = (_proxy.score * effective_tries) / (effective_tries + 1)
        _proxy.tries += 1

        self._update_save()
