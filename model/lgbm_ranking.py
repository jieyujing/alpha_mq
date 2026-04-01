# model/lgbm_ranking.py
import numpy as np
import pandas as pd
import lightgbm as lgb
from typing import List, Tuple, Union, Text
from qlib.contrib.model.gbdt import LGBModel
from qlib.data.dataset import DatasetH
from qlib.data.dataset.handler import DataHandlerLP
from qlib.data.dataset.weight import Reweighter
from qlib.workflow import R

class LGBRankingModel(LGBModel):
    """
    Custom LightGBM Ranking Model that correctly handles group information for ranking tasks.
    In Qlib, groups are defined by the 'datetime' in the index.
    """

    def __init__(self, loss="lambdarank", early_stopping_rounds=50, num_boost_round=1000, **kwargs):
        # Override __init__ to allow 'lambdarank' which is blocked in LGBModel
        # But we still initialize the underlying parameters.
        self.params = {"objective": loss, "verbosity": -1}
        self.params.update(kwargs)
        self.early_stopping_rounds = early_stopping_rounds
        self.num_boost_round = num_boost_round
        self.model = None

    def _prepare_data(self, dataset: DatasetH, reweighter=None) -> List[Tuple[lgb.Dataset, str]]:
        """
        Prepare data with group information for ranking tasks.
        """
        ds_l = []
        assert "train" in dataset.segments
        for key in ["train", "valid"]:
            if key in dataset.segments:
                df = dataset.prepare(key, col_set=["feature", "label"], data_key=DataHandlerLP.DK_L)
                if df.empty:
                    raise ValueError(f"Empty data from dataset for segment {key}, please check your dataset config.")
                
                # Ensure the data is sorted by datetime to make group calculation correct
                df = df.sort_index(level="datetime")
                
                x, y_df = df["feature"], df["label"]

                # Handle label for ranking
                if y_df.values.ndim == 2 and y_df.values.shape[1] == 1:
                    y = np.squeeze(y_df.values)
                else:
                    raise ValueError("LightGBM doesn't support multi-label training")

                # If objective is lambdarank, labels must be integers.
                # Continuous labels (returns) should be transformed into relevance scores.
                if self.params.get("objective", "") == "lambdarank":
                    # Map continuous labels into 5 discrete levels (0-4 quintiles) within each group (date)
                    # This is common practice for ranking models in finance.
                    # Use rank if data is too small or has duplicates
                    def discretize_label(group):
                        if group.isnull().all():
                            return group
                        try:
                            # Quintiles (0-4)
                            return pd.qcut(group, 5, labels=False, duplicates='drop')
                        except ValueError:
                            # Fallback if too few samples, use simple rank
                            return (group.rank(pct=True) * 4).astype(int)
                    
                    y = df.groupby("datetime")["label"].transform(discretize_label).values
                    # Ensure y is integer type
                    y = y.astype(int)
                
                # Calculate group size per date (assuming 'datetime' is in the index)
                # This depends on the index being (datetime, instrument)
                group = df.index.get_level_values("datetime").value_counts().sort_index().values
                
                if reweighter is None:
                    w = None
                elif isinstance(reweighter, Reweighter):
                    w = reweighter.reweight(df)
                else:
                    raise ValueError("Unsupported reweighter type.")
                
                # Create lgb.Dataset with group information
                ds_l.append((lgb.Dataset(x.values, label=y, weight=w, group=group), key))
        return ds_l
