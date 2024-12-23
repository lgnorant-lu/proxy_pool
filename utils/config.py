"""
----------------------------------------------------------------
File name:                  config.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理池系统配置管理模块
----------------------------------------------------------------

Changed history:            初始化配置文件,定义系统全局配置
                            2024/12/24: 增加环境变量支持和配置验证
----------------------------------------------------------------
"""

import os
from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from pathlib import Path
import json
import yaml

from proxy_pool.utils.exceptions import ConfigError
from proxy_pool.utils.logger import setup_logger


@dataclass
class ProxyConfig:
    """
    代理池系统配置类

    管理系统全局配置参数:
    1. Redis 配置
    2. 代理评分配置
    3. 统计配置
    """

    # Redis配置参数
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None
    REDIS_KEY: str = "proxies"

    # 代理评分配置
    INITIAL_SCORE: int = 10
    MIN_SCORE: int = 0
    MAX_SCORE: int = 100

    # 统计配置
    CONFIDENCE_LEVEL: float = 0.95
    SAMPLE_SIZE: int = 50

    # 代理验证配置
    VALIDATE_TIMEOUT: int = 5
    MAX_RETRY_TIMES: int = 3

    # 代理获取配置
    Fetch_INTERVAL: int = 300  # 300 秒获取一次


def get_config():
    return ProxyConfig()
