import sqlite3

DB_FILE = "skymate.db"

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "CREATE TABLE IF NOT EXISTS passengers (id INTEGER PRIMARY KEY AUTOINCREMENT, phone TEXT UNIQUE, name TEXT, flight TEXT, route TEXT, terminal TEXT, gate TEXT, departure_time TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)"
    )
    c.execute(
        "CREATE TABLE IF NOT EXISTS security_scans (id INTEGER PRIMARY KEY AUTOINCREMENT, entry_time TIMESTAMP, exit_time TIMESTAMP, clearance_minutes REAL, hour_of_day INTEGER)"
    )
    conn.commit()
    conn.close()
    print("Database initialized: skymate.db")

def save_passenger(phone, info):
    conn = get_connection()
    c = conn.cursor()
    c.execute(
        "INSERT INTO passengers (phone,name,flight,route,terminal,gate,departure_time) VALUES (?,?,?,?,?,?,?) ON CONFLICT(phone) DO UPDATE SET name=excluded.name,flight=excluded.flight,route=excluded.route,terminal=excluded.terminal,gate=excluded.gate,departure_time=excluded.departure_time",
        (
            phone,
            info["name"],
            info["flight"],
            info["route"],
            info["terminal"],
            info["gate"],
            info["departure_time"]
        )
    )
    conn.commit()
    conn.close()

def get_passenger(phone):
    conn = get_connection()
    c = conn.cursor()
    c.execute("SELECT * FROM passengers WHERE phone = ?", (phone,))
    row = c.fetchone()
    conn.close()
    if row:
        return {
            "name": row["name"],
            "flight": row["flight"],
            "route": row["route"],
            "terminal": row["terminal"],
            "gate": row["gate"],
            "departure_time": row["departure_time"]
        }
    return None

init_db()