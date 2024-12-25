"""
----------------------------------------------------------------
File name:                  proxy_model.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理模型定义模块
----------------------------------------------------------------

Changed history:            定义代理模型,包含统计特征
                            2024/12/25: 增加性能评分和状态管理
----------------------------------------------------------------
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import ipaddress
import json
from enum import Enum


class ProxyStatus(Enum):
    """ 代理状态枚举 """
    UNKNOWN = "unknown"  # 沃尔玛购物袋
    ACTIVE = "active"  # 上房揭瓦
    UNSTABLE = "unstable"  # 绝命毒师
    FAILED = "failed"  # 半拉柯基
    BANNED = "banned"  # 66


class ProxyAnonymity(Enum):
    """ 代理匿名度枚举 """
    TRANSPARENT = "transparent"  # 透理
    ANONYMOUS = "anonymous"  # 普匿
    HIGH = "high"  # 高匿
    ELITE = "elite"  # 精理
    UNKNOWN = "unknown"  # 未知


@dataclass
class ProxyModel:
    """
    代理模型,封装代理详细信息和统计特征

    包含:
    1. 基本代理信息
    2. 性能统计指标
    3. 状态更新方法
    4. 验证方法
    5. 序列化支持
    ...
    """

    ip: str
    port: int
    source: str = ''
    protocol: str = "http"
    success_rate: float = 0.0
    avg_response_time: float = 0.0
    last_check_time: datetime = field(default_factory=datetime.now)
    consecutive_failed_times: int = 0
    total_requests: int = 0
    location: Optional[str] = None
    anonymity: ProxyAnonymity = ProxyAnonymity.UNKNOWN
    last_status_code: Optional[int] = None
    tags: Dict[str, Any] = field(default_factory=dict)
    status: ProxyStatus = ProxyStatus.UNKNOWN
    created_time: datetime = field(default_factory=datetime.now)
    last_success_time: Optional[datetime] = None
    response_times: List[float] = field(default_factory=list)
    max_response_times: int = 100  # 保存最近 100 次响应时间
    fail_count: Optional[int] = None

    def __post_init__(self):
        """ 验证初始化参数 """
        self.validate()
        if isinstance(self.anonymity, str):
            self.anonymity = ProxyAnonymity(self.anonymity)
        if isinstance(self.status, str):
            self.status = ProxyStatus(self.status)

    def validate(self) -> None:
        """
        验证代理参数的有效性

        Raises:
            ValueError: 当参数无效时抛出
        """
        # 验证IP地址
        try:
            ipaddress.ip_address(self.ip)
        except ValueError:
            raise ValueError(f"无效的IP地址: {self.ip}")

        # 验证端口
        if not 0 <= self.port <= 65535:
            raise ValueError(f"无效的端口号: {self.port}")

        # 验证协议
        if self.protocol.lower() not in ['http', 'https', 'socks4', 'socks5']:
            raise ValueError(f"不支持的协议: {self.protocol}")

        # 验证统计数据
        if not 0 <= self.success_rate <= 1:
            raise ValueError(f"无效的成功率: {self.success_rate}")

        if self.avg_response_time < 0:
            raise ValueError(f"无效的平均响应时间: {self.avg_response_time}")

    def update_stats(self, is_success: bool, response_time: float, status_code: Optional[int] = None) -> None:
        """
        更新代理统计特征

        Args:
            is_success: 请求是否成功
            response_time: 响应时间
            status_code: HTTP状态码
        """
        self.total_requests += 1

        # 更新成功率
        self.success_rate = (
            self.success_rate * (self.total_requests - 1) + (1 if is_success else 0)
        ) / self.total_requests

        # 更新响应时间
        self.avg_response_time = (
            self.avg_response_time * (self.total_requests - 1) + response_time
        ) / self.total_requests

        # 更新失败次数
        if is_success:
            self.consecutive_failed_times = 0
        else:
            self.consecutive_failed_times += 1

        # 更新状态码
        if status_code is not None:
            self.last_status_code = status_code

        # 更新最后检查时间
        self.last_check_time = datetime.now()

    def _update_status(self, is_success: bool) -> None:
        """
        更新代理状态

        Args:
            is_success: 请求是否成功
        """
        if is_success:
            if self.success_rate >= 0.8:
                self.status = ProxyStatus.ACTIVE
            elif self.success_rate >= 0.5:
                self.status = ProxyStatus.UNSTABLE
        else:
            if self.consecutive_failed_times >= 5:
                self.status = ProxyStatus.FAILED
            elif self.success_rate < 0.3:
                self.status = ProxyStatus.UNSTABLE

    def get_score(self) -> float:
        """
        计算代理的性能评分 (0-100)

        Returns:
            float: 性能评分
        """
        if self.total_requests == 0:
            return 0.0

            # 基础分数 (40分)
        base_score = 40.0 * self.success_rate

        # 响应时间分数 (30分)
        response_score = 30.0 * (1.0 - min(self.avg_response_time / 10.0, 1.0))

        # 稳定性分数 (20分)
        stability_score = 20.0 * (1 - self.consecutive_failed_times / 5.0)

        # 时效性分数 (10分)
        time_score = 10.0
        if self.last_success_time:
            hours_since_success = (datetime.now() - self.last_success_time).total_seconds() / 3600.0
            time_score *= max(0.0, 1.0 - hours_since_success / 24.0)  # 24小时内递减

        return min(100.0, max(0.0, base_score + response_score + stability_score + time_score))

    def is_valid(self) -> bool:
        """
        检查代理是否仍然有效

        Returns:
            bool: 代理是否有效
        """
        score = self.get_score()
        return (
            score >= 60  # 综合评分大于60
            and self.status != ProxyStatus.FAILED
            and self.status != ProxyStatus.BANNED
            and (datetime.now() - self.last_check_time) < timedelta(hours=1)  # 1小时内检查过
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        序列化代理对象为字典

        Returns:
            Dict: 代理信息字典
        """
        data = {
            "ip": self.ip,
            "port": self.port,
            "source": self.source,
            "protocol": self.protocol,
            "success_rate": self.success_rate,
            "avg_response_time": self.avg_response_time,
            "last_check_time": self.last_check_time.isoformat(),
            "consecutive_failed_times": self.consecutive_failed_times,
            "total_requests": self.total_requests,
            "location": self.location,
            "anonymity": self.anonymity.value,
            "last_status_code": self.last_status_code,
            "tags": self.tags,
            "status": self.status.value,
            "created_time": self.created_time.isoformat(),
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,  #
            "score": self.get_score(),  #
            "response_times": self.response_times,
            "max_response_times": self.max_response_times,
        }
        if self.last_success_time:
            data['response_times'] = self.last_success_time.isoformat()
        return data

    def to_json(self) -> str:
        """
        序列化代理对象为 JSON

        Returns:
            str: 代理信息 JSON
        """
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ProxyModel":
        """
        从字典创建代理对象

        Args:
            data: 代理信息字典

        Returns:
            ProxyModel: 新的代理对象
        """
        # 创建数据副本，避免修改原始数据
        data = data.copy()

        # 处理 datetime 字段
        for datetime_field in ['last_check_time', 'created_time']:
            if datetime_field in data and isinstance(data[datetime_field], str):
                data[datetime_field] = datetime.fromisoformat(data[datetime_field])

        if 'last_success_time' in data and data['last_success_time']:
            data['last_success_time'] = datetime.fromisoformat(data['last_success_time'])

        # 移除不需要的字段
        for extra_field in ['score']:
            data.pop(extra_field, None)

        # 创建新实例
        return cls(**data)

    @classmethod
    def from_json(cls, json_data: str) -> "ProxyModel":
        """
        从 JSON 创建代理对象

        Args:
            json_data: 代理信息 JSON

        Returns:
            ProxyModel: 新的代理对象
        """
        return cls.from_dict(json.loads(json_data))

    def __str__(self) -> str:
        """
        代理模型字符串表示

        Returns:
            str: 代理信息的可读字符串
        """
        status = "有效" if self.is_valid() else "无效"
        return (
            f"Proxy: {self.ip}:{self.port} "
            f"({status}, "
            f"Protocol: {self.protocol}, "
            f"Success Rate: {self.success_rate:.2%}, "
            f"Avg Response Time: {self.avg_response_time:.2f}s, "
            f"Requests: {self.total_requests})"
        )

    def __eq__(self, other: object) -> bool:
        """
        判断两个代理模型是否相等

        Args:
            other: 另一个代理模型

        Returns:
            bool: 等值判断结果
        """
        if isinstance(other, ProxyModel):
            return (
                self.ip == other.ip
                and self.port == other.port
                and self.protocol == other.protocol
            )
        return False

    def __hash__(self) -> int:
        """
        计算代理模型的哈希值

        Returns:
            int: 代理模型的哈希值
        """
        return hash((self.ip, self.port, self.protocol))


