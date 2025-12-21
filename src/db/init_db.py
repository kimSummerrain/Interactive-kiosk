import sqlite3

DB_PATH = "kiosk.db"

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # --------------------
    # 1️⃣ 메뉴 테이블
    # --------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS menus (
      menu_id TEXT PRIMARY KEY,
      menu_index INTEGER NOT NULL,
      name TEXT NOT NULL,
      price INTEGER NOT NULL,
      image_path TEXT
    )
    """)

    # --------------------
    # 2️⃣ 나이대별 통계
    # --------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS age_menu_stats (
      age_group TEXT PRIMARY KEY,
      menu_1 INTEGER DEFAULT 0,
      menu_2 INTEGER DEFAULT 0,
      menu_3 INTEGER DEFAULT 0,
      menu_4 INTEGER DEFAULT 0,
      menu_5 INTEGER DEFAULT 0,
      menu_6 INTEGER DEFAULT 0,
      menu_7 INTEGER DEFAULT 0,
      menu_8 INTEGER DEFAULT 0,
      menu_9 INTEGER DEFAULT 0,
      menu_10 INTEGER DEFAULT 0
    )
    """)

    # 기본 나이대 row
    cur.execute("INSERT OR IGNORE INTO age_menu_stats (age_group) VALUES ('10_40')")
    cur.execute("INSERT OR IGNORE INTO age_menu_stats (age_group) VALUES ('41_50')")

    # --------------------
    # 3️⃣ ⭐ 날씨 테이블
    # --------------------
    cur.execute("""
    CREATE TABLE IF NOT EXISTS weather_hourly (
      datetime TEXT PRIMARY KEY,
      temperature REAL,
      weather TEXT
    )
    """)

    conn.commit()
    conn.close()

if __name__ == "__main__":
    init_db()
