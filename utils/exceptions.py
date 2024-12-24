"""
----------------------------------------------------------------
File name:                  exceptions.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理池系统自定义异常模块
----------------------------------------------------------------

Changed history:            定义系统特定异常类型
                            2024/12/24: 增加异常处理机制和错误码
----------------------------------------------------------------
"""
from typing import Optional, Dict, Any
from enum import Enum


class ErrorCode(Enum):
    """
    错误码枚举
    """
    # 系统级错误 (1000-1999)
    SYSTEM_ERROR = 1000
    CONFIG_ERROR = 1001
    NETWORK_ERROR = 1002

    # 代理池错误 (2000-2999)
    POOL_EMPTY = 2000
    POOL_FULL = 2001
    PROXY_EXISTS = 2002
    PROXY_NOT_FOUND = 2003

    # 代理验证错误 (3000-3999)
    VALIDATION_TIMEOUT = 3000
    VALIDATION_FAILED = 3001
    MAX_RETRIES_EXCEEDED = 3002

    # 代理获取错误 (4000-4999)
    FETCH_TIMEOUT = 4000
    FETCH_FAILED = 4001
    SOURCE_ERROR = 4002

    # Redis 操作错误 (5000-5999)
    REDIS_CONNECTION_ERROR = 5000
    REDIS_OPERATION_ERROR = 5001

    # 配置错误 (6000-6999)
    INVALID_CONFIG = 6000
    CONFIG_FILE_ERROR = 6001

    def __str__(self):
        return f"{self.name}({self.value})"


class ProxyPoolError(Exception):
    """
    代理池基础异常类

    作为所有自定义异常的基类

    Attributes:
        code: 错误码
        message: 错误消息
        details: 详细信息
    """
    def __init__(
            self,
            code: ErrorCode,
            message: str,
            details: Optional[Dict[str, Any]] = None
    ):
        self.code = code
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

    def __str__(self):
        return f"{self.code}: {self.message}"

    def to_dict(self) -> Dict[str, Any]:
        """ 转化为字典格式 """
        return {
            "code": self.code.value,
            "error": self.code.name,
            "message": self.message,
            "details": self.details,
        }


class ConfigError(ProxyPoolError):
    """
    代理池配置异常

    读取或解析配置文件时发生错误时抛出
    """
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=ErrorCode.CONFIG_ERROR,
            message=message,
            details=details,
        )


class PoolEmptyError(ProxyPoolError):
    """
    代理池为空异常

    当代理池中没有可用代理时抛出
    """
    def __init__(
        self,
        message: str = "代理池中没有可用代理",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            code=ErrorCode.POOL_EMPTY,
            message=message,
            details=details,
        )


class ProxyValidationError(ProxyPoolError):
    """
    代理验证异常

    代理验证过程中发生错误时抛出
    """
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        code: ErrorCode = ErrorCode.VALIDATION_FAILED,
    ):
        super().__init__(
            code=code,
            message=message,
            details=details,
        )


class ProxyFetchError(ProxyPoolError):
    """
    代理获取异常

    从代理源获取代理失败时抛出
    """
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        code: ErrorCode = ErrorCode.FETCH_FAILED,
    ):
        super().__init__(
            code=code,
            message=message,
            details=details,
        )


class RedisError(ProxyPoolError):
    """
    Redis 连接或操作异常

    与 Redis 相关的操作中发生错误时抛出
    """
    def __init__(
        self,
        message: str,
        details: Optional[Dict[str, Any]] = None,
        code: ErrorCode = ErrorCode.REDIS_OPERATION_ERROR,
    ):
        super().__init__(
            code=code,
            message=message,
            details=details,
        )


class RequestError(Exception):
    """ 请求异常基类 """
    pass


class ProxyError(RequestError):
    """ 代理相关异常 """
    pass


def handle_exception(e: Exception) -> Dict[str, Any]:
    """
    统一异常处理

    Args:
        e: 异常对象

    Returns:
        异常信息字典
    """
    if isinstance(e, ProxyPoolError):
        return e.to_dict()
    else:
        return {
            "code": ErrorCode.SYSTEM_ERROR.value,
            "error": ErrorCode.SYSTEM_ERROR.name,
            "message": str(e),
            "details": {"type": e.__class__.__name__},
        }


if __name__ == "__main__":
    try:
        raise ProxyValidationError(
            message="代理验证超时",
            code=ErrorCode.VALIDATION_TIMEOUT,
            details={"proxy": "220.248.70.237:9002", "timeout": 5},
        )
    except Exception as e:
        error_info = handle_exception(e)
        print(error_info)
