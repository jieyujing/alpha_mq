import os
import pandas as pd
from pathlib import Path

def generate():
    export_dir = Path("data/exports")
    
    # 1. 获取每日特征 (valuation, mktvalue, basic)
    daily_features = []
    for cat in ["valuation", "mktvalue", "basic"]:
        path = export_dir / cat
        if path.exists():
            first_file = next(path.glob("*.csv"), None)
            if first_file:
                df = pd.read_csv(first_file, nrows=0)
                cols = [f"${c}" for c in df.columns if c not in ["symbol", "trade_date", "bob", "rpt_type", "data_type"]]
                daily_features.extend(cols)

    # 2. 获取 PIT 特征 (fundamentals_*)
    pit_features = []
    for cat in ["fundamentals_balance", "fundamentals_income", "fundamentals_cashflow"]:
        path = export_dir / cat
        if path.exists():
            first_file = next(path.glob("*.csv"), None)
            if first_file:
                df = pd.read_csv(first_file, nrows=0)
                # 使用 P() 算子引用 PIT 数据
                cols = [f"P('{c}')" for c in df.columns if c not in ["symbol", "pub_date", "rpt_date", "rpt_type", "data_type"]]
                pit_features.extend(cols)

    # 3. 组装 YAML
    all_extra = daily_features + pit_features
    
    # 将列表转为 YAML 格式的字符串列表
    feature_list_str = "\n                - ".join([""] + all_extra)
    
    yaml_template = f"""
qlib_init:
    provider_uri: "data/qlib_bin"
    region: cn

data_handler_config: &data_handler_config
    class: Alpha158
    module_path: qlib.contrib.data.handler
    kwargs:
        start_time: 2020-01-01
        end_time: 2026-04-20
        instruments: csi1000
        data_loader_config:
            label: 
                - "Ref($close, -1)/$close-1"
                - "Ref($close, -5)/$close-1"
                - "Ref($close, -10)/$close-1"
                - "Ref($close, -20)/$close-1"
            label_names: ["LABEL_1D", "LABEL_5D", "LABEL_10D", "LABEL_20D"]
            feature: {feature_list_str}
        learn_processors:
            - class: DropnaLabel
            - class: CSRankNorm
              kwargs:
                  fields_group: label
        label: ["LABEL_1D"]

task:
    model:
        class: LGBModel
        module_path: qlib.contrib.model.gbdt
        kwargs:
            loss: mse
            n_estimators: 1000
            learning_rate: 0.05
    dataset:
        class: DatasetH
        module_path: qlib.data.dataset
        kwargs:
            handler:
                class: Alpha158
                module_path: qlib.contrib.data.handler
                kwargs: *data_handler_config
            segments:
                train: [2020-01-01, 2023-12-31]
                valid: [2024-01-01, 2024-12-31]
                test: [2025-01-01, 2026-04-20]
"""
    # 确保目录存在
    Path("configs").mkdir(exist_ok=True)
    
    with open("configs/alpha158_train.yaml", "w") as f:
        f.write(yaml_template)
    print(f"成功生成全量配置：configs/alpha158_train.yaml，包含 {len(all_extra)} 个额外特征。")

if __name__ == "__main__":
    generate()
