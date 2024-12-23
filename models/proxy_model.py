"""
----------------------------------------------------------------
File name:                  proxy_model.py
Author:                     Ignorant-lu
Date created:               2024/12/17
Description:                代理模型定义模块
----------------------------------------------------------------

Changed history:            定义代理模型,包含统计特征
----------------------------------------------------------------
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any
from datetime import datetime
import ipaddress
import json


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
    anonymity: Optional[str] = None
    last_status_code: Optional[int] = None
    tags: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        """验证初始化参数"""
        self.validate()

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

    def is_valid(self) -> bool:
        """
        检查代理是否仍然有效

        Returns:
            bool: 代理是否有效
        """
        # 阈值设置
        return (
            self.success_rate >= 0.3
            and self.consecutive_failed_times <= 5
            and self.avg_response_time < 10.0
            # and self.total_requests >= 100
        )

    def to_dict(self) -> Dict[str, Any]:
        """
        序列化代理对象为字典

        Returns:
            Dict: 代理信息字典
        """
        return {
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
            "anonymity": self.anonymity,
            "last_status_code": self.last_status_code,
            "tags": self.tags,
        }

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
        # 处理 datetime 字段
        if 'last_check_time' in data:
            data['last_check_time'] = datetime.fromisoformat(data['last_check_time'])

        return cls(**data)

    @classmethod
    def from_json(cls, json_str: str) -> "ProxyModel":
        """
        从 JSON 创建代理对象

        Args:
            json_str: 代理信息 JSON

        Returns:
            ProxyModel: 新的代理对象
        """
        return cls.from_dict(json.loads(json_str))

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
    # 测试用例
    proxy = ProxyModel(
        ip="192.168.1.1",
        port=8080,
        source="test",
        tags={"type": "http", "country": "CN"}
    )

    # 测试更新统计
    proxy.update_stats(True, 0.5, 200)
    proxy.update_stats(False, 1.0, 404)

    # 测试序列化
    proxy_dict = proxy.to_dict()
    proxy_json = proxy.to_json()

    # 测试反序列化
    new_proxy = ProxyModel.from_json(proxy_json)

    print(f"Original proxy: {proxy}")
    print(f"Deserialized proxy: {new_proxy}")
    print(f"Equal?: {proxy == new_proxy}")
