# core/db.py
from __future__ import annotations
import logging
from functools import lru_cache
import streamlit as st
from supabase import create_client, Client

logger = logging.getLogger("core.db")


@lru_cache(maxsize=1)
def get_client() -> Client:
    """
    建立並快取 Supabase 連線，整個 App 生命週期只初始化一次。
    使用 service_role key 以繞過 RLS，適合後端伺服器端存取。
    """
    url: str = st.secrets["supabase"]["url"]
    key: str = st.secrets["supabase"]["service_key"]
    client = create_client(url, key)
    logger.info("Supabase 連線初始化完成")
    return client
