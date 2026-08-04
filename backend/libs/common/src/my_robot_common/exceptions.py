from __future__ import annotations


class AppException(Exception):
    """统一业务异常，由 app_factory 的异常处理器转成 JSON。"""

    def __init__(
        self,
        status_code: int = 400,
        code: str = "bad_request",
        message: str = "Bad Request",
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)
