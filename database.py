# backend/database.py
import sqlite3
import os

DB_PATH = os.getenv("DATABASE_URL", "gamelab.db")

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            coins INTEGER DEFAULT 0,
            exp INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            admin_id INTEGER,
            action TEXT NOT NULL,
            amount INTEGER NOT NULL,
            resource TEXT NOT NULL,
            comment TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY(user_id) REFERENCES users(id),
            FOREIGN KEY(admin_id) REFERENCES users(id)
        )
    ''')

    conn.commit()
    conn.close()

def get_db_connection():
    """Возвращает обычное синхронное соединение с SQLite."""
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn