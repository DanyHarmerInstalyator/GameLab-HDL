# backend/reset_password.py
import sys
import secrets
import string
from database import get_db_connection
from models import hash_password

def generate_password(length=8):
    """Генерирует случайный надёжный пароль"""
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(length))

def reset_password(name: str, new_password: str = None):
    """
    Сбрасывает пароль пользователя.
    Если new_password не задан — генерирует автоматически.
    """
    if not new_password:
        new_password = generate_password(8)

    conn = get_db_connection()
    cursor = conn.cursor()

    # Обновляем хеш пароля
    cursor.execute(
        "UPDATE users SET password_hash = ? WHERE name = ?",
        (hash_password(new_password), name)
    )

    if cursor.rowcount == 0:
        print(f"❌ Пользователь '{name}' не найден в базе.")
    else:
        print(f"✅ Пароль для '{name}' успешно обновлён!")
        print(f"🔑 Новый пароль: {new_password}")
        print("\n⚠️  Передай его сотруднику лично и попроси сменить при первой возможности.")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python reset_password.py \"ФИО сотрудника\" [новый_пароль]")
        sys.exit(1)

    name = sys.argv[1]
    password = sys.argv[2] if len(sys.argv) > 2 else None
    reset_password(name, password)