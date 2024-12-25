"""
----------------------------------------------------------------
File name:                  storage.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                Redis 代理存储管理模块
----------------------------------------------------------------

Changed history:            重构 Redis 存储逻辑,增强代理存储管理
                            2024/12/25: 连接池管理, 拓展框架预留
----------------------------------------------------------------
"""

# import aioredis  # 3.11 兼容 bug
import redis
# import asyncio  # 结合 redis 实现同 aioreis 的异步功能
import random
import json
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from typing import Optional, Union, List, Dict, Any

from proxy_pool.utils.config import ProxyConfig
# from proxy_pool.utils.exceptions import ProxyPoolError
from proxy_pool.utils.logger import setup_logger
from proxy_pool.models.proxy_model import ProxyModel


class RedisConnectionPool:
    """ Redis 连接池管理 """
    def __init__(self, config: ProxyConfig):
        """
        初始化连接池

        Args:
            config: Redis 配置参数
        """
        self._config = config
        self._pool = redis.ConnectionPool(
            host=config.REDIS_HOST,
            port=config.REDIS_PORT,
            password=config.REDIS_PASSWORD,
            decode_responses=True,
            max_connections=50  # 最大连接数
        )

    @contextmanager
    def get_connection(self):
        """
        获取 Redis 连接的上下文管理器

        Yields:
            Redis 连接对象
        """
        conn = None
        try:
            conn = redis.Redis(connection_pool=self._pool)
            yield conn
        finally:
            if conn:
                conn.close()


