"""
GM 数据下载器基类

定义下载流程骨架，子类实现特定逻辑。
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List
import logging


class GMDownloader(ABC):
    """
    GM 数据下载器抽象基类

    子类需实现:
    - get_target_pool(): 获取目标标的池
    - get_categories(): 获取数据类别配置
    - run(): 执行下载流程
    """

    def __init__(self, config: Dict):
        self.config = config
        self.exports_base = Path(config.get("exports_base", "data/exports"))
        self.limiter = None  # 子类初始化

    @abstractmethod
    def get_target_pool(self) -> List[str]:
        """获取目标标的池"""
        pass

    @abstractmethod
    def get_categories(self) -> Dict:
        """获取数据类别配置"""
        pass

    @abstractmethod
    def run(self):
        """执行完整下载流程"""
        pass

    def setup(self):
        """创建输出目录"""
        self.exports_base.mkdir(parents=True, exist_ok=True)
        for category in self.get_categories().keys():
            cat_dir = self.exports_base / category
            cat_dir.mkdir(parents=True, exist_ok=True)
        logging.info(f"Downloader setup complete: {self.exports_base}")