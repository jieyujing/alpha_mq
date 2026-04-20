import os
import pandas as pd
from datetime import datetime
from tqdm import tqdm
from gm.api import set_token, history

# ---------------------------------------------------------
# 1. 配置与标的定义
# ---------------------------------------------------------

# 使用掘金 (GM) SDK 的 Token (已根据 gm_skill 与 main.py 同步)
TOKEN = "478dc4635c5198dbfcc962ac3bb209e5327edbff"
set_token(TOKEN)

# 目标 ETFs 池 (直接从 main.py 复制，确保一致性)
FULL_ETF_POOL = {
    'SHSE.513120': '港股创新药ETF',
    'SZSE.159301': '公用事业ETF',
    'SZSE.159869': '游戏ETF',
    'SHSE.511260': '10年期国债ETF',
    'SHSE.511090': '30年期国债ETF',
    'SHSE.511380': '可转债ETF',
    'SHSE.518800': '黄金ETF',
    'SHSE.510300': '沪深300ETF',
    'SZSE.159915': '创业板ETF',
    'SHSE.513920': '港股通央企红利ETF',
    'SZSE.159920': '恒生ETF',
    'SZSE.159742': '恒生科技ETF',
    'SZSE.159941': '纳指ETF',
    'SHSE.501018': '南方原油ETF',
    'SZSE.162411': '华宝油气ETF'
}

# 数据存储目录
OUTPUT_DIR = "data/etf_history"

def download_etf_data(start_date: str = "2015-01-01", end_date: str = None):
    """
    下载 ETF 池中的历史行情数据并保存到本地 CSV
    """
    if end_date is None:
        end_date = datetime.now().strftime("%Y-%m-%d")
        
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)
        print(f"创建目录: {OUTPUT_DIR}")

    print(f"开始下载 ETF 数据: {start_date} 至 {end_date}")
    
    # 字段包含: 代码, 时间, 开盘, 最高, 最低, 收盘, 成交量, 成交额
    fields = 'symbol,bob,open,high,low,close,volume,amount'
    
    results_summary = []

    for symbol, name in tqdm(FULL_ETF_POOL.items(), desc="下载进度"):
        try:
            # 调用 history 接口获取日线数据
            df = history(
                symbol=symbol, 
                frequency='1d', 
                start_time=start_date, 
                end_time=end_date, 
                fields=fields, 
                df=True
            )
            
            if df is None or df.empty:
                print(f"\n[警告] {symbol} ({name}) 未获取到数据。")
                continue
                
            # 格式化日期并将时区信息移除 (Parquet/CSV 兼容性处理)
            df['bob'] = pd.to_datetime(df['bob']).dt.tz_localize(None)
            
            # 排序
            df = df.sort_values('bob')
            
            # 保存文件 (格式: 代码_名称.csv)
            file_name = f"{symbol}_{name}.csv"
            file_path = os.path.join(OUTPUT_DIR, file_name)
            df.to_csv(file_path, index=False, encoding='utf-8-sig') # 使用 utf-8-sig 方便 Excel 直接打开
            
            results_summary.append({
                'Symbol': symbol,
                'Name': name,
                'Start': df['bob'].min().strftime('%Y-%m-%d'),
                'End': df['bob'].max().strftime('%Y-%m-%d'),
                'Count': len(df)
            })
            
        except Exception as e:
            print(f"\n[错误] 下载 {symbol} ({name}) 时发生异常: {e}")

    # 打印总结表
    if results_summary:
        print("\n\n" + "="*50)
        print(f"{'代码':<12} | {'名称':<15} | {'起始':<10} | {'结束':<10} | {'数量'}")
        print("-" * 50)
        for res in results_summary:
            print(f"{res['Symbol']:<12} | {res['Name']:<15} | {res['Start']:<10} | {res['End']:<10} | {res['Count']}")
        print("="*50)
        print(f"所有数据已保存至: {os.path.abspath(OUTPUT_DIR)}")
    else:
        print("\n未下载到任何数据。")

if __name__ == "__main__":
    # 默认下载从 2015 年至今的数据
    download_etf_data()
