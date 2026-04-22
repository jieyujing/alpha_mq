class SymbolAdapter:
    _TO_QLIB = {"SHSE": "SH", "SZSE": "SZ"}
    _TO_GM = {"SH": "SHSE", "SZ": "SZSE"}

    @staticmethod
    def to_qlib(gm_symbol: str) -> str:
        ex, code = gm_symbol.split(".")
        return f"{SymbolAdapter._TO_QLIB.get(ex, ex)}{code}"

    @staticmethod
    def to_gm(qlib_symbol: str) -> str:
        prefix, code = qlib_symbol[:2], qlib_symbol[2:]
        return f"{SymbolAdapter._TO_GM.get(prefix, prefix)}.{code}"