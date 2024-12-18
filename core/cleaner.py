"""
----------------------------------------------------------------
File name:                  cleaner.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理清理模块
----------------------------------------------------------------

Changed history:            代理清理模块: 定期清理废弃代理
----------------------------------------------------------------
"""

import asyncio
import time
from typing import List, Optional

from ..utils.logger import setup_logger
from .storage import RedisProxyClient
from .validator import ProxyValidator
from ..models.proxy_model import ProxyModel
from ..utils.config import ProxyConfig


class ProxyCleaner:
    def __init__(
            self,
            config: ProxyConfig = ProxyConfig(),
            storage: Optional[RedisProxyClient] = None,
            validator: Optional[ProxyValidator] = None
    ):
        self.config = config
        self.logger = setup_logger()
        self.storage = storage or RedisProxyClient(config)
        self.validator = validator or ProxyValidator(config)

    async def clean_invalid_proxies(self) -> int:
        """
        清理无效代理

        Returns:
            清理的代理数量
        """
        try:
            # 获取所有代理
            all_proxies = self.storage.get_all_proxies()
            invalid_proxies = []

            # 并发验证代理
            for proxy_str in all_proxies:
                ip, port = proxy_str.split(':')
                proxy = ProxyModel(ip=ip, port=int(port))

                is_valid = await self.validator.validate_proxy(proxy)
                if not is_valid:
                    invalid_proxies.append(proxy_str)

            # 批量移除无效代理
            for proxy in invalid_proxies:
                self.storage.remove(proxy)

            self.logger.info(f"清理无效代理 {len(invalid_proxies)} 个")
            return len(invalid_proxies)

        except Exception as e:
            self.logger.error(f"代理清理异常: {e}")
            return 0

    async def periodic_clean(
            self,
            interval: int = 3600,
            max_retries: int = 3
    ):
        """
        定期清理代理

        Args:
            interval: 清理间隔(秒)
            max_retries: 最大重试次数
        """
        retries = 0
        while retries < max_retries:
            try:
                await self.clean_invalid_proxies()
                retries = 0  # 成功后重置重试计数
                await asyncio.sleep(interval)
            except Exception as e:
                retries += 1
                self.logger.warning(f"定期清理失败，重试 {retries}/{max_retries}: {e}")
                await asyncio.sleep(interval)

        self.logger.error("定期清理达到最大重试次数，已停止")
