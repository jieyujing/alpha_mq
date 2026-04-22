from core.symbol import SymbolAdapter


def test_symbol_conversion():
    assert SymbolAdapter.to_qlib("SHSE.600000") == "SH600000"
    assert SymbolAdapter.to_gm("SZ000001") == "SZSE.000001"