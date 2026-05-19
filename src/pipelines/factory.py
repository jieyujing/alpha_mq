import logging
from typing import Dict, Any
from src.etf_portfolio.data_source import GMDataSource, RateLimiter
from src.etf_portfolio.rqalpha_data import RQAlphaDataSource

def create_data_source(config: Dict[str, Any]):
    """
    根据配置创建数据源实例。
    支持 'gm' (掘金) 和 'rqalpha' (RQAlpha Bundle)。
    """
    data_cfg = config.get("data", {})
    source_type = data_cfg.get("source_type", "gm").lower()
    
    if source_type == "rqalpha":
        bundle_path = data_cfg.get("rqalpha_bundle_path", "/Users/link/.rqalpha/bundle")
        logging.info(f"Creating RQAlphaDataSource with bundle: {bundle_path}")
        return RQAlphaDataSource(bundle_path=bundle_path)
    else:
        token = data_cfg.get("token") or config.get("token")
        if not token:
            import os
            token = os.environ.get("GM_TOKEN")
        
        # 默认回退到 GM (如果 token 存在)
        logging.info(f"Creating GMDataSource (source_type={source_type})")
        limiter = RateLimiter(max_req=950)
        return GMDataSource(limiter=limiter, token=token or "")
