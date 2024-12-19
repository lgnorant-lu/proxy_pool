"""
----------------------------------------------------------------
File name:                  storage.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                Redis 代理存储管理模块
----------------------------------------------------------------

Changed history:            重构 Redis 存储逻辑,增强代理存储管理
----------------------------------------------------------------
"""

import redis
from typing import Optional, Union, List
import random

from ..utils.config import ProxyConfig
from ..utils.exceptions import ProxyPoolError
from ..utils.logger import setup_logger
from ..models.proxy_model import ProxyModel


class RedisProxyClient:
    """
    Redis 代理存储客户端

    提供代理的:
    1. 存储
    2. 获取
    3. 更新
    4. 删除
    等核心功能
    """

    def __init__(self, config: ProxyConfig = ProxyConfig()):
        """
        初始化Redis客户端

        Args:
            config: 配置参数
        """
        self._config = config
        self._logger = setup_logger()

        try:
            self.db = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                password=config.REDIS_PASSWORD,
                decode_responses=True,
            )
        except redis.ConnectionError as e:
            self._logger.error(f"Redis连接失败: {e}")
            raise ProxyPoolError(f"Redis连接失败: {e}")

    async def add(self, proxy: Union[str, ProxyModel], score: Optional[float] = None) -> bool:
        """
        添加代理到代理池

        Args:
            proxy: 代理地址或代理模型
            score: 代理评分

        Returns:
            是否添加成功
        """
        try:
            # 处理不同类型输入
            if isinstance(proxy, ProxyModel):
                proxy_key = f"{proxy.ip}:{proxy.port}"
                proxy_score = score or proxy.success_rate * 100
            else:
                proxy_key = proxy
                proxy_score = score or self._config.INITIAL_SCORE

            # 防止重复添加
            if not self.db.zscore(self._config.REDIS_KEY, proxy_key):
                return bool(
                    self.db.zadd(self._config.REDIS_KEY, {proxy_key: proxy_score})
                )
            return False
        except Exception as e:
            self._logger.error(f"添加代理 {proxy} 失败: {e}")
            return False

    def remove(self, proxy: Union[str, ProxyModel]) -> bool:
        """
        从代理池移除代理

        Args:
            proxy: 代理地址或代理模型

        Returns:
            是否移除成功
        """
        try:
            proxy_key = proxy if isinstance(proxy, str) else f"{proxy.ip}:{proxy.port}"

            result = self.db.zrem(self._config.REDIS_KEY, proxy_key)
            return bool(result)
        except Exception as e:
            self._logger.error(f"移除代理 {proxy} 失败: {e}")
            return False

    def update_score(
        self, proxy: Union[str, ProxyModel], score: Optional[float] = None
    ) -> bool:
        """
        更新代理评分

        Args:
            proxy: 代理地址或代理模型
            score: 新的评分

        Returns:
            是否更新成功
        """
        try:
            if isinstance(proxy, ProxyModel):
                proxy_key = f"{proxy.ip}:{proxy.port}"
                proxy_score = score or proxy.success_rate * 100
            else:
                proxy_key = proxy
                proxy_score = score or self._config.INITIAL_SCORE

            return bool(self.db.zadd(self._config.REDIS_KEY, {proxy_key: proxy_score}))
        except Exception as e:
            self._logger.error(f"更新代理 {proxy} 评分失败: {e}")
            return False

    def random_proxy(self, min_score: Optional[float] = None) -> Optional[str]:
        """
        随机获取一个代理

        Args:
            min_score: 最低评分要求

        Returns:
            代理地址或None
        """
        try:
            min_score = min_score or self._config.MIN_SCORE

            # 获取符合评分要求的代理
            proxies = self.db.zrangebyscore(
                self._config.REDIS_KEY, min_score, float("inf"), withscores=False
            )

            return random.choice(proxies) if proxies else None
        except Exception as e:
            self._logger.error(f"随机获取代理失败: {e}")
            return None

    def get_all_proxies(self) -> List[str]:
        """
        获取所有代理

        Returns:
            所有代理地址列表
        """
        try:
            return self.db.zrange(self._config.REDIS_KEY, 0, -1)
        except Exception as e:
            self._logger.error(f"获取所有代理失败: {e}")
            return []

    def get_proxy_count(self) -> int:
        """
        获取代理总数

        Returns:
            代理总数
        """
        try:
            return self.db.zcard(self._config.REDIS_KEY)
        except Exception as e:
            self._logger.error(f"获取代理总数失败: {e}")
            return 0

    def get_proxies_by_score_range(
        self, min_score: float, max_score: float
    ) -> List[str]:
        """
        获取指定评分范围内的代理

        Args:
            min_score: 最低评分
            max_score: 最高评分

        Returns:
            符合评分范围的代理列表
        """
        try:
            return self.db.zrangebyscore(self._config.REDIS_KEY, min_score, max_score)
        except Exception as e:
            self._logger.error(f"获取评分范围代理失败: {e}")
            return []

    def clear_proxies(self) -> bool:
        """
        清空代理池

        Returns:
            是否清空成功
        """
        try:
            self.db.delete(self._config.REDIS_KEY)
            return True
        except Exception as e:
            self._logger.error(f"清空代理池失败: {e}")
            return False
