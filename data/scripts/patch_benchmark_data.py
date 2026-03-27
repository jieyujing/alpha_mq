import pandas as pd
from pathlib import Path
from gm.api import set_token, history
from data.utils.env_utils import get_gm_token
import subprocess
import sys

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
                existing_dates = set(line.strip() for line in f.readlines() if line.strip())
            all_dates = sorted(existing_dates | set(dates))
        else:
            all_dates = sorted(set(dates))
            
        with open(cal_path, 'w', encoding='utf-8') as f:
            for dt in all_dates:
                f.write(f"{dt}\n")
    print("元数据更新完成。")

def run_dump(csv_path: Path, qlib_dir: Path):
    """
    通过 subprocess 调用 dump_bin.py 将 CSV 转换为 Qlib 二进制格式。
    """
    print(f"正在调用 dump_bin.py 转换 {csv_path.name}...")
    dump_script = Path("data/scripts/dump_bin.py")
    
    # 构造命令
    # dump_all 会扫描整个 data_path 下的所有 .csv 文件并将其转换为 Qlib 二进制格式。
    # 这里我们指向 csv_path.parent (data/csv_source/)。
    # 为了避免全量重新转换，Qlib 的 dump_all 逻辑通常会覆盖现有文件。
    # 因为我们只想补丁中证1000，这里我们假设 csv_source 下只有当前这一个文件，
    # 或者我们通过 --limit_nums 限制，或者 dump_bin 自己的逻辑就是每个文件独立。
    cmd = [
        sys.executable, str(dump_script), "dump_all",
        "--data_path", str(csv_path.parent),
        "--qlib_dir", str(qlib_dir),
        "--include_fields", "open,high,low,close,volume,amount",
        "--symbol_field_name", "symbol"
    ]
    
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print("转换出错：")
        print(result.stderr)
    else:
        print("二进制转换完成。")
        print(result.stdout)

def main():
    """
    主程序流程：下载 -> 转换 CSV -> 同步元数据 -> 二进制 Dump。
    """
    qlib_dir = Path("data/qlib_data")
    csv_file = Path("data/csv_source/SH000852.csv")
    
    # 1. 下载
    try:
        df = fetch_index_data(symbol="SHSE.000852", start="2015-01-01")
    except Exception as e:
        print(f"下载失败: {e}")
        return

    # 2. 处理并保存 CSV
    dates = process_to_csv(df, csv_file)

    # 3. 同步元数据
    update_metadata(qlib_dir, 'SH000852', dates)

    # 4. 执行二进制 Dump
    run_dump(csv_file, qlib_dir)
    
    print("\n[成功] 中证1000指数数据补丁已完成。")

if __name__ == "__main__":
    main()
