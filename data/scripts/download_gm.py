# data/scripts/download_gm.py
"""
GM 数据下载脚本 - 使用重构后的架构。
"""
import time
import collections
import random
import os
import glob
import logging
import pandas as pd
from tqdm import tqdm
from datetime import datetime, timedelta

# 导入重构后的模块
from src.etf_portfolio.data_source import GMDataSource, RateLimiter
from src.etf_portfolio.decorators import with_rate_limit, with_retry

# GM SDK imports (保留)
from gm.api import (
    set_token, stk_get_index_constituents, history,
    stk_get_daily_valuation, stk_get_daily_basic, stk_get_daily_mktvalue,
    stk_get_fundamentals_balance, stk_get_fundamentals_income,
    stk_get_fundamentals_cashflow, stk_get_adj_factor,
    get_instruments, get_trading_dates, stk_get_symbol_industry
)

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Token (保持硬编码)
TOKEN = "478dc4635c5198dbfcc962ac3bb209e5327edbff"


def _clean_df_tz(df):
    """移除 DataFrame 中的时区信息，以便保存"""
    if df is None:
        return pd.DataFrame()
    if isinstance(df, list) or isinstance(df, tuple):
        df = pd.DataFrame(df)
    if hasattr(df, 'empty') and df.empty:
        return df
    # 查找所有带时区的 datetime 列
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            if getattr(df[col].dt, 'tz', None) is not None:
                df[col] = df[col].dt.tz_localize(None)
    return df


def make_fetcher(api_func, limiter, max_attempts=3):
    """创建带流控和重试的 API 获取函数"""
    @with_rate_limit(limiter)
    @with_retry(max_attempts=max_attempts, backoff_base=2.0)
    def fetcher(*args, **kwargs):
        df = api_func(*args, **kwargs)
        return _clean_df_tz(df)
    return fetcher


def get_downloaded_symbols(category_dir: str, file_format='csv') -> set:
    """
    检查指定目录下已经下载成功的标的，返回 symbol 集合
    """
    if not os.path.isdir(category_dir):
        return set()
    csv_files = glob.glob(os.path.join(category_dir, f"*.{file_format}"))
    # 从文件名提取 symbol (剔除后缀)
    symbols = {os.path.basename(f).replace(f'.{file_format}', '') for f in csv_files}
    return symbols


def get_time_chunks(start_date, end_date):
    """
    将时间区间切分为月度分片，应对 GMT 33000 条限制
    """
    start = datetime.strptime(start_date.split(' ')[0], '%Y-%m-%d')
    end = datetime.strptime(end_date.split(' ')[0], '%Y-%m-%d')

    chunks = []
    curr_start = start
    while curr_start <= end:
        # 计算当前月最后一天
        if curr_start.month == 12:
            next_month = curr_start.replace(year=curr_start.year + 1, month=1, day=1)
        else:
            next_month = curr_start.replace(month=curr_start.month + 1, day=1)

        curr_end = next_month - timedelta(seconds=1)
        if curr_end > end:
            curr_end = end

        chunks.append((curr_start.strftime('%Y-%m-%d %H:%M:%S'), curr_end.strftime('%Y-%m-%d %H:%M:%S')))
        curr_start = next_month

    return chunks


def get_last_timestamp(file_path, file_format='parquet'):
    """
    获取已有文件中最后一行的 bob (timestamp)
    """
    try:
        if file_format == 'parquet':
            # 只读取最后一列/最后一行以提高性能
            df = pd.read_parquet(file_path, columns=['bob'])
            if not df.empty:
                return df['bob'].max()
        elif file_format == 'csv':
            # CSV 只能读取最后几行
            df = pd.read_csv(file_path, usecols=['bob'])
            if not df.empty:
                return pd.to_datetime(df['bob']).max()
    except Exception:
        pass
    return None


