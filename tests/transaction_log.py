import sqlite3, json, os, sys
from datetime import datetime
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT, asset TEXT, amount REAL,
    gas_fee REAL DEFAULT 0.0, network TEXT, status TEXT DEFAULT 'pending',
    tx_hash TEXT, kill_switch_on INTEGER DEFAULT 0, error TEXT, timestamp TEXT
);
CREATE TABLE IF NOT EXISTS kill_switch_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, action TEXT, reason TEXT, timestamp TEXT
);
CREATE TABLE IF NOT EXISTS bug_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT, bug_id TEXT UNIQUE, title TEXT,
    severity TEXT, steps TEXT, expected TEXT, actual TEXT,
    status TEXT DEFAULT 'open', reported_at TEXT
);"""

def _now(): return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class TransactionLogger:

    def __init__(self, db="wallet_qa.db"):
        self.conn = sqlite3.connect(db)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def log_preview(self, preview, kill_switch_on=False):
        """Save a TransactionPreview as 'pending'. Returns row ID."""
        cur = self.conn.execute(
            "INSERT INTO transactions (asset,amount,gas_fee,network,status,kill_switch_on,timestamp) VALUES (?,?,?,?,?,?,?)",
            (preview.draft.symbol, float(preview.draft.amount), float(preview.est_fee),
             preview.network, "pending", int(kill_switch_on), _now())
        )
        self.conn.commit()
        return cur.lastrowid

    def log_result(self, tx_id, result):
        """Update a pending row with the SendResult (confirmed / blocked / failed)."""
        status = "confirmed" if result.ok else ("blocked" if result.error and "Kill switch" in result.error else "failed")
        self.conn.execute("UPDATE transactions SET status=?, tx_hash=?, error=? WHERE id=?",
                          (status, result.tx_hash, result.error, tx_id))
        self.conn.commit()

    def log_kill_switch(self, action, reason=""):
        self.conn.execute("INSERT INTO kill_switch_log (action,reason,timestamp) VALUES (?,?,?)",
                          (action, reason, _now()))
        self.conn.commit()

    def summary(self):
        q = lambda sql: self.conn.execute(sql).fetchone()[0]
        return {
            "total"    : q("SELECT COUNT(*) FROM transactions"),
            "confirmed": q("SELECT COUNT(*) FROM transactions WHERE status='confirmed'"),
            "blocked"  : q("SELECT COUNT(*) FROM transactions WHERE status='blocked'"),
            "failed"   : q("SELECT COUNT(*) FROM transactions WHERE status='failed'"),
            "ks_events": q("SELECT COUNT(*) FROM kill_switch_log"),
        }

    def export(self, path="qa_report.json"):
        self.conn.row_factory = sqlite3.Row
        rows = self.conn.execute("SELECT * FROM transactions").fetchall()
        with open(path, "w") as f:
            json.dump({"summary": self.summary(),
                       "transactions": [dict(zip(r.keys(), tuple(r))) for r in rows]}, f, indent=2)
        print(f"  Exported to {path}")


class BugLog:
    _count = 0

    def __init__(self, db="wallet_qa.db"):
        self.conn = sqlite3.connect(db)
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def report(self, title, severity, steps, expected, actual):
        BugLog._count += 1
        bug_id = f"BUG-{BugLog._count:03d}"
        self.conn.execute(
            "INSERT OR IGNORE INTO bug_log (bug_id,title,severity,steps,expected,actual,reported_at) VALUES (?,?,?,?,?,?,?)",
            (bug_id, title, severity, steps, expected, actual, _now()))
        self.conn.commit()
        print(f"  {bug_id}: {title} [{severity.upper()}]")
        return bug_id

    def resolve(self, bug_id):
        self.conn.execute("UPDATE bug_log SET status='fixed' WHERE bug_id=?", (bug_id,))
        self.conn.commit()

    def print_report(self):
        print("\n── Bug Log " + "─" * 48)
        for r in self.conn.execute("SELECT * FROM bug_log").fetchall():
            print(f"  {'✅' if r[7]=='fixed' else '🔴'} [{r[1]}] {r[2]} | {r[3].upper()} | {r[7]}")
            print(f"     Steps: {r[4]}  |  Expected: {r[5]}  |  Actual: {r[6]}")
        print("─" * 58)


if __name__ == "__main__":
    import tempfile
    from walletapp.models import AssetKind, TransactionDraft
    from walletapp.services.secure_backend import SecureWalletBackend

    for f in ["wallet_qa.db", "qa_report.json"]:
        if os.path.exists(f): os.remove(f)

    vault = SecureWalletBackend(tempfile.mktemp(suffix=".db"))
    vault.initialize_vault("testpass123")
    log, bugs = TransactionLogger(), BugLog()

    # Valid send
    d1 = TransactionDraft(AssetKind.CRYPTO, "ETH", 0.1, "0xABCD")
    p1 = vault.preview_transaction(d1)
    log.log_result(log.log_preview(p1), vault.send_transaction(p1))

    # Kill switch block
    vault.save_security_settings(killswitch=True, require_pin=False, biometrics=False)
    log.log_kill_switch("activated", "Suspicious transfer")
    d2 = TransactionDraft(AssetKind.CRYPTO, "ETH", 0.5, "0xBAD")
    p2 = vault.preview_transaction(d2)
    log.log_result(log.log_preview(p2, kill_switch_on=True), vault.send_transaction(p2))
    vault.save_security_settings(killswitch=False, require_pin=False, biometrics=False)
    log.log_kill_switch("deactivated", "User verified")

    # Insufficient funds
    d3 = TransactionDraft(AssetKind.CRYPTO, "ETH", 9999.0, "0xABCD")
    p3 = vault.preview_transaction(d3)
    log.log_result(log.log_preview(p3), vault.send_transaction(p3))

    bugs.report("StubBackend.preview_transaction unreachable (indentation bug)",
                "critical", "Call StubBackend().preview_transaction()",
                "TransactionPreview returned", "Method nested inside get_portfolio_total_usd — never runs")
    b2 = bugs.report("MarketService returns 0.0 on API failure with no fallback",
                     "high", "Disable network, check portfolio total",
                     "Cached price or error label", "Shows $0.00 silently")
    bugs.resolve(b2)

    s = log.summary()
    print(f"\nTotal:{s['total']} Confirmed:{s['confirmed']} Blocked:{s['blocked']} Failed:{s['failed']} KS:{s['ks_events']}")
    bugs.print_report()
    log.export()
