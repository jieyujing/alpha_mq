import logging
import pandas as pd
from datetime import datetime
from pathlib import Path
from typing import Dict, List
from tqdm import tqdm

from data_download.base import GMDownloader
from data_download.incremental import check_time_coverage, check_symbol_coverage
from data_download.gm_api import RateLimiter

class FundamentalsDownloader(GMDownloader):
    """
    财务报表数据下载器
    
    支持三大财务报表 (资产负债表、利润表、现金流量表) 的增量下载。
    """

    CATEGORIES = {
        "fundamentals_income": {
            "func_name": "stk_get_fundamentals_income",
            "format": "csv",
            "time_col": "pub_date",
            "fields": [
                "net_inc_fee_comm", "net_inc_secu_agy", "net_inc_int", "inc_rin_prem", "rin_prem_cede",
                "unear_prem_rsv", "in_prem_earn", "exp_sell", "inc_other_oper", "exp_rin",
                "net_inc_cust_ast_mgmt", "inc_fee_comm", "exp_oper_adm", "exp_int", "inc_fee_comm_other",
                "ttl_inc_oper", "net_inc_uw", "inc_oper", "inc_in_biz", "exp_oper",
                "exp_fee_comm", "other_oper_cost", "exp_fin", "exp_adm", "cost_oper",
                "biz_tax_sur", "ttl_cost_oper", "exp_rd", "inc_oper_balance", "ttl_inc_oper_other",
                "inc_int", "int_fee", "draw_insur_liab", "ast_impr_loss", "amor_insur_liab",
                "rin_clm_pay", "oper_exp_balance", "inv_inv_jv_p", "ttl_cost_oper_other", "rfd_prem",
                "inc_fv_chg", "inc_ast_dspl", "ttl_prof", "inc_inv", "exp_ph_dvd",
                "exp_noper", "comp_pay", "oper_prof", "min_int_inc", "net_prof",
                "exp_oper_other", "oper_net_prof", "inc_other", "cred_impr_loss", "inc_noper",
                "ttl_prof_balance", "oper_prof_other", "net_prof_pcom", "oper_prof_balance", "inc_tax",
                "other_comp_inc", "eps_base", "eps_dil", "prof_pre_merge", "end_net_prof",
                "other_comp_inc_min", "net_pay_comp", "net_prof_other", "afs_fv_chg_pl", "ttl_comp_inc_pcom",
                "other_comp_inc_pcom", "net_loss_ncur_ast", "cur_trans_diff", "amod_fin_asst_end",
                "oth_debt_inv_cred_impr", "net_rsv_in_contr", "ttl_comp_inc_min", "cash_flow_hedging_pl",
                "oth_debt_inv_fv_chg", "ttl_comp_inc", "gain_ncur_ast", "oth_eqy_inv_fv_chg",
            ],
        },
        "fundamentals_balance": {
            "func_name": "stk_get_fundamentals_balance",
            "format": "csv",
            "time_col": "pub_date",
            "fields": [
                "ppay", "mny_cptl", "int_rcv", "oth_rcv", "acct_rcv",
                "oth_cur_ast", "loan_adv", "dev_exp", "acct_pay", "int_pay",
                "oth_pay", "oth_cur_liab", "bnd_pay", "est_liab", "oth_ncur_liab",
                "oth_liab", "oth_eqy", "ttl_eqy",
            ],
        },
        "fundamentals_cashflow": {
            "func_name": "stk_get_fundamentals_cashflow",
            "format": "csv",
            "time_col": "pub_date",
            "fields": [
                "cash_rcv_orig_in", "net_decrdpst_cb_ob", "cash_rcv_int", "cash_rcv_oth_oper",
                "cash_pay_int", "net_prof",
            ],
        },
    }

    MAX_FIELDS = 20 # GM API limit

    def __init__(self, config: Dict):
        super().__init__(config)
        self.index_code = config.get("index_code", "SHSE.000852")
        self.start_date = config.get("start_date", "2020-01-01")
        self.end_date = config.get("end_date") or datetime.now().strftime("%Y-%m-%d")
        self.token = config.get("token")

        if self.token:
            from gm.api import set_token
            set_token(self.token)

        self.limiter = RateLimiter(max_req=100) # Fundamentals API might have stricter limits or be slower
        self._constituents = None

    def get_target_pool(self) -> List[str]:
        if self._constituents is None:
            from gm.api import stk_get_index_constituents
            logging.info(f"Fetching {self.index_code} constituents...")
            self._constituents = stk_get_index_constituents(index=self.index_code)

        if self._constituents is None or self._constituents.empty:
            logging.error("Failed to get constituents")
            return []

        return self._constituents['symbol'].tolist()

    def get_categories(self) -> Dict:
        return self.CATEGORIES

    def run(self):
        self.setup()
        for category, cat_config in self.get_categories().items():
            logging.info(f"Processing category: {category}")
            self.download_category_incremental(category, cat_config)

    def download_category_incremental(self, category: str, cat_config: Dict):
        target_pool = self.get_target_pool()
        cat_dir = self.exports_base / category
        file_format = cat_config.get("format", "csv")
        time_col = cat_config.get("time_col", "pub_date")

        symbol_gap = check_symbol_coverage(cat_dir, target_pool, file_format)
        logging.info(f"{category}: {len(symbol_gap.existing)} existing, {len(symbol_gap.missing)} missing")

        end_dt = datetime.strptime(self.end_date, "%Y-%m-%d")
        download_tasks = []

        for symbol in symbol_gap.missing:
            download_tasks.append((symbol, self.start_date, self.end_date))

        for symbol in symbol_gap.existing:
            file_path = cat_dir / f"{symbol}.{file_format}"
            coverage = check_time_coverage(file_path, end_dt, time_col)
            if not coverage.covered and coverage.gap_start:
                gap_start_str = coverage.gap_start.strftime("%Y-%m-%d")
                download_tasks.append((symbol, gap_start_str, self.end_date))

        if not download_tasks:
            logging.info(f"{category}: all data covered, skipping")
            return

        from gm import api as gm_api
        fetch_func = getattr(gm_api, cat_config["func_name"], None)
        if fetch_func is None:
            logging.error(f"GM API function not found: {cat_config['func_name']}")
            return

        logging.info(f"{category}: downloading {len(download_tasks)} tasks")
        for symbol, start, end in tqdm(download_tasks, desc=f"Downloading {category}"):
            self._download_single_fundamentals(symbol, start, end, cat_dir, cat_config, fetch_func)

    def _download_single_fundamentals(self, symbol: str, start_date: str, end_date: str,
                                     cat_dir: Path, cat_config: Dict, fetch_func):
        file_format = cat_config.get("format", "csv")
        file_path = cat_dir / f"{symbol}.{file_format}"
        all_fields = cat_config.get("fields", [])
        
        # Split fields into batches
        field_batches = [all_fields[i:i+self.MAX_FIELDS] for i in range(0, len(all_fields), self.MAX_FIELDS)]

        try:
            merged = None
            for batch in field_batches:
                self.limiter.wait()
                df = fetch_func(
                    symbol=symbol,
                    fields=",".join(batch),
                    start_date=start_date,
                    end_date=end_date,
                    df=True
                )
                if df is not None and not df.empty:
                    if merged is None:
                        merged = df
                    else:
                        key_cols = [c for c in ['symbol', 'pub_date', 'rpt_date', 'rpt_type', 'data_type'] if c in df.columns]
                        merged = merged.merge(df, on=key_cols, how="outer")

            if merged is None or merged.empty:
                return

            # Remove timezone
            for col in merged.columns:
                if pd.api.types.is_datetime64_any_dtype(merged[col]):
                    if getattr(merged[col].dt, 'tz', None) is not None:
                        merged[col] = merged[col].dt.tz_localize(None)

            # Merge with existing file
            if file_path.exists():
                old_df = pd.read_csv(file_path)
                # Ensure date columns are parsed for merge/dedup if needed, 
                # but usually strings are fine if format is consistent.
                # However, gm-api returns datetime objects in DF.
                cat_config.get("time_col", "pub_date")
                # Deduplicate by symbol and pub_date (or rpt_date?)
                # Fundamentals usually use (symbol, rpt_date, pub_date) as unique key
                subset_cols = [c for c in ["symbol", "pub_date", "rpt_date"] if c in merged.columns]
                merged = pd.concat([old_df, merged]).drop_duplicates(subset=subset_cols)

            merged.to_csv(file_path, index=False, encoding="gbk")

        except Exception as e:
            logging.warning(f"Failed to download {symbol}: {e}")
