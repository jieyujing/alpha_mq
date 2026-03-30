import pytest
import pandas as pd
from pathlib import Path
import sys

_root = Path(__file__).parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from data.handler import Alpha158PathTargetHandler
from path_target import PathTargetConfig


# pytest fixture for qlib initialization
@pytest.fixture(scope="module")
def qlib_initialized():
    """Initialize qlib once for all tests in this module."""
    import qlib
    from qlib.constant import REG_CN

    provider_uri = Path(__file__).parent.parent / "data" / "qlib_data"
    qlib.init(provider_uri=str(provider_uri), region=REG_CN)
    return True


class TestAlpha158PathTargetHandler:
    """测试 Alpha158PathTargetHandler 类"""

    def test_handler_init_with_defaults(self, qlib_initialized):
        """测试默认参数初始化"""
        _ = qlib_initialized  # 触发 qlib 初始化
        # 使用少量 instruments 避免 qlib "all" instruments 问题
        handler = Alpha158PathTargetHandler(
            start_time="2024-01-01",
            end_time="2024-01-31",
            instruments=["SH600006"],
        )
        assert handler.benchmark == "SH000852"
        assert handler.beta_window == 60
        assert handler.target_cfg is not None

    def test_handler_init_with_custom_config(self, qlib_initialized):
        """测试自定义参数初始化"""
        _ = qlib_initialized  # 触发 qlib 初始化
        custom_config = PathTargetConfig(
            vol_window=30,
            k_upper=1.5,
            k_lower=1.5,
            max_holding=5,
        )
        handler = Alpha158PathTargetHandler(
            benchmark="SH000300",
            path_target_config=custom_config,
            beta_window=40,
            start_time="2024-01-01",
            end_time="2024-01-31",
            instruments=["SH600006"],
        )
        assert handler.benchmark == "SH000300"
        assert handler.beta_window == 40
        assert handler.target_cfg.vol_window == 30

    def test_handler_init_with_custom_beta_window(self, qlib_initialized):
        """测试自定义 beta_window 参数"""
        _ = qlib_initialized  # 触发 qlib 初始化
        handler = Alpha158PathTargetHandler(
            beta_window=30,
            start_time="2024-01-01",
            end_time="2024-01-31",
            instruments=["SH600006"],
        )
        assert handler.beta_window == 30
        assert handler.benchmark == "SH000852"  # 默认值

    def test_handler_target_cfg_defaults(self, qlib_initialized):
        """测试 target_cfg 使用 PathTargetConfig 默认值"""
        _ = qlib_initialized  # 触发 qlib 初始化
        handler = Alpha158PathTargetHandler(
            start_time="2024-01-01",
            end_time="2024-01-31",
            instruments=["SH600006"],
        )
        # 验证 PathTargetConfig 默认值
        assert handler.target_cfg.vol_window == 20
        assert handler.target_cfg.k_upper == 2.0
        assert handler.target_cfg.k_lower == 2.0
        assert handler.target_cfg.max_holding == 10
        assert handler.target_cfg.lamda == 1.0
        assert handler.target_cfg.beta_alpha == 0.5

    def test_handler_fetch_returns_multiindex(self, qlib_initialized):
        """测试 fetch 返回 MultiIndex DataFrame"""
        _ = qlib_initialized  # 触发 qlib 初始化
        handler = Alpha158PathTargetHandler(
            start_time="2024-01-01",
            end_time="2024-01-31",
            instruments=["SH600006", "SH600012"],
        )

        # 不传递 col_set 参数，让 handler 使用默认行为
        df = handler.fetch()

        # 检查返回格式
        assert isinstance(df, pd.DataFrame)
        assert isinstance(df.columns, pd.MultiIndex)

        # 检查包含 FEATURE 和 LABEL (handler 内部转换为大写)
        column_levels = df.columns.get_level_values(0).unique()
        assert "FEATURE" in column_levels
        assert "LABEL" in column_levels

        # 检查 label 值范围 (0, 1)
        label_values = df[("LABEL", "target")].dropna()
        assert label_values.min() >= 0
        assert label_values.max() <= 1

    def test_handler_fetch_with_instruments_list(self, qlib_initialized):
        """测试使用 instruments 列表的 fetch"""
        _ = qlib_initialized  # 触发 qlib 初始化
        # 使用少量 instruments 进行快速测试
        instruments = ["SH600006", "SH600012"]
        start_time = "2024-01-01"
        end_time = "2024-02-01"

        cfg = PathTargetConfig(max_holding=2)  # Short holding for fast test
        handler = Alpha158PathTargetHandler(
            instruments=instruments,
            start_time=start_time,
            end_time=end_time,
            path_target_config=cfg,
        )

        df = handler.fetch()

        assert isinstance(df, pd.DataFrame)
        column_levels = df.columns.get_level_values(0).unique()
        assert "FEATURE" in column_levels
        assert "LABEL" in column_levels
        # 检查自定义 label 'target' 存在
        assert "target" in df["LABEL"].columns

    def test_handler_fetch_label_range_with_short_holding(self, qlib_initialized):
        """测试短持有期的 label 范围"""
        _ = qlib_initialized  # 触发 qlib 初始化
        # 使用极短的持有期和更宽松的屏障
        cfg = PathTargetConfig(
            max_holding=3,
            k_upper=1.0,
            k_lower=1.0,
            vol_window=5,
        )
        handler = Alpha158PathTargetHandler(
            start_time="2024-01-01",
            end_time="2024-01-20",
            instruments=["SH600006"],
            path_target_config=cfg,
        )

        df = handler.fetch()

        # 确保获取到数据
        assert not df.empty

        # 检查 label 列
        label_col = df[("LABEL", "target")]
        non_null_labels = label_col.dropna()

        # 短持有期可能产生更多 NaN（因为需要足够数据计算）
        if len(non_null_labels) > 0:
            assert non_null_labels.min() >= 0
            assert non_null_labels.max() <= 1


class TestPathTargetConfigIntegration:
    """测试 PathTargetConfig 与 Handler 的集成"""

    def test_config_passed_correctly(self, qlib_initialized):
        """测试配置正确传递给 Handler"""
        _ = qlib_initialized  # 触发 qlib 初始化
        config = PathTargetConfig(
            vol_window=15,
            k_upper=3.0,
            k_lower=3.0,
            max_holding=20,
            lamda=2.0,
            beta_alpha=1.0,
        )
        handler = Alpha158PathTargetHandler(
            path_target_config=config,
            start_time="2024-01-01",
            end_time="2024-01-31",
            instruments=["SH600006"],
        )

        # 验证所有参数正确传递
        assert handler.target_cfg.vol_window == 15
        assert handler.target_cfg.k_upper == 3.0
        assert handler.target_cfg.k_lower == 3.0
        assert handler.target_cfg.max_holding == 20
        assert handler.target_cfg.lamda == 2.0
        assert handler.target_cfg.beta_alpha == 1.0

    def test_none_config_uses_defaults(self, qlib_initialized):
        """测试 None 配置使用默认值"""
        _ = qlib_initialized  # 触发 qlib 初始化
        handler = Alpha158PathTargetHandler(
            path_target_config=None,
            start_time="2024-01-01",
            end_time="2024-01-31",
            instruments=["SH600006"],
        )

        # 验证使用默认 PathTargetConfig
        default_config = PathTargetConfig()
        assert handler.target_cfg.vol_window == default_config.vol_window
        assert handler.target_cfg.k_upper == default_config.k_upper
        assert handler.target_cfg.max_holding == default_config.max_holding