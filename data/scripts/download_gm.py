# data/scripts/download_gm.py
import time
import collections
import random
import os
import glob
import logging
import pandas as pd
from tqdm import tqdm
from tenacity import retry, wait_exponential, stop_after_attempt
from gm.api import set_token, stk_get_index_constituents, history
from gm.api import stk_get_daily_valuation, stk_get_daily_basic, stk_get_daily_mktvalue
from gm.api import stk_get_fundamentals_balance, stk_get_fundamentals_income, stk_get_fundamentals_cashflow

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class RateLimiter:
    """
    掘金 API 流控拦截器
    限制: 1000次/5分钟 (300秒)
    本实现采用滑动窗口，并预留安全边界 (max_req=950)
    """
    def __init__(self, max_req=950, window=300):
        self.max_req = max_req
        self.window = window
        self.history = collections.deque()
        self.min_interval = 0.35  # 两次请求间的最小基础间隔

    def wait(self):
        now = time.time()
        # 移除窗口外的历史记录
        while self.history and now - self.history[0] > self.window:
            self.history.popleft()
            
        # 如果达到窗口上限，阻塞直到最早的记录滑出窗口
        if len(self.history) >= self.max_req:
            sleep_time = self.window - (now - self.history[0]) + 0.1
            logging.warning(f"Rate limit approaching. Sleeping for {sleep_time:.2f}s")
            time.sleep(sleep_time)
            
        # 基础间隔控制 + Jitter 抖动
        now = time.time()
        if self.history and now - self.history[-1] < self.min_interval:
            jitter = random.uniform(0.05, 0.15)
            wait_time = self.min_interval - (now - self.history[-1]) + jitter
            time.sleep(max(0, wait_time))
            
        self.history.append(time.time())

def get_downloaded_symbols(category_dir: str) -> set:
    """
    检查指定目录下已经下载成功的 CSV 文件，返回 symbol 集合
    """
    if not os.path.isdir(category_dir):
        return set()
    csv_files = glob.glob(os.path.join(category_dir, "*.csv"))
    # 从文件名提取 symbol (剔除 .csv 后缀)
    symbols = {os.path.basename(f).replace('.csv', '') for f in csv_files}
    return symbols

def clean_df_tz(df):
    """移除 DataFrame 中的时区信息，以便保存"""
    if df is None or df.empty:
        return df
    # 查找所有带时区的 datetime 列
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            if df[col].dt.tz is not None:
                df[col] = df[col].dt.tz_localize(None)
    return df

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def fetch_safe(func, *args, **kwargs):
    """带重试机制的 API 调用"""
    try:
        df = func(*args, **kwargs)
        return clean_df_tz(df)
    except Exception as e:
        logging.error(f"Error calling {func.__name__}: {e}")
        raise

def download_category_data(base_pool, category_name, fetch_func, limiter, start_date, end_date, fields=None):
    """
    通用分类数据下载逻辑
    """
    category_dir = os.path.join("data", "exports", category_name)
    os.makedirs(category_dir, exist_ok=True)
    
    downloaded = get_downloaded_symbols(category_dir)
    to_download = [s for s in base_pool if s not in downloaded]
    
    if not to_download:
        logging.info(f"All symbols in {category_name} already downloaded.")
        return

    logging.info(f"Downloading {category_name} for {len(to_download)} symbols...")
    
    for symbol in tqdm(to_download, desc=f"Downloading {category_name}"):
        limiter.wait()
        try:
            kwargs = {
                'symbol': symbol,
                'start_date': start_date,
                'end_date': end_date,
                'df': True
            }
            if fields:
                kwargs['fields'] = fields
                
            df = fetch_safe(fetch_func, **kwargs)
            
            if df is not None and not df.empty:
                save_path = os.path.join(category_dir, f"{symbol}.csv")
                df.to_csv(save_path, index=False)
            else:
                logging.debug(f"No data for {symbol} in {category_name}")
        except Exception as e:
            logging.error(f"Failed to download {category_name} for {symbol}: {e}")

def run_download_workflow(token, start_date, end_date):
    """执行完整的数据下载工作流"""
    set_token(token)
    limiter = RateLimiter(max_req=950)
    
    # 1. 获取中证 1000 最新成分股
    logging.info("Fetching CSI 1000 constituents...")
    constituents = stk_get_index_constituents(index='SHSE.000852')
    if constituents is None or constituents.empty:
        logging.error("Failed to fetch constituents. Exiting.")
        return
    
    symbols = constituents['symbol'].tolist()
    # 加入指数自身，用于下载基准行情
    base_pool = symbols + ['SHSE.000852']
    
    # 2. 下载历史行情 (history)
    # 这里的 history 接口在 gm 3.x 以后支持多支股票查询，但为了简单和断点续传，我们仍以 symbol 为单位保存
    download_category_data(base_pool, "history_1d", history, limiter, start_date, end_date)
    
    # 3. 下载日频估值 (valuation)
    # 指数本身通常没有估值和基本面数据，过滤掉
    stock_pool = [s for s in symbols]
    
    valuation_fields = "pe_ttm,pb_mrq,ps_ttm,pcf_ttm_oper"
    download_category_data(stock_pool, "valuation", stk_get_daily_valuation, limiter, start_date, end_date, fields=valuation_fields)
    
    # 4. 下载市值数据 (mktvalue)
    mktvalue_fields = "tot_mv,a_mv"
    download_category_data(stock_pool, "mktvalue", stk_get_daily_mktvalue, limiter, start_date, end_date, fields=mktvalue_fields)

    # 5. 下载基础指标 (basic)
    basic_fields = "tclose,turnrate,ttl_shr,circ_shr"
    download_category_data(stock_pool, "basic", stk_get_daily_basic, limiter, start_date, end_date, fields=basic_fields)

    # 6. 下载基本面 (财务报表)
    # 财务报表通常按季度，这里我们根据日期范围拉取
    logging.info("Downloading Fundamental reports...")
    fundamental_tasks = [
        ("balance", stk_get_fundamentals_balance),
        ("income", stk_get_fundamentals_income),
        ("cashflow", stk_get_fundamentals_cashflow)
    ]
    
    for name, func in fundamental_tasks:
        download_category_data(stock_pool, f"fundamentals_{name}", func, limiter, start_date, end_date)

    logging.info("Download workflow completed.")

if __name__ == "__main__":
    import argparse
    from datetime import datetime, timedelta
    
    parser = argparse.ArgumentParser(description="Download CSI 1000 Data from GM")
    parser.add_argument("--token", type=str, help="GM SDK Token")
    parser.add_argument("--start", type=str, default=(datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"), help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=datetime.now().strftime("%Y-%m-%d"), help="End date (YYYY-MM-DD)")
    
    args = parser.parse_args()
    
    # 优先从环境变量读取 TOKEN
    token = args.token or os.getenv("GM_TOKEN")
    if not token:
        print("Error: No token provided. Use --token or set GM_TOKEN environment variable.")
    else:
        run_download_workflow(token, args.start, args.end)
