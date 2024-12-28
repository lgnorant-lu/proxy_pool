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
from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, List
from pathlib import Path
import json
import yaml

from proxy_pool.utils.exceptions import ConfigError
from proxy_pool.utils.logger import setup_logger

logger = setup_logger()


@dataclass
class ProxyConfig:
    """
    代理池系统配置类

    配置项说明:

    Redis配置:
        REDIS_HOST: Redis服务器地址
        REDIS_PORT: Redis服务器端口
        REDIS_PASSWORD: Redis密码
        REDIS_KEY: 代理存储键名
        REDIS_DB: Redis数据库号

    评分配置:
        INITIAL_SCORE: 代理初始分数
        MIN_SCORE: 最低分数
        MAX_SCORE: 最高分数
        SCORE_STEP: 分数步长

    统计配置:
        CONFIDENCE_LEVEL: 置信水平
        SAMPLE_SIZE: 样本大小
        MIN_SAMPLE_SIZE: 最小样本大小

    验证配置:
        VALIDATE_TIMEOUT: 验证超时时间
        MAX_RETRY_TIMES: 最大重试次数
        TEST_URLS: 测试URL列表
        VALIDATE_BATCH_SIZE: 验证批次大小
        VALIDATE_INTERVAL: 验证间隔

    获取配置:
        FETCH_INTERVAL: 获取间隔
        FETCH_TIMEOUT: 获取超时时间
        FETCH_BATCH_SIZE: 获取批次大小
        MAX_FETCHERS: 最大获取器数量
    """

    # Redis配置参数
    REDIS_HOST: str = field(default="localhost")
    REDIS_PORT: int = field(default=6379)
    REDIS_PASSWORD: Optional[str] = field(default=None)
    REDIS_KEY: str = field(default="proxies")
    REDIS_DB: int = field(default=0)

    # 代理评分配置
    INITIAL_SCORE: int = field(default=10)
    MIN_SCORE: int = field(default=0)
    MAX_SCORE: int = field(default=100)
    SCORE_STEP: int = field(default=1)

    # 统计配置
    CONFIDENCE_LEVEL: float = field(default=0.95)
    SAMPLE_SIZE: int = field(default=50)
    MIN_SAMPLE_SIZE: int = field(default=10)

    # 代理验证配置
    VALIDATE_TIMEOUT: int = field(default=5)
    MAX_RETRY_TIMES: int = field(default=3)
    TEST_URLS: List[str] = field(default_factory=lambda: ["http://www.baidu.com"])
    VALIDATE_BATCH_SIZE: int = field(default=100)
    VALIDATE_INTERVAL: int = field(default=300)  # 300s 检验频次

    # 代理获取配置
    FETCH_INTERVAL: int = field(default=300)  # 300s 获取频次
    FETCH_TIMEOUT: int = field(default=10)
    FETCH_BATCH_SIZE: int = field(default=20)
    MAX_FETCHERS: int = field(default=5)

    def __init__(self):
        self.verify_proxy = True

    def __post_init__(self):
        """初始化后验证和环境变量处理"""
        self._load_from_env()
        self._validate_config()

    def _load_from_env(self):
        """从环境变量加载配置"""
        env_mapping = {
            "PROXY_POOL_REDIS_HOST": "REDIS_HOST",
            "PROXY_POOL_REDIS_PORT": ("REDIS_PORT", int),
            "PROXY_POOL_REDIS_PASSWORD": "REDIS_PASSWORD",
            "PROXY_POOL_REDIS_DB": ("REDIS_DB", int),
            "PROXY_POOL_VALIDATE_TIMEOUT": ("VALIDATE_TIMEOUT", int),
            "PROXY_POOL_FETCH_INTERVAL": ("FETCH_INTERVAL", int),
        }

        for env_key, config_info in env_mapping.items():
            if isinstance(config_info, tuple):
                config_key, convert_func = config_info
            else:
                config_key, convert_func = config_info, str

            if env_value := os.getenv(env_key):
                try:
                    setattr(self, config_key, convert_func(env_value))
                    logger.debug(f"从环境变量加载配置: {env_key}={env_value}")
                except ValueError as e:
                    logger.warning(
                        f"环境变量转换失败: {env_key}={env_value}, error: {e}"
                    )

    def _validate_config(self):
        """验证配置有效性"""
        validations = [
            (0 <= self.MIN_SCORE <= self.INITIAL_SCORE <= self.MAX_SCORE,
             "评分配置无效: MIN_SCORE <= INITIAL_SCORE <= MAX_SCORE"),
            (0 < self.CONFIDENCE_LEVEL < 1,
             "置信水平必须在0到1之间"),
            (self.SAMPLE_SIZE >= self.MIN_SAMPLE_SIZE,
             "样本大小必须大于等于最小样本大小"),
            (all(self.TEST_URLS),
             "测试URL列表不能为空"),
            (self.VALIDATE_TIMEOUT > 0,
             "验证超时时间必须大于0"),
            (self.MAX_RETRY_TIMES > 0,
             "最大重试次数必须大于0"),
            (self.FETCH_INTERVAL > 0,
             "获取间隔必须大于0"),
            (self.FETCH_TIMEOUT > 0,
             "获取超时时间必须大于0")
        ]

        for condition, message in validations:
            if not condition:
                raise ConfigError(f"配置验证失败: {message}")

    def export_config(self, file_path: str):
        """导出配置到文件"""
        path = Path(file_path)
        try:
            with open(path, "w", encoding="utf-8") as f:
                if path.suffix in [".yaml", ".yml"]:
                    yaml.dump(self.to_dict(), f, allow_unicode=True)
                elif path.suffix == ".json":
                    json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
                else:
                    raise ConfigError(f"不支持の配置文件格式: {path.suffix}")
            logger.info(f"配置已导出至: {file_path}")
        except Exception as e:
            raise ConfigError(f"导出配置文件失败: {str(e)}")

    def load_from_file(self, config_path: str):
        """从配置文件加载配置"""
        try:
            path = Path(config_path)
            if not path.exists():
                raise ConfigError(f"配置文件不存在: {config_path}")

            with open(path, "r", encoding="utf-8") as f:
                if path.suffix in [".yaml", ".yml"]:
                    config_data = yaml.safe_load(f)
                elif path.suffix == ".json":
                    config_data = json.load(f)
                else:
                    raise ConfigError(f"不支持的配置文件格式: {path.suffix}")

            # 更新配置
            for key, value in config_data.items():
                if hasattr(self, key):
                    setattr(self, key, value)

            logger.info(f"成功加载配置文件: {config_path}")
            self._validate_config()

        except Exception as e:
            raise ConfigError(f"加载配置文件失败: {str(e)}")

    def reload(self):
        """ 重新加载配置 """
        self._load_from_env()
        self._validate_config()
        logger.info("配置已重新加载")

    def to_dict(self) -> Dict[str, str]:
        """ 转换为字典 """
        return asdict(self)

    def __str__(self) -> str:
        """ 字符串梅花 """
        config_dict = self.to_dict()
        grouped_config = {
            "Redis配置": {
                k: v for k, v in config_dict.items() if k.startswith("REDIS_")
            },
            "评分配置": {k: v for k, v in config_dict.items() if "SCORE" in k},
            "统计配置": {
                k: v
                for k, v in config_dict.items()
                if k in ["CONFIDENCE_LEVEL", "SAMPLE_SIZE", "MIN_SAMPLE_SIZE"]
            },
            "验证配置": {k: v for k, v in config_dict.items() if "VALIDATE" in k},
            "获取配置": {k: v for k, v in config_dict.items() if "FETCH" in k},
        }
        return json.dumps(grouped_config, indent=2, ensure_ascii=False)


