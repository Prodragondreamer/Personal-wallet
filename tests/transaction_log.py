import sqlite3
import json
from datetime import datetime


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# SQL SCHEME
SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    asset          TEXT,
    amount         REAL,
    gas_fee        REAL    DEFAULT 0.0,
    status         TEXT    DEFAULT 'pending',
    kill_switch_on INTEGER DEFAULT 0,
    timestamp      TEXT
);
CREATE TABLE IF NOT EXISTS kill_switch_log (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    action    TEXT,
    reason    TEXT,
    timestamp TEXT
);
CREATE TABLE IF NOT EXISTS bug_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    bug_id      TEXT UNIQUE,
    title       TEXT,
    severity    TEXT,
    steps       TEXT,
    expected    TEXT,
    actual      TEXT,
    status      TEXT DEFAULT 'open',
    reported_at TEXT
);
"""


# The Transaction Logger Logic
class TransactionLogger:

    def __init__(self, db="wallet.db"):
        self.conn = sqlite3.connect(db)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def log(self, asset, amount, status="pending", gas_fee=0.0, kill_switch_on=False):
        """Log one transaction. Returns the new row ID."""
        cur = self.conn.execute(
            "INSERT INTO transactions (asset, amount, gas_fee, status, kill_switch_on, timestamp) "
            "VALUES (?,?,?,?,?,?)",
            (asset, amount, gas_fee, status, int(kill_switch_on), now())
        )
        self.conn.commit()
        return cur.lastrowid

    def update(self, tx_id, status):
        self.conn.execute("UPDATE transactions SET status=? WHERE id=?", (status, tx_id))
        self.conn.commit()

    def log_kill_switch(self, action, reason=""):
        """action = 'activated' or 'deactivated'"""
        self.conn.execute(
            "INSERT INTO kill_switch_log (action, reason, timestamp) VALUES (?,?,?)",
            (action, reason, now())
        )
        self.conn.commit()

    def summary(self):
        c = self.conn
        return {
            "total"      : c.execute("SELECT COUNT(*) FROM transactions").fetchone()[0],
            "confirmed"  : c.execute("SELECT COUNT(*) FROM transactions WHERE status='confirmed'").fetchone()[0],
            "blocked"    : c.execute("SELECT COUNT(*) FROM transactions WHERE status='blocked'").fetchone()[0],
            "ks_events"  : c.execute("SELECT COUNT(*) FROM kill_switch_log").fetchone()[0],
        }

    def export(self, path="report.json"):
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute("SELECT * FROM transactions").fetchall()
        data = {
            "summary"      : self.summary(),
            "transactions" : [dict(zip(r.keys(), tuple(r))) for r in rows],
        }
        with open(path, "w") as f:
            json.dump(data, f, indent=2)
        print(f"Exported to {path}")


# The Bug Log Logic
class BugLog:
    _count = 0

    def __init__(self, db="wallet.db"):
        self.conn = sqlite3.connect(db)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def report(self, title, severity, steps, expected, actual):
        BugLog._count += 1
        bug_id = f"BUG-{BugLog._count:03d}"
        self.conn.execute(
            "INSERT OR IGNORE INTO bug_log (bug_id,title,severity,steps,expected,actual,reported_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (bug_id, title, severity, steps, expected, actual, now())
        )
        self.conn.commit()
        print(f"  Filed {bug_id}: {title} [{severity.upper()}]")
        return bug_id

    def resolve(self, bug_id):
        self.conn.execute("UPDATE bug_log SET status='fixed' WHERE bug_id=?", (bug_id,))
        self.conn.commit()

    def print_report(self):
        rows = self.conn.execute("SELECT * FROM bug_log").fetchall()
        print("\n── Bug Log " + "─" * 50)
        for r in rows:
            icon = "✅" if r[7] == "fixed" else "🔴"
            print(f"  {icon} [{r[1]}] {r[2]} | {r[3].upper()} | {r[7]}")
            print(f"     Steps   : {r[4]}")
            print(f"     Expected: {r[5]}")
            print(f"     Actual  : {r[6]}")
        print("─" * 60)


# Running it in general
if __name__ == "__main__":
    import os; [os.remove(f) for f in ["wallet.db","report.json"] if os.path.exists(f)]

    log  = TransactionLogger()
    bugs = BugLog()

    # Normal transaction
    log.log("ETH", 0.25, status="confirmed", gas_fee=0.00042)

    # Kill switch activated so it blocks transaction
    log.log_kill_switch("activated", reason="Suspicious activity")
    log.log("ETH", 1.5, status="blocked", kill_switch_on=True)
    log.log_kill_switch("deactivated", reason="User verified")

    # Stock transaction (no gas fee)
    log.log("AAPL", 5, status="confirmed")

    # Bug reports
    b1 = bugs.report(
        title    = "Dashboard shows $0 when CoinGecko is down",
        severity = "high",
        steps    = "Disable network, open app, check dashboard total",
        expected = "Last cached price or 'Unavailable'",
        actual   = "Dashboard shows $0.00"
    )
    b2 = bugs.report(
        title    = "Kill Switch button overlaps balance on iPhone SE",
        severity = "medium",
        steps    = "Open app on 375x667 screen",
        expected = "Button below balance display",
        actual   = "Button covers balance number"
    )
    bugs.resolve(b2)

    # Print summary
    s = log.summary()
    print("\n── Transaction Summary " + "─" * 38)
    print(f"  Total: {s['total']}  |  Confirmed: {s['confirmed']}  |  Blocked: {s['blocked']}  |  KS Events: {s['ks_events']}")
    bugs.print_report()
    log.export()
