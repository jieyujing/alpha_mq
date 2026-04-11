# tests/test_checkpoint.py
import os
from data.scripts.download_gm import get_downloaded_symbols

def test_get_downloaded(tmp_path):
    # 创建模拟目录
    category_dir = tmp_path / "valuation"
    category_dir.mkdir()
    (category_dir / "SHSE.600000.csv").touch()
    (category_dir / "SZSE.000001.csv").touch()
    
    symbols = get_downloaded_symbols(str(category_dir))
    assert "SHSE.600000" in symbols
    assert "SZSE.000001" in symbols
    assert "SZSE.000002" not in symbols
