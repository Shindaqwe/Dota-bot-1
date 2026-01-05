import os
import logging
import sqlite3
from datetime import datetime

logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        # На Railway используем переменную окружения или SQLite
        self.db_url = os.getenv('DATABASE_URL')
        self.use_postgres = False
        
        if self.db_url and self.db_url.startswith('postgresql://'):
            self.use_postgres = True
            logger.info("Используется PostgreSQL")
        else:
            # Используем SQLite локально
            self.db_file = 'dota2_bot.db'
            logger.info(f"Используется SQLite: {self.db_file}")
    
    def get_connection(self):
        if self.use_postgres:
            # Для Railway с PostgreSQL
            import psycopg2
            from psycopg2.extras import RealDictCursor
            return psycopg2.connect(self.db_url, cursor_factory=RealDictCursor)
        else:
            # Локально с SQLite
            conn = sqlite3.connect(self.db_file)
            conn.row_factory = sqlite3.Row
            return conn
    
    def init_db(self):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.use_postgres:
            # PostgreSQL таблицы
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id BIGINT PRIMARY KEY,
                    account_id BIGINT NOT NULL,
                    score INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS friends (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(telegram_id),
                    friend_account_id BIGINT NOT NULL,
                    friend_name TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        else:
            # SQLite таблицы
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    telegram_id INTEGER PRIMARY KEY,
                    account_id INTEGER NOT NULL,
                    score INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS friends (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    friend_account_id INTEGER NOT NULL,
                    friend_name TEXT,
                    added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(telegram_id)
                )
            ''')
        
        conn.commit()
        conn.close()
        logger.info("✅ База данных инициализирована")
    
    def bind_user(self, telegram_id, account_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.use_postgres:
            cursor.execute('''
                INSERT INTO users (telegram_id, account_id)
                VALUES (%s, %s)
                ON CONFLICT (telegram_id) 
                DO UPDATE SET account_id = EXCLUDED.account_id
            ''', (telegram_id, account_id))
        else:
            cursor.execute('''
                INSERT OR REPLACE INTO users (telegram_id, account_id)
                VALUES (?, ?)
            ''', (telegram_id, account_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_account_id(self, telegram_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.use_postgres:
            cursor.execute('SELECT account_id FROM users WHERE telegram_id = %s', (telegram_id,))
        else:
            cursor.execute('SELECT account_id FROM users WHERE telegram_id = ?', (telegram_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return row['account_id'] if self.use_postgres else row[0]
        return None
    
    def add_friend(self, telegram_id, friend_account_id, friend_name):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.use_postgres:
            cursor.execute('''
                INSERT INTO friends (user_id, friend_account_id, friend_name)
                VALUES (%s, %s, %s)
            ''', (telegram_id, friend_account_id, friend_name))
        else:
            cursor.execute('''
                INSERT INTO friends (user_id, friend_account_id, friend_name)
                VALUES (?, ?, ?)
            ''', (telegram_id, friend_account_id, friend_name))
        
        conn.commit()
        conn.close()
        return True
    
    def get_friends(self, telegram_id):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.use_postgres:
            cursor.execute('''
                SELECT friend_account_id, friend_name 
                FROM friends 
                WHERE user_id = %s
                ORDER BY added_at DESC
            ''', (telegram_id,))
        else:
            cursor.execute('''
                SELECT friend_account_id, friend_name 
                FROM friends 
                WHERE user_id = ?
                ORDER BY added_at DESC
            ''', (telegram_id,))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            if self.use_postgres:
                result.append(dict(row))
            else:
                result.append({
                    'friend_account_id': row[0],
                    'friend_name': row[1]
                })
        return result
    
    def update_score(self, telegram_id, points):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.use_postgres:
            cursor.execute('''
                UPDATE users 
                SET score = score + %s 
                WHERE telegram_id = %s
            ''', (points, telegram_id))
        else:
            cursor.execute('''
                UPDATE users 
                SET score = score + ? 
                WHERE telegram_id = ?
            ''', (points, telegram_id))
        
        conn.commit()
        conn.close()
        return True
    
    def get_leaderboard(self, limit=10):
        conn = self.get_connection()
        cursor = conn.cursor()
        
        if self.use_postgres:
            cursor.execute('''
                SELECT telegram_id, score 
                FROM users 
                ORDER BY score DESC 
                LIMIT %s
            ''', (limit,))
        else:
            cursor.execute('''
                SELECT telegram_id, score 
                FROM users 
                ORDER BY score DESC 
                LIMIT ?
            ''', (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        result = []
        for row in rows:
            if self.use_postgres:
                result.append(dict(row))
            else:
                result.append({
                    'telegram_id': row[0],
                    'score': row[1]
                })
        return result

# Создаем глобальный экземпляр
db = Database()

# Функции для обратной совместимости
def init_db():
    return db.init_db()

def bind_user(telegram_id, account_id):
    return db.bind_user(telegram_id, account_id)

def get_account_id(telegram_id):
    return db.get_account_id(telegram_id)

def add_friend(telegram_id, friend_account_id, friend_name):
    return db.add_friend(telegram_id, friend_account_id, friend_name)

def get_friends(telegram_id):
    return db.get_friends(telegram_id)

def update_score(telegram_id, points):
    return db.update_score(telegram_id, points)

def get_leaderboard(limit=10):
    return db.get_leaderboard(limit)