def download_category_data(base_pool, category_name, fetch_func, limiter, start_date, end_date,
                           fields=None, frequency='1d', file_format='csv'):
    """
    通用分类数据下载逻辑 (支持对超过20个字段的基本面数据进行分段抓取和合并)
    """
    category_dir = os.path.join("data", "exports", category_name)
    os.makedirs(category_dir, exist_ok=True)

    downloaded = get_downloaded_symbols(category_dir, file_format=file_format)
    # 对于 history 数据，我们采用增量模式，不直接跳过已存在的 symbol，除非它已经更新到最新
    is_history = fetch_func.__name__ == 'history'
    if is_history:
        to_download = base_pool  # 增量模式检查文件内部
    else:
        to_download = [s for s in base_pool if s not in downloaded]

    if not to_download:
        logging.info(f"All symbols in {category_name} already downloaded.")
        return

    logging.info(f"Downloading {category_name} for {len(to_download)} symbols...")

    # 字段分片逻辑 (每片最多15个字段，留余量给系统字段)
    field_list = fields.split(",") if fields else []
    is_fundamental = category_name.startswith("fundamentals_")

    if is_fundamental and len(field_list) > 15:
        field_chunks = [field_list[i:i + 15] for i in range(0, len(field_list), 15)]
    else:
        field_chunks = [field_list] if field_list else [None]

    for symbol in tqdm(to_download, desc=f"Downloading {category_name}"):
        try:
            save_path = os.path.join(category_dir, f"{symbol}.{file_format}")

            # 1. 增量断点检查
            last_dt = None
            if os.path.exists(save_path):
                last_dt = get_last_timestamp(save_path, file_format=file_format)
                if last_dt:
                    # 如果已有数据最新时间已超过请求的结束时间，跳过
                    req_end_dt = pd.to_datetime(end_date)
                    if last_dt >= req_end_dt:
                        continue

            # 2. 确定时间分片
            if is_history:
                # 只有 history 需要处理 33000 条限制，按月切片
                # 调整起始时间为断点之后
                actual_start = start_date
                if last_dt:
                    # 断点后推 1 秒/分钟/天（取决于频度，这里简单处理为后推 1 秒）
                    actual_start = (last_dt + timedelta(seconds=1)).strftime('%Y-%m-%d %H:%M:%S')

                time_chunks = get_time_chunks(actual_start, end_date)
            else:
                time_chunks = [(start_date, end_date)]

            combined_df = None
            # 如果是增量模式，且文件存在，先加载旧数据以便合并（或者后面用 append）
            # 对于 Parquet，我们先读出来再写回去，或者使用 fastparquet 的 append 功能
            if os.path.exists(save_path):
                if file_format == 'parquet':
                    combined_df = pd.read_parquet(save_path)
                else:
                    combined_df = pd.read_csv(save_path)

            for t_start, t_end in time_chunks:
                limiter.wait()
                chunk_combined_df = None

                for f_chunk in field_chunks:
                    kwargs = {'symbol': symbol, 'df': True}
                    if is_history:
                        kwargs.update({'start_time': t_start, 'end_time': t_end, 'frequency': frequency})
                    else:
                        kwargs.update({'start_date': t_start, 'end_date': t_end})

                    if f_chunk:
                        kwargs['fields'] = ",".join(f_chunk)

                    if fetch_func.__name__ == 'stk_get_adj_factor':
                        kwargs.pop('df', None)

                    # 使用 make_fetcher 创建的带装饰器的函数
                    fetcher = make_fetcher(fetch_func, limiter)
                    df = fetcher(**kwargs)

                    if df is not None and not df.empty:
                        if chunk_combined_df is None:
                            chunk_combined_df = df
                        elif is_fundamental:
                            merge_keys = ['symbol', 'pub_date', 'rpt_date']
                            new_cols = [c for c in df.columns if c not in chunk_combined_df.columns or c in merge_keys]
                            chunk_combined_df = pd.merge(chunk_combined_df, df[new_cols], on=merge_keys, how='outer')

                if chunk_combined_df is not None and not chunk_combined_df.empty:
                    if combined_df is None:
                        combined_df = chunk_combined_df
                    else:
                        combined_df = pd.concat([combined_df, chunk_combined_df]).drop_duplicates(
                            subset=['symbol', 'bob'] if is_history else None)

            if combined_df is not None and not combined_df.empty:
                if file_format == 'parquet':
                    combined_df.to_parquet(save_path, index=False)
                else:
                    combined_df.to_csv(save_path, index=False)

        except Exception as e:
            logging.error(f"Failed to download {category_name} for {symbol}: {e}")


