"""
----------------------------------------------------------------
File name:                  exceptions.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理池系统自定义异常模块
----------------------------------------------------------------

Changed history:            定义系统特定异常类型
----------------------------------------------------------------
"""


class ProxyPoolError(Exception):
    """
    代理池基础异常类

    作为所有自定义异常的基类
    """

    pass


class PoolEmptyError(ProxyPoolError):
    """
    代理池为空异常

    当代理池中没有可用代理时抛出
    """

    pass


class ProxyValidationError(ProxyPoolError):
    """
    代理验证异常

    代理验证过程中发生错误时抛出
    """

    pass


class ProxyFetchError(ProxyPoolError):
    """
    代理获取异常

    从代理源获取代理失败时抛出
    """

    pass
