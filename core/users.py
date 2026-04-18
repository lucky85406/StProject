# core/users.py

# 使用者資料（未來可替換為資料庫查詢）
USERS: dict[str, str] = {
    "admin": "admin123",
    "user": "user123",
}

def verify_password(username: str, password: str) -> bool:
    """驗證帳號密碼是否正確"""
    return USERS.get(username) == password