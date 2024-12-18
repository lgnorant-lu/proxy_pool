"""
----------------------------------------------------------------
File name:                  proxy_memory.py
Auther:                     Ignorant-lu
Date created:               2024/12/17 10:38
Description:                IP 代理池获取模块, 其为初构建的第一模块
----------------------------------------------------------------

Changed history:            更改内容格式, 文件统一描述, 暂明确了文件进行的分流向

----------------------------------------------------------------
"""

import logging
import random
from typing import Optional, List

import redis


# 常量配置
class ProxyConfig:
    INITIAL_SCORE = 10
    MIN_SCORE = 0
    MAX_SCORE = 100
    REDIS_HOST = "localhost"
    REDIS_PORT = 6379
    REDIS_PASSWORD = None
    REDIS_KEY = "proxies"


# 自定义异常
class PoolEmptyError(Exception):
    """代理池为空异常"""

    pass


class ProxyPoolError(Exception):
    """代理池异常基类"""

    pass


class RedisProxyClient:
    """
    Redis 代理池客户端
    """

    def __init__(
        self,
        host: str = ProxyConfig.REDIS_HOST,
        port: int = ProxyConfig.REDIS_PORT,
        password: Optional[str] = ProxyConfig.REDIS_PASSWORD,
    ):
        """
        初始化 Redis 客户端

        Args:
            host:           Redis 服务器 IP 地址
            port:           Redis 服务器端口
            password:       Redis 服务器密码
        """
        try:
            self.db = redis.Redis(
                host=host, port=port, password=password, decode_responses=True
            )
            self._logger = logging.getLogger(self.__class__.__name__)
        except redis.ConnectionError as e:
            self._logger.error(f"Redis 连接失败: {e}")
            raise

    def add(self, proxy, score=ProxyConfig.INITIAL_SCORE) -> bool:
        """
        代理添加, 权重分初始化设置

        Args:
            proxy:          代理
            score:          权重分

        Return:
            添加成功状态
        """
        try:
            # 防止重复添加
            if not self.db.zscore(ProxyConfig.REDIS_KEY, proxy):
                return bool(self.db.zadd(ProxyConfig.REDIS_KEY, {proxy: score}))
            return False
        except Exception as e:
            self._logger.error(f"代理 {proxy} 添加失败: {e}")
            return False

    def random_proxy(self) -> str:
        """
        随机获取一个代理,

        Return:
            随机代理

        Raises:
            PoolEmptyError: 代理池为空
        """
        try:
            # 优先获取高分代理
            result = self.db.zrangebyscore(
                ProxyConfig.REDIS_KEY, ProxyConfig.MIN_SCORE, ProxyConfig.MAX_SCORE
            )
            if result:
                return random.choice(result)
            # 备选方案
            result = self.db.zrevrange(ProxyConfig.REDIS_KEY, 0, 100)
            if result:
                return random.choice(result)
            raise PoolEmptyError("代理池已空")
        except PoolEmptyError:
            self._logger.warning("代理池为空")
            raise
        except Exception as e:
            self._logger.error(f"获取代理异常: {e}")
            raise

    def update_score(
        self, proxy: str, delta: int = 1, max_score: int = ProxyConfig.MAX_SCORE
    ) -> bool:
        """
        更新代理评分

        Args:
            proxy:          代理地址
            delta:          分数变化
            max_score:      最大分数

        Returns:
            更新成功状态
        """
        try:
            current_score = self.db.zscore(ProxyConfig.REDIS_KEY, proxy)
            if current_score is not None:
                new_score = min(current_score + delta, max_score)
                self.db.zadd(ProxyConfig.REDIS_KEY, {proxy: new_score})
                return True
            return False
        except Exception as e:
            self._logger.error(f"更新代理 {proxy} 评分失败: {e}")
            return False

    def remove_proxy(self, proxy: str) -> bool:
        """
        删除代理

        Args:
            proxy: 代理

        Returns:
            删除成功状态
        """
        try:
            return bool(self.db.zrem(ProxyConfig.REDIS_KEY, proxy))
        except Exception as e:
            self._logger.error(f"移除代理 {proxy} 失败: {e}")
            return False

    def get_proxies(
        self,
        min_score: int = ProxyConfig.MIN_SCORE,
        max_score: int = ProxyConfig.MAX_SCORE,
    ) -> List[str]:
        """
        获取指定分数范围内的代理

        Args:
            min_score: 最小分数
            max_score: 最大分数

        Returns:
            代理列表
        """
        try:
            return self.db.zrangebyscore(ProxyConfig.REDIS_KEY, min_score, max_score)
        except Exception as e:
            self._logger.error(
                f"获取分数在 {min_score}-{max_score} 之间的代理失败: {e}"
            )
            return []


def main():
    try:
        client = RedisProxyClient()
        client.add("127.0.0.1:8080")
        print(client.random_proxy())
        client.update_score("127.0.0.1:8080", delta=10)
        print(client.get_proxies())
        client.remove_proxy("127.0.0.1:8080")
        print(client.get_proxies())
    except Exception as e:
        print(f"代理池操作异常: {e}")


if __name__ == "__main__":
    main()
