"""
Pipeline 注册表

所有可用的数据管道在此注册，供 CLI 加载使用。
"""
from pipelines.base import DataPipeline
from pipelines.data_ingest.csi1000_pipeline import CSI1000QlibPipeline
from pipelines.factor.filter_pipeline import FactorFilterPipeline
from pipelines.model.model_pipeline import ModelPipeline


PIPELINE_REGISTRY: dict[str, type[DataPipeline]] = {
    "csi1000_qlib": CSI1000QlibPipeline,
    "factor_filter": FactorFilterPipeline,
    "model": ModelPipeline,
}


def get_pipeline(name: str) -> type[DataPipeline]:
    """获取已注册的 Pipeline 类"""
    if name not in PIPELINE_REGISTRY:
        raise ValueError(f"Unknown pipeline: {name}. Available: {list(PIPELINE_REGISTRY.keys())}")
    return PIPELINE_REGISTRY[name]