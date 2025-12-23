# backend/main.py
from fastapi import FastAPI, HTTPException, Request, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from database import init_db, get_db_connection
from models import verify_password
import os

# Инициализация базы данных при запуске
init_db()

app = FastAPI(title="GameLab HDL Backend")

# Простое in-memory хранилище сессий (для демо / 1 инстанс)
active_sessions = {}

# Настройка CORS/
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

# --- Вспомогательные функции ---
def get_current_user(request: Request):
    session_id = request.cookies.get("session_id")
    print(f"DEBUG get_current_user: session_id = {session_id}")  # Отладка
    
    if not session_id:
        print("DEBUG: No session_id in cookies")  # Отладка
        raise HTTPException(status_code=401, detail="Не авторизован: нет сессии")
    
    if session_id not in active_sessions:
        print(f"DEBUG: Session {session_id} not found in active_sessions")  # Отладка
        raise HTTPException(status_code=401, detail="Сессия истекла")
    
    user_id = active_sessions[session_id]
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM users WHERE id = ?", (user_id,))
    user = cursor.fetchone()
    conn.close()
    
    if not user:
        print(f"DEBUG: User {user_id} not found in database")  # Отладка
        raise HTTPException(status_code=401, detail="Пользователь удалён")
    
    print(f"DEBUG: Current user found: {user}")  # Отладка
    return {"id": user["id"], "name": user["name"]}

# --- Эндпоинты ---

@app.post("/api/login", response_model=UserResponse)
def login(data: UserLogin, response: Response):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, password_hash, coins, exp, score FROM users WHERE name = ?", (data.name,))
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверное имя или пароль")

    user_id = row["id"]
    session_id = os.urandom(24).hex()
    active_sessions[session_id] = user_id

    response.set_cookie(
        key="session_id",
        value=session_id,
        httponly=True,
        secure=True,  
        samesite="none"
    )

    return {
        "id": user_id,
        "name": row["name"],
        "coins": row["coins"],
        "exp": row["exp"],
        "score": row["score"]
    }

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
    request: Request,  # Добавляем параметр request
    current_user = Depends(get_current_user)
):
    # Отладочная информация
    session_id = request.cookies.get("session_id")
    print(f"DEBUG: Session ID from cookie: {session_id}")
    print(f"DEBUG: Current user: {current_user}")
    
    if current_user["id"] != 175:
        raise HTTPException(status_code=403, detail="Только Наталья может начислять коины")

    if amount <= 0:
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE name = ?", (target_name,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    cursor.execute("UPDATE users SET coins = coins + ? WHERE name = ?", (amount, target_name))
    cursor.execute(
        "INSERT INTO transactions (user_id, admin_id, action, amount, resource, comment) VALUES (?, ?, ?, ?, ?, ?)",
        (target["id"], current_user["id"], "add", amount, "coins", f"Начислено админом {current_user['name']}")
    )

    conn.commit()
    conn.close()
    return {"message": f"{amount} коинов добавлено {target_name}"}

# --- История ---
@app.get("/api/history/{user_id}")
def get_history(user_id: int):
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