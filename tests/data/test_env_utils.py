import pytest
import os
from data.utils.env_utils import get_gm_token

def test_get_gm_token(monkeypatch):
    monkeypatch.setenv("GM_TOKEN", "dummy_token")
    assert get_gm_token() == "dummy_token"
