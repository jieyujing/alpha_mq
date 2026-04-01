import re
from typing import Tuple, Optional
from datetime import datetime

class FuturesSymbolConverter:
    """
    期货品种命名转换工具 (CTP <-> GM 掘金量化)
    
    支持交易所: CFFEX, SHFE, DCE, CZCE, INE, GFEX
    支持类型: 普通合约 (History), 期权合约 (Option), 主力/连续合约 (Main)
    """

    # 交易所大小写/代码映射 (GM -> 交易所全名)
    EXCHANGES = ["CFFEX", "SHFE", "DCE", "CZCE", "INE", "GFEX"]
    
    # 交易所对应主品种代码是否全大写 (用于主力合约转换)
    UPPERCASE_EXCHANGES = ["CFFEX", "CZCE"]

    def __init__(self, main_contract_format: str = "NAME.EXCHANGE"):
        """
        :param main_contract_format: 主力合约格式。
            "NAME.EXCHANGE" (默认, 遵循用户 Rule 1): 如 RB.SHFE, IF.CFFEX
            "EXCHANGE.NAME" (掘金标准): 如 SHFE.RB, CFFEX.IF
        """
        self.main_format = main_contract_format.upper()

    def ctp_to_gm(self, ctp_symbol: str, exchange: str) -> str:
        """
        CTP 合约 ID 转换为掘金 Symbol (如 rb2110 + SHFE -> SHFE.rb2110)
        """
        exchange = exchange.upper()
        if exchange not in self.EXCHANGES:
            raise ValueError(f"Unknown exchange: {exchange}")

        # 如果是主力合约 (不包含数字)
        if re.fullmatch(r"[a-zA-Z]+", ctp_symbol):
            symbol = ctp_symbol.upper() if exchange in self.UPPERCASE_EXCHANGES else ctp_symbol.lower()
            if self.main_format == "NAME.EXCHANGE":
                return f"{symbol.upper()}.{exchange}"
            else:
                return f"{exchange}.{symbol.upper()}"

        # 如果是普通合约或期权合约
        # 直接拼接前缀即可，因为 CTP 内部格式在 CFFEX/CZCE 下大写，其他下小写，这与掘金一致
        # 但我们强制纠正一遍大小写以防 CTP 传入参数不规范
        if exchange in self.UPPERCASE_EXCHANGES:
            return f"{exchange}.{ctp_symbol.upper()}"
        else:
            # SHFE/DCE/INE/GFEX: 品种部分通常是小写
            # 这点需要区分期权中的 C/P 标识（通常大写）
            return f"{exchange}.{ctp_symbol}"

    def gm_to_ctp(self, gm_symbol: str) -> Tuple[str, str]:
        """
        掘金 Symbol 转换为 CTP 格式 (如 SHFE.rb2110 -> (rb2110, SHFE))
        或者主力合约转换 (如 RB.SHFE -> (rb, SHFE))
        """
        # 情况1: 品种.交易所 (用户自定义主力格式)
        if "." in gm_symbol:
            parts = gm_symbol.split(".")
            # 判断是在哪一端 (通过交易所列表匹配)
            if parts[1].upper() in self.EXCHANGES:
                exchange = parts[1].upper()
                symbol_part = parts[0]
            elif parts[0].upper() in self.EXCHANGES:
                exchange = parts[0].upper()
                symbol_part = parts[1]
            else:
                raise ValueError(f"Invalid GM symbol: {gm_symbol}")
            
            # 根据交易所规范 CTP 的大小写
            if exchange in self.UPPERCASE_EXCHANGES:
                ctp_symbol = symbol_part.upper()
            else:
                # 期货合约名部分小写 (期权 C/P 除外)
                # 为简单起见，如果是纯字母主力合约，转小写；如果是合约名，不做强制改变
                if re.fullmatch(r"[a-zA-Z]+", symbol_part):
                    ctp_symbol = symbol_part.lower()
                else:
                    ctp_symbol = symbol_part
                    
            return ctp_symbol, exchange
        else:
            raise ValueError(f"GM symbol {gm_symbol} mush contain a dot ('.')")

    @staticmethod
    def parse_czce_year(ctp_symbol: str, pivot_year: Optional[int] = None) -> int:
        """
        解析郑商所 1 位年份。
        示例: TA910 -> 201910 或 202910
        :param ctp_symbol: 如 'TA910'
        :param pivot_year: 基准年份，默认当前年。
        :return: 完整的 4 位年份数字
        """
        if pivot_year is None:
            pivot_year = datetime.now().year
            
        # 寻找代码中的数字部分
        match = re.search(r"(\d)(\d{2})", ctp_symbol)
        if not match:
            raise ValueError(f"Invalid CZCE symbol format: {ctp_symbol}")
            
        y_digit = int(match.group(1)) # 1位年
        
        # 寻找最接近 pivot_year 且个位为 y_digit 的年份
        # 方法：计算 pivot_year 与目标 y_digit 的偏离度，选取绝对值最小的 10 年倍数
        # target_year = 10 * k + y_digit
        # 我们寻找 k 使得 abs(10 * k + y_digit - pivot_year) 最小
        k = round((pivot_year - y_digit) / 10)
        candidate_year = 10 * k + y_digit
        
        return candidate_year


if __name__ == "__main__":
    # 测试代码
    converter = FuturesSymbolConverter(main_contract_format="NAME.EXCHANGE")
    
    # 1. 期货合约测试
    print(f"CTP -> GM (SHFE rb2110): {converter.ctp_to_gm('rb2110', 'SHFE')}") # SHFE.rb2110
    print(f"CTP -> GM (CZCE TA910):  {converter.ctp_to_gm('TA910', 'CZCE')}")  # CZCE.TA910
    
    # 2. 主力合约测试 (用户规则: NAME.EXCHANGE)
    print(f"Main -> GM (RB SHFE):    {converter.ctp_to_gm('rb', 'SHFE')}")     # RB.SHFE
    
    # 3. 期权合约测试 (带连字符 / 紧凑)
    print(f"Option -> GM (DCE m2110-C-5000): {converter.ctp_to_gm('m2110-C-5000', 'DCE')}") # DCE.m2110-C-5000
    
    # 4. 反向转换
    print(f"GM -> CTP (SHFE.rb2110):  {converter.gm_to_ctp('SHFE.rb2110')}")   # ('rb2110', 'SHFE')
    print(f"GM -> CTP (RB.SHFE):      {converter.gm_to_ctp('RB.SHFE')}")       # ('rb', 'SHFE')
    
    # 5. 郑商所年份解析
    full_year = converter.parse_czce_year('TA910', pivot_year=2026)
    print(f"Year 解析 (TA910, base 2026): {full_year}") # 2029 (假设是远月)
    full_year_old = converter.parse_czce_year('TA910', pivot_year=2021)
    print(f"Year 解析 (TA910, base 2021): {full_year_old}") # 2019 (假设是过去)