def download_static_data(stock_pool, limiter, static_dir):
    """下载静态数据 (行业分类, 上市信息)"""
    os.makedirs(static_dir, exist_ok=True)

    def chunked_string(lst, n):
        return [",".join(lst[i:i + n]) for i in range(0, len(lst), n)]

    # 行业分类
    industry_dfs = []
    for chunk in chunked_string(stock_pool, 100):
        try:
            limiter.wait()
            # api 返回包含 symbol, industry1 等字段
            res = stk_get_symbol_industry(symbols=chunk)
            if res is not None:
                if isinstance(res, list):
                    res = pd.DataFrame(res)
                if not res.empty:
                    industry_dfs.append(res)
        except Exception as e:
            logging.error(f"Failed to fetch industry for chunk: {e}")

    if industry_dfs:
        pd.concat(industry_dfs).drop_duplicates('symbol').to_csv(
            os.path.join(static_dir, "industry.csv"), index=False)

    # 股票列表 (上市/退市日期等)
    inst_dfs = []
    for chunk in chunked_string(stock_pool, 100):
        try:
            limiter.wait()
            res = get_instruments(symbols=chunk, df=True)
            if res is not None and not res.empty:
                cols = [c for c in ['symbol', 'list_date', 'delist_date'] if c in res.columns]
                inst_dfs.append(res[cols])
        except Exception as e:
            logging.error(f"Failed to fetch instruments for chunk: {e}")

    if inst_dfs:
        pd.concat(inst_dfs).drop_duplicates('symbol').to_csv(
            os.path.join(static_dir, "instruments.csv"), index=False)