class ProxySerializer:
    """ 代理数据序列化处理 """
    @staticmethod
    def serialize(proxy: ProxyModel) -> str:
        """
        序列化代理对象为 JSON 字符串

        Args:
            proxy: 代理模型对象

        Returns:
            序列化后的 JSON 字符串
        """
        return json.dumps({
            'ip': proxy.ip,
            'port': proxy.port,
            'protocol': proxy.protocol,
            'success_rate': proxy.success_rate,
            'response_times': proxy.response_times,
            'last_check_time': proxy.last_check_time.isoformat() if proxy.last_check_time else None,
        })

    @staticmethod
    def deserialize(data: str) -> ProxyModel:
        """
        反序列化 JSON 字符串为代理对象

        Args:
            data: JSON 字符串

        Returns:
            代理模型对象
        """
        proxy_dict = json.loads(data)
        if proxy_dict.get('last_check_time'):
            proxy_dict['last_check_time'] = datetime.fromisoformat(proxy_dict['last_check_time'])
        return ProxyModel(**proxy_dict)


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
        初始化 Redis 客户端

        Args:
            config: 配置参数
        """
        self._config = config
        self._logger = setup_logger()
        self._pool = RedisConnectionPool(config)
        self._serializer = ProxySerializer()
        self.executor = ThreadPoolExecutor()

    async def _run_sync(self, func, *args):
        """
        使用线程池执行同步 Redis 操作

        Args:
            func: Redis 操作函数
            *args: 函数参数

        Return:
            调用 Redis 操作作函数返回值
        """
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(self.executor, func, *args)

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
            def _add():
                with self._pool.get_connection() as conn:
                    # 处理不同类型输入
                    if isinstance(proxy, ProxyModel):
                        proxy_key = f"{proxy.ip}:{proxy.port}"
                        proxy_score = score or proxy.success_rate * 100
                        proxy_data = self._serializer.serialize(proxy)
                    else:
                        proxy_key = proxy
                        proxy_score = score or self._config.INITIAL_SCORE
                        proxy_data = proxy_key

                    # 防止重复添加
                    if not conn.zscore(self._config.REDIS_KEY, proxy_key):
                        pipeline = conn.pipeline()
                        pipeline.zadd(self._config.REDIS_KEY, {proxy_key: proxy_score})
                        pipeline.hset(f"{self._config.REDIS_KEY}:details", proxy_key, proxy_data)
                        return all(pipeline.execute())
                    return False
            return await self._run_sync(_add)
        except Exception as e:
            self._logger.error(f"添加代理 {proxy} 失败: {e}")
            return False

    async def remove(self, proxy: Union[str, ProxyModel]) -> bool:
        """
        从代理池移除代理

        Args:
            proxy: 代理地址或代理模型

        Returns:
            是否移除成功
        """
        try:
            def _remove():
                with self._pool.get_connection() as conn:
                    proxy_key = proxy if isinstance(proxy, str) else f"{proxy.ip}:{proxy.port}"
                    pipeline = conn.pipeline()
                    pipeline.zrem(self._config.REDIS_KEY, proxy_key)
                    pipeline.hdel(f"{self._config.REDIS_KEY}:details", proxy_key)
                    return all(pipeline.execute())
            return await self._run_sync(_remove)
        except Exception as e:
            self._logger.error(f"移除代理 {proxy} 失败: {e}")
            return False

    async def update_score(
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
            def _update():
                with self._pool.get_connection() as conn:
                    if isinstance(proxy, ProxyModel):
                        proxy_key = f"{proxy.ip}:{proxy.port}"
                        proxy_score = score or proxy.success_rate * 100
                        # 更新详细信息
                        proxy_data = self._serializer.serialize(proxy)
                        pipeline = conn.pipeline()
                        pipeline.zadd(self._config.REDIS_KEY, {proxy_key: proxy_score})
                        pipeline.hset(f"{self._config.REDIS_KEY}:details", proxy_key, proxy_data)
                        return all(pipeline.execute())
                    else:
                        proxy_key = proxy
                        proxy_score = score or self._config.INITIAL_SCORE
                        return bool(conn.zadd(self._config.REDIS_KEY, {proxy_key: proxy_score}))
            return await self._run_sync(_update)
        except Exception as e:
            self._logger.error(f"更新代理 {proxy} 评分失败: {e}")
            return False

    async def random_proxy(self, min_score: Optional[float] = None) -> Optional[str]:
        """
        随机获取一个代理

        Args:
            min_score: 最低评分要求

        Returns:
            代理地址或 None
        """
        try:
            with self._pool.get_connection() as conn:
                min_score = min_score or self._config.MIN_SCORE
                # 获取符合评分要求的代理
                proxies = conn.zrangebyscore(
                    self._config.REDIS_KEY,
                    min_score,
                    float("inf"),
                )
                if proxies:
                    proxy_key = random.choice(proxies)
                    # 获取详细信息
                    proxy_data = conn.hget(f"{self._config.REDIS_KEY}:details", proxy_key)
                    if proxy_data:
                        return str(self._serializer.deserialize(proxy_data))
                    return proxy_key
                return None
        except Exception as e:
            self._logger.error(f"随机获取代理失败: {e}")
            return None

    async def get_all_proxies(self) -> List[Union[str, ProxyModel]]:
        """
        获取所有代理

        Returns:
            所有代理地址列表
        """
        try:
            with self._pool.get_connection() as conn:
                proxy_keys = conn.zrange(self._config.REDIS_KEY, 0, -1)
                result = []
                for key in proxy_keys:
                    proxy_data = conn.hget(f"{self._config.REDIS_KEY}:details", key)
                    if proxy_data:
                        result.append(self._serializer.deserialize(proxy_data))
                    else:
                        result.append(key)
                return result
        except Exception as e:
            self._logger.error(f"获取所有代理失败: {e}")
            return []

    async def get_proxy_count(self) -> int:
        """
        获取代理总数

        Returns:
            代理总数
        """
        try:
            with self._pool.get_connection() as conn:
                return conn.zcard(self._config.REDIS_KEY)
        except Exception as e:
            self._logger.error(f"获取代理总数失败: {e}")
            return 0

    async def get_proxies_by_score_range(
        self,
        min_score: float,
        max_score: float,
    ) -> List[Union[str, ProxyModel]]:
        """
        获取指定评分范围内的代理

        Args:
            min_score: 最低评分
            max_score: 最高评分

        Returns:
            符合评分范围的代理列表
        """
        try:
            with self._pool.get_connection() as conn:
                proxy_keys = conn.zrangebyscore(self._config.REDIS_KEY, min_score, max_score)
                result = []
                for key in proxy_keys:
                    proxy_data = conn.hget(f"{self._config.REDIS_KEY}:details", key)
                    if proxy_data:
                        result.append(self._serializer.deserialize(proxy_data))
                    else:
                        result.append(key)
                return result
        except Exception as e:
            self._logger.error(f"获取评分范围代理失败: {e}")
            return []

    async def clear_proxies(self) -> bool:
        """
        清空代理池

        Returns:
            是否清空成功
        """
        try:
            def _clear():
                with self._pool.get_connection() as conn:
                    pipeline = conn.pipeline()
                    pipeline.delete(self._config.REDIS_KEY)
                    pipeline.delete(f"{self._config.REDIS_KEY}:details")
                    return all(pipeline.execute())
            return await self._run_sync(_clear)
        except Exception as e:
            self._logger.error(f"清空代理池失败: {e}")
            return False

    async def batch_add(self, proxies: List[ProxyModel]) -> Dict[str, bool]:
        """
        批量添加代理

        Args:
            proxies: 代理对象列表

        Returns:
            添加结果字典 {proxy_key: success_bool}
        """
        results = {}
        try:
            with self._pool.get_connection() as conn:
                pipeline = conn.pipeline()
                for proxy in proxies:
                    proxy_key = f"{proxy.ip}:{proxy.port}"
                    proxy_score = proxy.success_rate * 100
                    # 检查是否存在
                    if not conn.zscore(self._config.REDIS_KEY, proxy_key):
                        pipeline.zadd(self._config.REDIS_KEY, {proxy_key: proxy_score})
                        # 存储详细信息
                        pipeline.hset(
                            f"{self._config.REDIS_KEY}:details",
                            proxy_key,
                            self._serializer.serialize(proxy)
                        )
                results = pipeline.execute()
        except Exception as e:
            self._logger.error(f"批量添加代理失败: {e}")
        return results

    class ProxyCache:
        """
        代理缓存层
        - 减少Redis访问频率
        - 提高响应速度
        """

        def __init__(self):
            self._local_cache = {}
            self._cache_ttl = 300

        async def get_cached(self, key: str) -> Any:
            """获取缓存的代理数据"""
            pass

        async def set_cached(self, key: str, value: Any):
            """设置代理缓存"""
            pass

    class RedisMetricsCollector:
        """
        Redis监控指标收集
        - 内存使用
        - 连接数
        - 操作统计
        """

        def collect_metrics(self) -> Dict:
            pass

    class RedisFailover:
        """
        Redis故障转移机制
        - 主从切换
        - 连接恢复
        """

        async def handle_failover(self):
            pass

    class RedisLock:
        """
        分布式锁实现
        - 资源竞争控制
        - 并发操作保护
        """

        async def acquire_lock(self, key: str, timeout: int = 10) -> bool:
            pass

        async def release_lock(self, key: str):
            pass

    class RedisBackup:
        """
        数据备份恢复机制
        - 定期备份
        - 数据恢复
        """

        async def backup(self, filename: str):
            pass

        async def restore(self, filename: str):
            pass

    async def check_consistency(self):
        """
        数据一致性检查
        - 数据完整性验证
        - 冗余数据清理
        """
        pass

    async def decay_scores(self, decay_factor: float = 0.95):
        """
        代理评分衰减机制
        - 时间衰减
        - 动态评分调整
        """
        pass


if __name__ == "__main__":
    import sys
    import asyncio

    async def test_redis_client():
        """简单的功能测试"""
        try:
            # 初始化客户端
            config = ProxyConfig()
            client = RedisProxyClient(config)

            print("=== 开始测试Redis代理存储 ===")

            # 测试连接
            with client._pool.get_connection() as conn:
                if not conn.ping():
                    print("Redis连接失败")
                    return
                print("Redis连接成功")

            # 清空测试环境
            clear_result = await client.clear_proxies()
            print(f"清空代理池: {'成功' if clear_result else '失败'}")

            # 测试添加代理
            test_proxy = ProxyModel(
                ip="127.0.0.1",
                port=8080,
                protocol="http",
                success_rate=0.8,
                response_times=[1.5],
                last_check_time=datetime.now(),
            )

            success = await client.add(test_proxy)
            print(f"添加单个代理: {'成功' if success else '失败'}")

            # 测试批量添加
            test_proxies = [
                ProxyModel(
                    ip=f"127.0.0.{i}",
                    port=8080 + i,
                    protocol="http",
                    success_rate=0.8,
                    response_times=[1.5],
                    last_check_time=datetime.now(),
                )
                for i in range(2, 5)
            ]

            results = await client.batch_add(test_proxies)
            print(f"批量添加代理: {len(results)} 个")

            # 测试获取代理
            count = await client.get_proxy_count()
            print(f"当前代理池数量: {count}")

            proxy = await client.random_proxy()
            if isinstance(proxy, ProxyModel):
                print(f"随机获取代理: {proxy.ip}:{proxy.port}")
            else:
                print(f"随机获取代理: {proxy}")

            proxies = await client.get_all_proxies()
            print(f"获取所有代理: {len(proxies)} 个")

            # 测试更新评分
            success = await client.update_score(test_proxy, 95.0)
            print(f"更新代理评分: {'成功' if success else '失败'}")

            # 测试删除代理
            success = await client.remove(test_proxy)
            print(f"删除代理: {'成功' if success else '失败'}")

            # 清理测试数据
            await client.clear_proxies()
            print("清理测试数据成功")

            print("=== 测试完成 ===")

        except Exception as e:
            print(f"测试过程出错: {e}")
            import traceback
            traceback.print_exc()


    # 运行测试
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_redis_client())
