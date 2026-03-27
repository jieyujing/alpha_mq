import pandas as pd
from pathlib import Path
from gm.api import set_token, history
from data.utils.env_utils import get_gm_token

def fetch_index_data(symbol="SHSE.000852", start="2015-01-01"):
    """
    使用掘金 API 下载中证1000指数数据。
    """
    token = get_gm_token()
    set_token(token)
    # 获取当前日期作为结束日期
    end_date = pd.Timestamp.now().strftime('%Y-%m-%d')
    print(f"正在从掘金下载 {symbol} 行情数据 ({start} 至 {end_date})...")
    df = history(
        symbol=symbol, 
        frequency='1d', 
        start_time=start, 
        end_time=end_date, 
        df=True
    )
    if df is None or df.empty:
        raise ValueError(f"未能获取到 {symbol} 的行情数据，请检查 Token 或网络。")
    return df

def process_to_csv(df, output_path: Path):
    """
    将下载的 DataFrame 转换为 Qlib 兼容的 CSV 格式。
    """
    print(f"正在转换数据并保存至 {output_path}...")
    # 时间点处理
    df['date'] = pd.to_datetime(df['bob']).dt.strftime('%Y-%m-%d')
    # 符号标准化 SHSE.000852 -> SH000852
    df['symbol'] = df['symbol'].replace('SHSE.000852', 'SH000852')
    
    # 选定 Qlib 基础行情字段
    cols = ['symbol', 'date', 'open', 'high', 'low', 'close', 'volume', 'amount']
    df_clean = df[cols].copy()
    
    # 确保输出目录存在
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df_clean.to_csv(output_path, index=False)
    return df_clean['date'].unique().tolist()

def update_metadata(qlib_dir: Path, symbol='SH000852', dates=None):
    """
    同步 Qlib 的 instruments 和 calendars。
    """
    print(f"正在更新 Qlib 元数据 ({symbol})...")
    # 1. 更新 instruments/all.txt
    inst_path = qlib_dir / "instruments" / "all.txt"
    inst_path.parent.mkdir(parents=True, exist_ok=True)
    
    start_date = dates[0]
    end_date = dates[-1]
    new_line = f"{symbol}\t{start_date}\t{end_date}\n"
    
    if inst_path.exists():
        with open(inst_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 查找是否已有该符号，有则更新，无则追加
        found = False
        new_lines = []
        for line in lines:
            if line.startswith(f"{symbol}\t"):
                new_lines.append(new_line)
                found = True
            else:
                new_lines.append(line)
        
        if not found:
            new_lines.append(new_line)
            
        with open(inst_path, 'w', encoding='utf-8') as f:
            f.writelines(new_lines)
    else:
        with open(inst_path, 'w', encoding='utf-8') as f:
            f.write(new_line)

    # 2. 更新 calendars/day.txt
    cal_path = qlib_dir / "calendars" / "day.txt"
    cal_path.parent.mkdir(parents=True, exist_ok=True)
    
    if dates:
        if cal_path.exists():
            with open(cal_path, 'r', encoding='utf-8') as f:
                existing_dates = set(l.strip() for l in f.readlines() if l.strip())
            all_dates = sorted(existing_dates | set(dates))
        else:
            all_dates = sorted(set(dates))
            
        with open(cal_path, 'w', encoding='utf-8') as f:
            for d in all_dates:
                f.write(f"{d}\n")
    print("元数据更新完成。")
