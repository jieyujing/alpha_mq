from abc import ABC, abstractmethod


class DataPipeline(ABC):
    VALID_STAGES = ["download", "validate", "clean", "ingest"]

    def __init__(self, config: dict):
        self.config = config
        self.stages = config["pipeline"]["stages"]

    def run(self) -> None:
        self.setup()
        try:
            if "download" in self.stages:
                self.download()
            if "validate" in self.stages:
                self.validate()
            if "clean" in self.stages:
                self.clean()
            if "ingest" in self.stages:
                self.ingest_to_qlib()
        finally:
            self.teardown()

    def setup(self):
        pass

    def teardown(self):
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