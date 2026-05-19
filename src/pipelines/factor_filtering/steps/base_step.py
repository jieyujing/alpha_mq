from __future__ import annotations

from abc import ABC, abstractmethod
from pipelines.factor_filtering.context import FilteringContext


class FilteringStep(ABC):
    """因子过滤步骤抽象基类。

    所有 Ring Step 必须继承自该基类，并实现统一的接口：
    `process(self, ctx: FilteringContext) -> FilteringContext`
    """

    @abstractmethod
    def process(self, ctx: FilteringContext) -> FilteringContext:
        """执行当前过滤/计算环逻辑，修改并返回 FilteringContext。"""
        pass