class CSI1000Workflow:
    """中证1000全量数据下载流程 - 使用重构后的架构"""

    def __init__(self, token, index_code='SHSE.000852', history_1m=False, output_dir='data/exports'):
        self.token = token
        self.index_code = index_code
        self.history_1m = history_1m
        self.output_dir = output_dir
        set_token(token)
        self.limiter = RateLimiter(max_req=950)
        self.source = GMDataSource(limiter=self.limiter, token=token)
        self._constituents = None

    def get_target_pool(self):
        """获取中证1000成分股"""
        if self._constituents is None:
            logging.info(f"Fetching {self.index_code} constituents...")
            self._constituents = stk_get_index_constituents(index=self.index_code)
        if self._constituents is None or self._constituents.empty:
            return []
        symbols = self._constituents['symbol'].tolist()
        # 加入指数自身，用于下载基准行情
        return symbols + [self.index_code]

    def get_categories(self):
        cats = ["history_1d", "valuation", "mktvalue", "basic",
                "fundamentals_balance", "fundamentals_income", "fundamentals_cashflow",
                "adj_factor"]
        if self.history_1m:
            cats.insert(1, "history_1m")
        return cats

    def get_fetcher(self, category):
        """获取对应类别的数据抓取函数"""
        fetchers = {
            "history_1d": history,
            "history_1m": history,
            "valuation": stk_get_daily_valuation,
            "mktvalue": stk_get_daily_mktvalue,
            "basic": stk_get_daily_basic,
            "fundamentals_balance": stk_get_fundamentals_balance,
            "fundamentals_income": stk_get_fundamentals_income,
            "fundamentals_cashflow": stk_get_fundamentals_cashflow,
            "adj_factor": stk_get_adj_factor,
        }
        return fetchers.get(category)

    def run(self, start_date, end_date, full_history=False):
        """执行下载流程"""
        pool = self.get_target_pool()
        if not pool:
            logging.error("No symbols to download")
            return

        # 如果是全量模式，重写起始日期
        h_start_date = "2017-01-01" if full_history else start_date
        h_start = f"{h_start_date} 09:00:00"
        h_end = f"{end_date} 16:00:00"

        # 分离股票池 (排除指数本身)
        stock_pool = pool[:-1]  # 排除最后的 index_code

        # 1. 下载日线历史
        logging.info("Downloading 1d history (Format: Parquet)...")
        download_category_data(pool, "history_1d", history, self.limiter, h_start, h_end,
                               file_format='parquet')

        # 2. 下载分钟线 (如果启用)
        if self.history_1m:
            m1_start_date = "2017-01-01" if full_history else (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")
            logging.info(f"Downloading 1m history (Format: Parquet, Start: {m1_start_date})...")
            m1_start = f"{m1_start_date} 09:00:00"
            m1_end = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            download_category_data(pool, "history_1m", history, self.limiter, m1_start, m1_end,
                                   frequency='1m', file_format='parquet')

        # 3. 下载估值数据
        valuation_fields = "pe_ttm,pb_mrq,ps_ttm,pcf_ttm_oper"
        download_category_data(stock_pool, "valuation", stk_get_daily_valuation, self.limiter,
                               start_date, end_date, fields=valuation_fields)

        # 4. 下载市值数据
        mktvalue_fields = "tot_mv,a_mv"
        download_category_data(stock_pool, "mktvalue", stk_get_daily_mktvalue, self.limiter,
                               start_date, end_date, fields=mktvalue_fields)

        # 5. 下载基础指标
        basic_fields = "tclose,turnrate,ttl_shr,circ_shr,is_st,is_suspended,upper_limit,lower_limit"
        download_category_data(stock_pool, "basic", stk_get_daily_basic, self.limiter,
                               start_date, end_date, fields=basic_fields)

        # 6. 下载财务报表
        logging.info("Downloading Full Fundamental reports (Chunked)...")

        balance_fields = (
            "cash_bal_cb,dpst_ob,mny_cptl,cust_cred_dpst,cust_dpst,pm,bal_clr,cust_rsv,ln_to_ob,"
            "fair_val_fin_ast,ppay,fin_out,trd_fin_ast,deriv_fin_ast,note_acct_rcv,note_rcv,acct_rcv,"
            "acct_rcv_fin,int_rcv,dvd_rcv,oth_rcv,in_prem_rcv,rin_acct_rcv,rin_rsv_rcv,rcv_un_prem_rin_rsv,"
            "rcv_clm_rin_rsv,rcv_li_rin_rsv,rcv_lt_hi_rin_rsv,ph_plge_ln,ttl_oth_rcv,rfd_dpst,term_dpst,"
            "pur_resell_fin,aval_sale_fin,htm_inv,hold_for_sale,acct_rcv_inv,invt,contr_ast,ncur_ast_one_y,"
            "oth_cur_ast,cur_ast_oth_item,ttl_cur_ast,loan_adv,cred_inv,oth_cred_inv,lt_rcv,lt_eqy_inv,"
            "oth_eqy_inv,rfd_cap_guar_dpst,oth_ncur_fin_ast,amor_cos_fin_ast_ncur,fair_val_oth_inc_ncur,"
            "inv_prop,fix_ast,const_prog,const_matl,fix_ast_dlpl,cptl_bio_ast,oil_gas_ast,rig_ast,"
            "intg_ast,trd_seat_fee,dev_exp,gw,lt_ppay_exp,dfr_tax_ast,oth_ncur_ast,ncur_ast_oth_item,"
            "ttl_ncur_ast,oth_ast,ast_oth_item,ind_acct_ast,ttl_ast,brw_cb,dpst_ob_fin_inst,ln_fm_ob,"
            "fair_val_fin_liab,sht_ln,adv_acct,contr_liab,trd_fin_liab,deriv_fin_liab,sell_repo_ast,"
            "cust_bnk_dpst,dpst_cb_note_pay,dpst_cb,acct_rcv_adv,in_prem_rcv_adv,fee_pay,note_acct_pay,"
            "stlf_pay,note_pay,acct_pay,rin_acct_pay,emp_comp_pay,tax_pay,int_pay,dvd_pay,ph_dvd_pay,"
            "indem_pay,oth_pay,ttl_oth_pay,ph_dpst_inv,in_contr_rsv,un_prem_rsv,clm_rin_rsv,li_liab_rsv,"
            "lt_hi_liab_rsv,cust_bnk_dpst_fin,inter_pay,agy_secu_trd,agy_secu_uw,sht_bnd_pay,est_cur_liab,"
            "liab_hold_for_sale,ncur_liab_one_y,oth_cur_liab,cur_liab_oth_item,ttl_cur_liab,lt_ln,lt_pay,"
            "leas_liab,dfr_inc,dfr_tax_liab,bnd_pay,bnd_pay_pbd,bnd_pay_pfd,oth_ncur_liab,spcl_pay,"
            "ncur_liab_oth_item,lt_emp_comp_pay,est_liab,oth_liab,liab_oth_item,ttl_ncur_liab,ind_acct_liab,"
            "ttl_liab,paid_in_cptl,oth_eqy,oth_eqy_pfd,oth_eqy_pbd,oth_eqy_oth,cptl_rsv,treas_shr,"
            "oth_comp_inc,spcl_rsv,sur_rsv,rsv_ord_rsk,trd_risk_rsv,ret_prof,sugg_dvd,eqy_pcom_oth_item,"
            "ttl_eqy_pcom,min_sheqy,sheqy_oth_item,ttl_eqy,ttl_liab_eqy"
        )

        income_fields = (
            "ttl_inc_oper,inc_oper,net_inc_int,exp_int,net_inc_fee_comm,inc_rin_prem,net_inc_secu_agy,"
            "inc_fee_comm,in_prem_earn,inc_in_biz,rin_prem_cede,unear_prem_rsv,net_inc_uw,net_inc_cust_ast_mgmt,"
            "inc_fx,inc_other_oper,inc_oper_balance,ttl_inc_oper_other,ttl_cost_oper,cost_oper,exp_oper,"
            "biz_tax_sur,exp_sell,exp_adm,exp_rd,exp_fin,int_fee,inc_int,exp_oper_adm,exp_rin,rfd_prem,"
            "comp_pay,rin_clm_pay,draw_insur_liab,amor_insur_liab,exp_ph_dvd,exp_fee_comm,other_oper_cost,"
            "oper_exp_balance,exp_oper_other,ttl_cost_oper_other,inc_inv,inv_inv_jv_p,inc_ast_dspl,"
            "ast_impr_loss,cred_impr_loss,inc_fv_chg,inc_other,oper_prof_balance,oper_prof,inc_noper,"
            "exp_noper,ttl_prof_balance,oper_prof_other,ttl_prof,inc_tax,net_prof,oper_net_prof,"
            "net_prof_pcom,min_int_inc,end_net_prof,net_prof_other,eps_base,eps_dil,other_comp_inc,"
            "other_comp_inc_pcom,other_comp_inc_min,ttl_comp_inc,ttl_comp_inc_pcom,ttl_comp_inc_min,"
            "prof_pre_merge,net_rsv_in_contr,net_pay_comp,net_loss_ncur_ast,amod_fin_asst_end,"
            "cash_flow_hedging_pl,cur_trans_diff,gain_ncur_ast,afs_fv_chg_pl,oth_eqy_inv_fv_chg,"
            "oth_debt_inv_fv_chg,oth_debt_inv_cred_impr"
        )

        cashflow_fields = (
            "cash_rcv_sale,net_incr_cust_dpst_ob,net_incr_cust_dpst,net_incr_dpst_ob,net_incr_brw_cb,"
            "net_incr_ln_fm_oth,cash_rcv_orig_in,net_cash_rcv_rin_biz,net_incr_ph_dpst_inv,net_decrdpst_cb_ob,"
            "net_decr_cb,net_decr_ob_fin_inst,net_cert_dpst,net_decr_trd_fin,net_incr_trd_liab,cash_rcv_int_fee,"
            "cash_rcv_int,cash_rcv_fee,net_incr_lnfm_sell_repo,net_incr_ln_fm,net_incr_sell_repo,"
            "net_decr_lnto_pur_resell,net_decr_ln_cptl,net_dect_pur_resell,net_incr_repo,net_decr_repo,"
            "tax_rbt_rcv,net_cash_rcv_trd,cash_rcv_oth_oper,net_cash_agy_secu_trd,cash_rcv_pur_resell,"
            "net_cash_agy_secu_uw,cash_rcv_dspl_debt,canc_loan_rcv,cf_in_oper,cash_pur_gds_svc,net_incr_ln_adv_cust,"
            "net_decr_brw_cb,net_incr_dpst_cb_ob,net_incr_cb,net_incr_ob_fin_inst,net_decr_dpst_ob,"
            "net_decr_issu_cert_dpst,net_incr_lnto_pur_resell,net_incr_ln_to,net_incr_pur_resell,"
            "net_decr_lnfm_sell_repo,net_decr_ln_fm,net_decr_sell_repo,net_incr_trd_fin,net_decr_trd_liab,"
            "cash_pay_indem_orig,net_cash_pay_rin_biz,cash_pay_int_fee,cash_pay_int,cash_pay_fee,ph_dvd_pay,"
            "net_decr_ph_dpst_inv,cash_pay_emp,cash_pay_tax,net_cash_pay_trd,cash_pay_oth_oper,"
            "net_incr_dspl_trd_fin,cash_pay_fin_leas,net_decr_agy_secu_pay,net_decr_dspl_trd_fin,cf_out_oper,"
            "net_cf_oper,cash_rcv_sale_inv,inv_inc_rcv,cash_rcv_dvd_prof,cash_rcv_dspl_ast,cash_rcv_dspl_sub_oth,"
            "cash_rcv_oth_inv,cf_in_inv,pur_fix_intg_ast,cash_out_dspl_sub_oth,cash_pay_inv,net_incr_ph_plge_ln,"
            "add_cash_pled_dpst,net_incr_plge_ln,net_cash_get_sub,net_pay_pur_resell,cash_pay_oth_inv,"
            "cf_out_inv,net_cf_inv,cash_rcv_cptl,sub_rcv_ms_inv,brw_rcv,cash_rcv_bnd_iss,net_cash_rcv_sell_repo,"
            "cash_rcv_oth_fin,issu_cert_dpst,cf_in_fin_oth,cf_in_fin,cash_rpay_brw,cash_pay_bnd_int,"
            "cash_pay_dvd_int,sub_pay_dvd_prof,cash_pay_oth_fin,net_cash_pay_sell_repo,cf_out_fin,net_cf_fin,"
            "efct_er_chg_cash,net_incr_cash_eq,cash_cash_eq_bgn,cash_cash_eq_end,net_prof,ast_impr,"
            "accr_prvs_ln_impa,accr_prvs_oth_impa,accr_prem_rsv,accr_unearn_prem_rsv,defr_fix_prop,"
            "depr_oga_cba,amor_intg_ast_lt_exp,amort_intg_ast,amort_lt_exp_ppay,dspl_ast_loss,"
            "fair_val_chg_loss,fv_chg_loss,dfa,fin_exp,inv_loss,exchg_loss,dest_incr,loan_decr,"
            "cash_pay_bnd_int_iss,dfr_tax,dfr_tax_ast_decr,dfr_tax_liab_incr,invt_decr,decr_rcv_oper,"
            "incr_pay_oper,oth,cash_end,cash_bgn,cash_eq_end,cash_eq_bgn,cred_impr_loss,est_liab_add,"
            "dr_cnv_cptl,cptl_bnd_expr_one_y,fin_ls_fix_ast,amort_dfr_inc,depr_inv_prop,trd_fin_decr,"
            "im_net_cf_oper,im_net_incr_cash_eq"
        )

        fundamental_tasks = [
            ("balance", stk_get_fundamentals_balance, balance_fields),
            ("income", stk_get_fundamentals_income, income_fields),
            ("cashflow", stk_get_fundamentals_cashflow, cashflow_fields)
        ]

        for name, func, f_fields in fundamental_tasks:
            download_category_data(stock_pool, f"fundamentals_{name}", func, self.limiter,
                                   start_date, end_date, fields=f_fields)

        # 7. 下载复权因子
        logging.info("Downloading Adj Factor...")
        download_category_data(stock_pool, "adj_factor", stk_get_adj_factor, self.limiter,
                               start_date, end_date)

        # 8. 下载静态数据
        logging.info("Downloading Static Data (Industry, Instruments)...")
        static_dir = os.path.join(self.output_dir, "static")
        download_static_data(stock_pool, self.limiter, static_dir)

        # 9. 下载交易日历
        logging.info("Downloading Trading Dates...")
        calendar_dir = os.path.join(self.output_dir, "calendar")
        os.makedirs(calendar_dir, exist_ok=True)
        try:
            self.limiter.wait()
            dates = get_trading_dates(exchange='SHSE', start_date=start_date, end_date=end_date)
            if dates:
                pd.DataFrame({'trade_date': dates}).to_csv(
                    os.path.join(calendar_dir, "trade_dates.csv"), index=False)
        except Exception as e:
            logging.error(f"Failed to fetch trading dates: {e}")

        logging.info("Download workflow completed.")


def run_download_workflow(token, start_date, end_date, index_code='SHSE.000852',
                          history_1m=False, full_history=False):
    """执行完整的数据下载工作流 - 使用 CSI1000Workflow"""
    workflow = CSI1000Workflow(token, index_code=index_code, history_1m=history_1m)
    workflow.run(start_date, end_date, full_history=full_history)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Download CSI 1000 Data from GM")
    parser.add_argument("--token", type=str, help="GM SDK Token (optional, uses hardcoded token)")
    parser.add_argument("--index", type=str, default="SHSE.000852",
                        help="Index code (e.g., SHSE.000852 for CSI 1000)")
    parser.add_argument("--start", type=str,
                        default=(datetime.now() - timedelta(days=365)).strftime("%Y-%m-%d"),
                        help="Start date (YYYY-MM-DD)")
    parser.add_argument("--end", type=str, default=datetime.now().strftime("%Y-%m-%d"),
                        help="End date (YYYY-MM-DD)")
    parser.add_argument("--history-1m", action="store_true", help="Download 1m history")
    parser.add_argument("--full-history", action="store_true",
                        help="Download history from 2017-01-01 (10 years)")

    args = parser.parse_args()

    # 使用硬编码 TOKEN (如果命令行未提供)
    token = args.token or TOKEN

    if not token:
        print("Error: No token provided.")
    else:
        run_download_workflow(token, args.start, args.end, args.index,
                              history_1m=args.history_1m, full_history=args.full_history)