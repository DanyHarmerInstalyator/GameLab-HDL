from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
from database import init_db, get_db_connection
from models import verify_password
import os
import uuid

# Инициализация базы данных при запуске
init_db()

app = FastAPI(title="GameLab HDL Backend")

# Схема безопасности
security = HTTPBearer()

# In-memory хранилище токенов
active_tokens = {}  # token -> user_id
token_to_session = {}  # token -> session_id (для обратной совместимости)

# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5501",
        "http://localhost:5501",
        "https://hdlgame.netlify.app",
        "https://gamelabhdl.netlify.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# --- Схемы данных ---
class UserLogin(BaseModel):
    name: str
    password: str

class UserResponse(BaseModel):
    id: int
    name: str
    position: str = "—"
    coins: int
    exp: int
    score: int

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    name: str

# --- Вспомогательные функции ---
def get_current_user(
    request: Request = None,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security)
):
    """
    Получает текущего пользователя через токен или куки (для обратной совместимости)
    """
    # Приоритет 1: Bearer токен
    if credentials:
        token = credentials.credentials
        if token in active_tokens:
            user_id = active_tokens[token]
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute("SELECT id, name FROM users WHERE id = ?", (user_id,))
            user = cursor.fetchone()
            conn.close()
            if user:
                return {"id": user["id"], "name": user["name"]}
    
    # Приоритет 2: Куки (старая версия)
    if request:
        session_id = request.cookies.get("session_id")
        if session_id and session_id in token_to_session:
            # Конвертируем старую сессию в токен
            token = token_to_session[session_id]
            if token in active_tokens:
                user_id = active_tokens[token]
                conn = get_db_connection()
                cursor = conn.cursor()
                cursor.execute("SELECT id, name FROM users WHERE id = ?", (user_id,))
                user = cursor.fetchone()
                conn.close()
                if user:
                    return {"id": user["id"], "name": user["name"]}
    
    raise HTTPException(status_code=401, detail="Не авторизован")

def cleanup_old_tokens():
    """Очистка старых токенов (опционально, для продакшена добавьте TTL)"""
    # Здесь можно добавить логику очистки старых токенов
    pass

# --- Эндпоинты аутентификации ---

@app.post("/api/auth/token", response_model=TokenResponse)
def get_auth_token(data: UserLogin, response: Response):
    """
    Получение Bearer токена для авторизации
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, password_hash, coins, exp, score FROM users WHERE name = ?", 
        (data.name,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверное имя или пароль")

    # Генерируем токен
    token = str(uuid.uuid4())
    user_id = row["id"]
    
    # Сохраняем токен
    active_tokens[token] = user_id
    
    # Также сохраняем для обратной совместимости с куками
    session_id = os.urandom(24).hex()
    token_to_session[session_id] = token
    
    # Устанавливаем куку (для совместимости со старым фронтендом)
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=24 * 60 * 60  # 24 часа
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "user_id": user_id,
        "name": row["name"]
    }

@app.post("/api/login", response_model=UserResponse)
def login(data: UserLogin, response: Response):
    """
    Старый эндпоинт для совместимости, также возвращает токен в заголовке
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, password_hash, coins, exp, score FROM users WHERE name = ?", 
        (data.name,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверное имя или пароль")

    user_id = row["id"]
    
    # Генерируем токен
    token = str(uuid.uuid4())
    active_tokens[token] = user_id
    
    # Устанавливаем куку
    session_id = os.urandom(24).hex()
    token_to_session[session_id] = token
    
    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,
        samesite="none",
        max_age=24 * 60 * 60
    )
    
    # Возвращаем токен в заголовке для нового фронтенда
    response.headers["X-Auth-Token"] = token

    return {
        "id": user_id,
        "name": row["name"],
        "coins": row["coins"],
        "exp": row["exp"],
        "score": row["score"]
    }

@app.post("/api/auth/logout")
def logout(
    response: Response,
    current_user = Depends(get_current_user)
):
    """
    Выход и инвалидация токена
    """
    # Находим и удаляем токен пользователя
    tokens_to_remove = []
    for token, user_id in active_tokens.items():
        if user_id == current_user["id"]:
            tokens_to_remove.append(token)
    
    for token in tokens_to_remove:
        del active_tokens[token]
    
    # Удаляем куку
    response.delete_cookie("session_id")
    
    return {"message": "Успешный выход"}

# --- Эндпоинты данных ---

@app.get("/api/users", response_model=List[UserResponse])
def get_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, coins, exp, score FROM users")
    rows = cursor.fetchall()
    conn.close()
    return [
        {
            "id": r["id"],
            "name": r["name"],
            "coins": r["coins"],
            "exp": r["exp"],
            "score": r["score"]
        }
        for r in rows
    ]

@app.post("/api/coins/add")
def add_coins(
    target_name: str, 
    amount: int, 
    current_user = Depends(get_current_user)
):
    """
    Начисление коинов (только для Натальи Сюр, ID 175)
    """
    if current_user["id"] != 175:
        raise HTTPException(status_code=403, detail="Только Наталья Сюр может начислять коины")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id, name FROM users WHERE name = ?", (target_name,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    cursor.execute("UPDATE users SET coins = coins + ? WHERE name = ?", (amount, target_name))
    cursor.execute(
        """INSERT INTO transactions 
           (user_id, admin_id, action, amount, resource, comment) 
           VALUES (?, ?, ?, ?, ?, ?)""",
        (target["id"], current_user["id"], "add", amount, "coins", 
         f"Начислено админом {current_user['name']}")
    )

    conn.commit()
    conn.close()
    return {"message": f"{amount} коинов добавлено {target_name}"}

@app.get("/api/auth/me")
def get_current_user_info(current_user = Depends(get_current_user)):
    """
    Получение информации о текущем пользователе
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, name, coins, exp, score FROM users WHERE id = ?", 
        (current_user["id"],)
    )
    row = cursor.fetchone()
    conn.close()
    
    if not row:
        raise HTTPException(status_code=404, detail="Пользователь не найден")
    
    return {
        "id": row["id"],
        "name": row["name"],
        "coins": row["coins"],
        "exp": row["exp"],
        "score": row["score"]
    }

# --- История ---
@app.get("/api/history/{user_id}")
def get_history(user_id: int, current_user = Depends(get_current_user)):
    """
    Получение истории операций (только для своего аккаунта или для админа)
    """
    if current_user["id"] != user_id and current_user["id"] != 175:
        raise HTTPException(status_code=403, detail="Нет доступа к истории другого пользователя")

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.amount, t.resource, t.timestamp, u.name as admin_name, t.comment
        FROM transactions t
        LEFT JOIN users u ON t.admin_id = u.id
        WHERE t.user_id = ?
        ORDER BY t.timestamp DESC
        LIMIT 50
    ''', (user_id,))
    rows = cursor.fetchall()
    conn.close()

    return [
        {
            "date": row["timestamp"],
            "resource": row["resource"],
            "amount": row["amount"],
            "admin": row["admin_name"] or "Система",
            "comment": row["comment"] or "Без комментария"
        }
        for row in rows
    ]

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)