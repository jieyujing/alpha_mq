import os

def get_gm_token() -> str:
    token = os.environ.get("GM_TOKEN")
    if not token:
        raise ValueError("Environment variable GM_TOKEN is not set")
    return token
