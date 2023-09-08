from __future__ import annotations


class PlanClientError(Exception):
    def __init__(self, message: str, status_code: int | None):
        super().__init__(message)
        self.status_code = status_code


class PlanNotFoundError(PlanClientError):
    pass


class UnauthorizedError(PlanClientError):
    pass


class NotModifiedError(PlanClientError):
    pass


class NoProxyAvailableError(PlanClientError):
    pass
