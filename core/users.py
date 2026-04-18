# core/users.py

import os
from dotenv import load_dotenv

load_dotenv()

USERS: dict[str, str] = {
    os.getenv("ADMIN_USERNAME", "admin"): os.getenv("ADMIN_PASSWORD", ""),
    os.getenv("USER1_USERNAME", "user"): os.getenv("USER1_PASSWORD", ""),
}


def verify_password(username: str, password: str) -> bool:
    """驗證帳號密碼是否正確"""
    return USERS.get(username) == password
