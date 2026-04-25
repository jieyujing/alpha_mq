"""Model training pipeline: pluggable models with template pattern."""
from pipelines.model.base_model import BaseModel, get_model

__all__ = ["BaseModel", "get_model"]
