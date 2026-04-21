# tests/test_etf_portfolio/test_workflow.py
import pytest
from src.etf_portfolio.workflow import DownloadWorkflow, HistoryWorkflow

class MockDataSource:
    """测试用模拟数据源"""
    def __init__(self):
        self.fetch_count = 0

    def fetch_history(self, symbol, start_time, end_time, **kw):
        self.fetch_count += 1
        import pandas as pd
        return pd.DataFrame({"symbol": [symbol], "close": [100.0]})

def test_workflow_template_method():
    """验证模板方法调用 get_categories"""
    source = MockDataSource()
    workflow = HistoryWorkflow(source=source)
    categories = workflow.get_categories()
    assert "history_1d" in categories

def test_workflow_can_override_categories():
    """验证子类可覆盖 get_categories"""
    source = MockDataSource()

    class MinuteWorkflow(DownloadWorkflow):
        def get_categories(self):
            return ["history_1m"]

    workflow = MinuteWorkflow(source=source)
    categories = workflow.get_categories()
    assert categories == ["history_1m"]

def test_workflow_get_category_fetcher():
    """验证 get_category_fetcher 返回正确函数"""
    source = MockDataSource()
    workflow = HistoryWorkflow(source=source)

    fetcher = workflow.get_category_fetcher("history_1d")
    assert fetcher is not None
    assert callable(fetcher)