_config_instance: Optional[ProxyConfig] = None


def get_config() -> ProxyConfig:
    """获取全局配置单例"""
    global _config_instance
    if _config_instance is None:
        _config_instance = ProxyConfig()
    return _config_instance


if __name__ == "__main__":
    try:
        # 测试基本配置
        config = get_config()
        print("配置说明:")
        print(config.__doc__)

        print("\n默认配置")
        print(config)

        # 导出配置文件
        export_path = "config.yaml"
        config.export_config(export_path)
        print(f"\n配置已导出到 {export_path}")
        print("\n导出的配置文件内容:")
        with open(export_path, 'r', encoding='utf-8') as f:
            print(f.read())

        # 测试环境变量
        print("\n环境变量测试:")
        os.environ["PROXY_POOL_REDIS_HOST"] = "127.0.0.1"
        os.environ["PROXY_POOL_REDIS_PORT"] = "6380"
        new_config = ProxyConfig()
        print("\n加载环境变量后的配置:")
        print(f"Redis Host: {new_config.REDIS_HOST}")
        print(f"Redis Port: {new_config.REDIS_PORT}")

        # 测试配置文件加载
        # config.load_from_file('config.yaml')

    except ConfigError as e:
        print(f"配置错误: {e}")
    except Exception as e:
        print(f"未知错误: {e}")
