from . import codes


class ApiError(Exception):
    """业务异常：默认 HTTP 200 + 业务 code，符合 BigTrans 前端契约。"""

    def __init__(self, code: int = codes.BAD_REQUEST, message: str = "操作失败", http_status: int = 200):
        super().__init__(message)
        self.code = code
        self.message = message
        self.http_status = http_status


def bad_request(message: str = "参数错误") -> ApiError:
    return ApiError(codes.BAD_REQUEST, message)


def not_found(message: str = "数据不存在") -> ApiError:
    return ApiError(codes.NOT_FOUND, message)


def unauthorized(message: str = "登录已失效，请重新登录") -> ApiError:
    return ApiError(codes.LOGIN_EXPIRED, message)


def forbidden(message: str = "无权限") -> ApiError:
    return ApiError(codes.FORBIDDEN, message)
