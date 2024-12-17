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
INITIAL_SCORE = 10
MIN_SCORE = 0
MAX_SCORE = 100
REDIS_HOST = 'localhost'
REDIS_PORT = 6379
REDIS_PASSWORD = None
REDIS_KEY = 'proxies'


import redis

from random import choice


class RedisClient(object):
    def __init__(self, host=REDIS_HOST, port=REDIS_PORT, password=REDIS_PASSWORD):
        """
        初始化:
        :param host: Redis 服务器的 IP 地址
        :param port: Redis 服务器的端口
        :param password: Redis 服务器的密码
        """
        self.db = redis.Redis(host=host, port=port, password=password, decode_responses=True)

        def add(self, proxy, score=INITIAL_SCORE):
            """
            代理添加, 权重分初始化设置:
            :param proxy:       代理
            :param score:       权重分
            :return:            添加结果
            """
            if not self.db.zscore(REDIS_KEY, proxy):
                return self.db.zadd(REDIS_KEY, score, proxy)

        def random(self):
            """
            随机获取一个代理, 分数有效性从高到低降序获取:
            :return:            随机代理
            """
            result = self.db.zrangebyscore(REDIS_KEY, MIN_SCORE, MAX_SCORE)
            if len(result):
                return choice(result)
            else:
                result = self.db.zrevrange(REDIS_KEY, 0, 100)
                if len(result):
                    return choice(result)
                else:
                    raise PoolEmptyError

        def score_change(self, score):
            pass