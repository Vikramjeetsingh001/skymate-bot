import sqlite3
import random
from datetime import datetime, timedelta

DB_FILE = "skymate.db"

WAIT_PATTERNS = {
    0: (4, 8), 1: (3, 7), 2: (3, 6), 3: (3, 6), 4: (5, 10), 5: (6, 12),
    6: (8, 15), 7: (12, 22), 8: (18, 28), 9: (20, 30), 10: (15, 22), 11: (12, 18),
    12: (10, 16), 13: (12, 20), 14: (15, 25), 15: (18, 28), 16: (20, 30), 17: (22, 32),
    18: (18, 26), 19: (14, 22), 20: (12, 18), 21: (8, 14), 22: (6, 12), 23: (5, 10)
}

def get_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def populate_simulated_data():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM security_scans")
    now = datetime.now()
    current_time = now.replace(hour=0, minute=0, second=0, microsecond=0)
    while current_time < now:
        hour = current_time.hour
        mn, mx = WAIT_PATTERNS.get(hour, (10, 20))
        for _ in range(random.randint(2, 5)):
            entry_time = current_time + timedelta(minutes=random.randint(0, 9))
            clearance = max(3, random.uniform(mn, mx) + random.gauss(0, 2))
            exit_time = entry_time + timedelta(minutes=clearance)
            cursor.execute(
                "INSERT INTO security_scans (entry_time, exit_time, clearance_minutes, hour_of_day) VALUES (?,?,?,?)",
                (
                    entry_time.isoformat(),
                    exit_time.isoformat(),
                    round(clearance, 1),
                    hour
                )
            )
        current_time += timedelta(minutes=10)
    conn.commit()
    total = cursor.execute("SELECT COUNT(*) FROM security_scans").fetchone()[0]
    conn.close()
    print("Simulated {} security scan records.".format(total))


def get_estimated_wait_time():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT clearance_minutes FROM security_scans ORDER BY entry_time DESC LIMIT 30"
    )
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return None, "No data"
    times = [r["clearance_minutes"] for r in rows]
    g1, g2, g3 = times[:5], times[5:15], times[15:30]
    a1 = sum(g1) / len(g1) if g1 else 0
    a2 = sum(g2) / len(g2) if g2 else 0
    a3 = sum(g3) / len(g3) if g3 else 0
    if g3:
        w = a1 * 0.50 + a2 * 0.35 + a3 * 0.15
    elif g2:
        w = a1 * 0.60 + a2 * 0.40
    else:
        w = a1

    est = round(w)
    if est <= 10:
        s = "Low - Quick clearance"
    elif est <= 20:
        s = "Moderate - Normal wait"
    elif est <= 30:
        s = "High - Expect delays"
    else:
        s = "Very High - Significant delays"
    return est, s

def get_security_alert(dep_str):
    try:
        est, _ = get_estimated_wait_time()
        if not est:
            return None
        h, m = map(int, dep_str.split(":"))
        now = datetime.now()
        dep = now.replace(hour=h, minute=m, second=0)
        left = (dep - now).total_seconds() / 60
        buf = est + 30
        if left < buf:
            return "URGENT: Security ~{} min. Flight at {}. {} min left. Go NOW!".format(
                est,
                dep_str,
                int(left)
            )
        elif left < buf + 30:
            return "HEADS UP: Security ~{} min. Head there soon for {} departure.".format(
                est,
                dep_str
            )
    except:pass
    return None

populate_simulated_data()