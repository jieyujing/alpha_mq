"""因子筛选流水线主编排器。"""

import yaml
from pathlib import Path


class FactorFilteringPipeline:
    """按序执行各阶段因子筛选步骤的流水线编排器。"""

    def __init__(self, config_path: str):
        with open(config_path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)
        self.steps: list = []

    def add_step(self, step) -> None:
        """添加一个处理步骤到流水线。"""
        self.steps.append(step)

    def run(self, df):
        """依次执行所有步骤，返回最终 DataFrame。"""
        for step in self.steps:
            df = step.process(df)
        return df
