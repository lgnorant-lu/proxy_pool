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
# import time
from typing import Optional

from ..utils.logger import setup_logger
from .storage import RedisProxyClient
from .validator import ProxyValidator
from ..utils.config import ProxyConfig
from .fetcher import ProxyFetcher


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
        self.fetcher = ProxyFetcher()

    async def clean_invalid_proxies(self) -> int:
        """
        清理无效代理

        Returns:
            清理的代理数量
        """
        try:
            # 获取所有代理, 加上 await 处理异步方法
            all_proxies_str = await self.storage.get_all_proxies()

            # 转换 str 列表为 ProxyModel 列表
            all_proxies = self.fetcher.parse_proxy_list(all_proxies_str)

            # 代理有效性验证, 有效代理获取
            valid_proxies = await self.validator.validate_proxy(all_proxies)

            # 无效代理差集获取
            invalid_proxies = [proxy for proxy in all_proxies if proxy not in valid_proxies]

            # 批量移除无效代理
            for proxy in invalid_proxies:
                await self.storage.remove(proxy)

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