if __name__ == '__main__':
    try:
        print("=== 创建代理实例 ===")
        proxy = ProxyModel(
            ip="220.248.70.237",
            port=9002,
            source="test",
            tags={"type": "http", "country": "CN"}
        )

        print("\n=== 模拟请求更新 ===")
        # 模拟一系列请求
        proxy.update_stats(True, 0.5, 200)
        proxy.update_stats(True, 0.8, 200)
        proxy.update_stats(False, 2.0, 404)
        proxy.update_stats(True, 0.6, 200)

        print("\n=== 代理状态 ===")
        print(f"Proxy: {proxy}")
        print(f"Score: {proxy.get_score():.2f}")
        print(f"Status: {proxy.status.value}")
        print(f"Valid: {proxy.is_valid()}")
        print(f"Average Response Time: {proxy.avg_response_time:.2f}s")

        print("\n=== 序列化测试 ===")
        # 测试序列化
        json_str = proxy.to_json()
        print("JSON representation:")
        print(json_str)

        print("\n=== 反序列化测试 ===")
        # 测试反序列化
        new_proxy = ProxyModel.from_json(json_str)
        print("Deserialized proxy:")
        print(new_proxy)

        print("\n=== 对象比较 ===")
        print(f"Original proxy: {proxy}")
        print(f"Deserialized proxy: {new_proxy}")
        print(f"Equal?: {proxy == new_proxy}")

    except Exception as e:
        print(f"\n发生错误: {type(e).__name__}")
        print(f"错误信息: {str(e)}")
