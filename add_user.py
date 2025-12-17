from database import get_db_connection
from models import hash_password

conn = get_db_connection()
cursor = conn.cursor()

# Пример: добавить Наталью Сюр
cursor.execute(
    "INSERT OR REPLACE INTO users (id, name, password_hash, coins, exp, score) VALUES (?, ?, ?, ?, ?, ?)",
    (175, "Наталья Сюр", hash_password("natalia123"), 0, 0, 0)
)

conn.commit()
conn.close()
print("✅ Пользователь добавлен")