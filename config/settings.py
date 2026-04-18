# config/settings.py
import os
from dotenv import load_dotenv

load_dotenv()  # 讀取 .env 檔案

# Cookie 加密設定
COOKIE_PASSWORD: str = os.environ.get("COOKIE_PASSWORD", "dev-only-change-in-production-32chars!")
COOKIE_SECRET_KEY: str = os.environ.get("COOKIE_SECRET_KEY", "dev-secret-key-change-in-production!")
COOKIE_PREFIX: str = "stproject_"