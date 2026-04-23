# src/pipelines/base.py
from abc import ABC, abstractmethod


class DataPipeline(ABC):
    # Subclasses override this to define their own stages and method mapping
    STAGE_METHOD_MAP: dict[str, str] = {
        "download": "download",
        "validate": "validate",
        "clean": "clean",
        "ingest": "ingest_to_qlib",
    }

    def __init__(self, config: dict):
        self.config = config
        self.stages = config["pipeline"]["stages"]
        self._completed = False

    def run(self) -> None:
        self.setup()
        try:
            for stage in self.stages:
                method_name = self.STAGE_METHOD_MAP.get(stage)
                if method_name is None:
                    raise ValueError(f"Unknown stage: {stage}. Map: {self.STAGE_METHOD_MAP}")
                method = getattr(self, method_name)
                result = method()
                # validate stage returns a list of errors; check if non-empty
                if stage == "validate" and result:
                    fail_on_error = self.config.get("pipeline", {}).get("validate", {}).get("fail_on_error", False)
                    if fail_on_error:
                        raise RuntimeError(f"Validation failed: {result}")
            self._completed = True
            self.on_success()
        finally:
            self.teardown()

    def setup(self):
        pass

    def teardown(self):
        """资源清理（无论成功或失败都会执行）"""
        pass

    def on_success(self):
        """成功完成后的回调（只有所有 stage 成功完成才执行）"""
        pass

    @abstractmethod
    def download(self):
        ...

    @abstractmethod
    def validate(self):
        ...

    @abstractmethod
    def clean(self):
        ...

    @abstractmethod
    def ingest_to_qlib(self):
        ...
