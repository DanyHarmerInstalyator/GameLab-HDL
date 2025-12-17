# backend/bulk_add_users.py — начало файла
import traceback

try:
    import json
    import secrets
    import string
    from database import get_db_connection
    from models import hash_password

    def generate_password(length=8):
        chars = string.ascii_letters + string.digits
        return ''.join(secrets.choice(chars) for _ in range(length))

    with open('bitrix_users.json', 'r', encoding='utf-8') as f:
        data = json.load(f)
        bx_users = data.get('result', [])
    if not isinstance(bx_users, list):
       raise ValueError("Ожидался массив пользователей в result")    

    conn = get_db_connection()
    cursor = conn.cursor()
    log_lines = []

    for user in bx_users:
        user_id = int(user['ID'])
        name = f"{user.get('NAME', '')} {user.get('LAST_NAME', '')}".strip()
        if not name or name == " ":
            continue

        cursor.execute("SELECT 1 FROM users WHERE name = ?", (name,))
        if cursor.fetchone():
            print(f"✅ Уже есть: {name}")
            continue

        password = generate_password(8)
        hashed = hash_password(password)

        cursor.execute(
            "INSERT INTO users (id, name, password_hash, coins, exp, score) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, name, hashed, 0, 0, 0)
        )

        log_lines.append(f"{name}: {password}")
        print(f"➕ Добавлен: {name}")

    conn.commit()
    conn.close()

    with open('user_credentials.txt', 'w', encoding='utf-8') as f:
        f.write("\n".join(log_lines))

    print("\n✅ Все новые пользователи добавлены.")
    print("📄 Пароли сохранены в user_credentials.txt")

except Exception as e:
    print("❌ ОШИБКА:")
    traceback.print_exc()