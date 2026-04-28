"""
下载三大财务报表数据到 data/exports/

用法: uv run python scripts/download_fundamentals.py
"""
import logging
import os
import time
from pathlib import Path
import pandas as pd

from gm.api import set_token, stk_get_fundamentals_income, stk_get_fundamentals_balance, stk_get_fundamentals_cashflow

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

EXPORTS = Path("data/exports")
TOKEN = os.environ.get("GM_TOKEN")
MAX_FIELDS = 20  # GM API limit

# Valid field lists (discovered through API testing)
INCOME_FIELDS = [
    "net_inc_fee_comm", "net_inc_secu_agy", "net_inc_int", "inc_rin_prem", "rin_prem_cede",
    "unear_prem_rsv", "in_prem_earn", "exp_sell", "inc_other_oper", "exp_rin",
    "net_inc_cust_ast_mgmt", "inc_fee_comm", "exp_oper_adm", "exp_int", "inc_fx",
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
]

BALANCE_FIELDS = [
    "ppay", "mny_cptl", "int_rcv", "oth_rcv", "acct_rcv",
    "oth_cur_ast", "loan_adv", "dev_exp", "acct_pay", "int_pay",
    "oth_pay", "oth_cur_liab", "bnd_pay", "est_liab", "oth_ncur_liab",
    "oth_liab", "oth_eqy", "ttl_eqy",
]

CASHFLOW_FIELDS = [
    "cash_rcv_orig_in", "net_decrdpst_cb_ob", "cash_rcv_int", "cash_rcv_oth_oper",
    "cash_pay_int", "net_prof",
]


def get_symbols():
    """Get current CSI 1000 constituents"""
    from gm.api import stk_get_index_constituents
    cons = stk_get_index_constituents(index='SHSE.000852')
    return cons['symbol'].tolist()


def download_category(category, all_fields, symbols, start_date, end_date):
    """Download a fundamentals category for all symbols with field batching"""
    out_dir = EXPORTS / category
    out_dir.mkdir(parents=True, exist_ok=True)

    func_map = {
        "fundamentals_income": stk_get_fundamentals_income,
        "fundamentals_balance": stk_get_fundamentals_balance,
        "fundamentals_cashflow": stk_get_fundamentals_cashflow,
    }
    fetch_func = func_map[category]

    # Split fields into batches of MAX_FIELDS
    field_batches = [all_fields[i:i+MAX_FIELDS] for i in range(0, len(all_fields), MAX_FIELDS)]
    logging.info(f"{category}: {len(all_fields)} fields in {len(field_batches)} batches")

    done = 0
    skipped = 0
    errors = 0

    for sym in symbols:
        out_path = out_dir / f"{sym}.csv"
        if out_path.exists() and out_path.stat().st_size > 1000:
            skipped += 1
            continue

        try:
            # Fetch each batch and merge
            merged = None
            for batch in field_batches:
                df = fetch_func(
                    symbol=sym,
                    fields=",".join(batch),
                    start_date=start_date,
                    end_date=end_date,
                    df=True
                )
                if df is not None and not df.empty:
                    if merged is None:
                        merged = df
                    else:
                        # Merge on common keys
                        key_cols = [c for c in ['symbol', 'pub_date', 'rpt_date', 'rpt_type', 'data_type'] if c in df.columns]
                        merged = merged.merge(df, on=key_cols, how="outer")
                    time.sleep(0.05)  # Rate limit between batches

            if merged is not None and not merged.empty:
                merged.to_csv(out_path, index=False, encoding="gbk")
                done += 1
            else:
                skipped += 1
        except Exception as e:
            errors += 1
            logging.warning(f"Failed {sym}: {e}")

        time.sleep(0.1)  # Rate limit between symbols

    logging.info(f"{category}: {done} downloaded, {skipped} skipped, {errors} errors")


def main():
    if not TOKEN:
        logging.error("Set GM_TOKEN environment variable")
        return

    set_token(TOKEN)
    symbols = get_symbols()
    logging.info(f"Found {len(symbols)} constituents")

    start_date = "2020-01-01"
    end_date = "2026-04-27"

    for cat, fields in [
        ("fundamentals_income", INCOME_FIELDS),
        ("fundamentals_balance", BALANCE_FIELDS),
        ("fundamentals_cashflow", CASHFLOW_FIELDS),
    ]:
        logging.info(f"Downloading {cat} ({len(fields)} fields)...")
        download_category(cat, fields, symbols, start_date, end_date)

    logging.info("Done!")


if __name__ == "__main__":
    main()
