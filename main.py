from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
from database import init_db, get_db_connection
from models import verify_password

# Инициализация БД
init_db()

app = FastAPI(title="GameLab HDL Backend")

# ✅ ЕДИНСТВЕННЫЙ, ЧИСТЫЙ CORS — без дублирования и пробелов
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5501",      # VS Code Live Server
        "http://localhost:5501",
        "http://127.0.0.1:5500",      # Другие Live Server варианты
        "http://localhost:5500",
        "http://localhost:8080",
        "https://hdlgame.netlify.app",  # ← БЕЗ пробелов!
        "https://gamelabhdl.netlify.app"  # ← БЕЗ пробелов!
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Схемы ---
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

class AddCoinsRequest(BaseModel):
    target_name: str
    amount: int
    admin_name: str
    admin_password: str

# --- Эндпоинты ---
@app.post("/api/login", response_model=UserResponse)
def login(data: UserLogin):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, password_hash, coins, exp, score FROM users WHERE name = ?", (data.name,))
    row = cursor.fetchone()
    conn.close()

    if not row or not verify_password(data.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Неверное имя или пароль")

    return {
        "id": row["id"],
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
def add_coins(data: AddCoinsRequest):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Проверка администратора
    cursor.execute("SELECT id, password_hash FROM users WHERE name = ?", (data.admin_name,))
    admin = cursor.fetchone()
    if not admin or not verify_password(data.admin_password, admin["password_hash"]):
        conn.close()
        raise HTTPException(status_code=403, detail="Неверные данные администратора")

    # Поиск целевого пользователя
    cursor.execute("SELECT id FROM users WHERE name = ?", (data.target_name,))
    target = cursor.fetchone()
    if not target:
        conn.close()
        raise HTTPException(status_code=404, detail="Пользователь не найден")

    if data.amount <= 0:
        conn.close()
        raise HTTPException(status_code=400, detail="Сумма должна быть положительной")

    # Обновление коинов
    cursor.execute("UPDATE users SET coins = coins + ? WHERE name = ?", (data.amount, data.target_name))

    # Логирование транзакции
    cursor.execute(
        "INSERT INTO transactions (user_id, admin_id, action, amount, resource, comment) VALUES (?, ?, ?, ?, ?, ?)",
        (target["id"], admin["id"], "add", data.amount, "coins", f"Начислено админом {data.admin_name}")
    )

    conn.commit()
    conn.close()
    return {"status": "success", "message": f"{data.amount} коинов добавлено {data.target_name}"}

# --- Дополнительно: debug-эндпоинт (удали после проверки) ---
@app.get("/api/debug/users")
def debug_users():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM users")
    users = [r[0] for r in cursor.fetchall()]
    conn.close()
    return {"users": users}

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
            "resource": row["resource"],        # "coins", "exp", "score"
            "amount": row["amount"],
            "admin": row["admin_name"] or "Система",
            "comment": row["comment"] or "Без комментария"
        }
        for row in rows
    ]