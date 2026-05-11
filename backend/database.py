"""
Persistence: Neon (PostgreSQL) when DATABASE_URL is postgres*, else SQLite.
CSV import runs only on SQLite unless ENABLE_CSV_IMPORT=1.
"""
from __future__ import annotations

import os
import sqlite3

import pandas as pd
from werkzeug.security import generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

try:
    from dotenv import load_dotenv

    load_dotenv(os.path.join(BASE_DIR, ".env"))
except ImportError:
    pass

CSV_EXPENSES = os.path.join(BASE_DIR, "expenses.csv")
CSV_BANKS = os.path.join(BASE_DIR, "banks.csv")
CSV_BILLS = os.path.join(BASE_DIR, "credit_bills.csv")


def _is_postgres() -> bool:
    u = os.environ.get("DATABASE_URL", "").strip()
    return u.startswith(("postgres://", "postgresql://"))


def _pg_dsn() -> str:
    return os.environ["DATABASE_URL"].strip()


def _q(sql: str) -> str:
    return sql.replace("?", "%s") if _is_postgres() else sql


def _connect():
    if _is_postgres():
        import psycopg
        from psycopg.rows import dict_row

        return psycopg.connect(_pg_dsn(), row_factory=dict_row)
    path = _get_sqlite_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    return conn


def _get_sqlite_path():
    explicit = os.environ.get("EXPENSE_TRACKER_DB", "").strip()
    if explicit:
        return explicit if os.path.isabs(explicit) else os.path.normpath(os.path.join(BASE_DIR, explicit))

    url = os.environ.get("DATABASE_URL", "").strip()
    if url.startswith("sqlite:///"):
        rest = url.removeprefix("sqlite:///")
        if not rest:
            raise ValueError("DATABASE_URL is empty after sqlite:///")
        if rest.startswith("/"):
            return rest
        return os.path.normpath(os.path.join(BASE_DIR, rest))

    return os.path.join(BASE_DIR, "expense_tracker.db")


def _row_dict(row):
    if row is None:
        return {}
    if isinstance(row, dict):
        return dict(row)
    return {k: row[k] for k in row.keys()}


def _insert_return_id(conn, sql: str, params: tuple) -> int:
    """INSERT … VALUES (…) → new primary key id."""
    if _is_postgres():
        cur = conn.execute(_q(sql) + " RETURNING id", params)
        row = cur.fetchone()
        return int(row["id"] if isinstance(row, dict) else row[0])

    full = sql + " RETURNING id"
    try:
        cur = conn.execute(full, params)
        row = cur.fetchone()
        if row is not None:
            return int(row[0])
    except sqlite3.OperationalError:
        pass
    cur = conn.execute(sql, params)
    return int(cur.lastrowid)


def _is_duplicate_email_error(exc: BaseException) -> bool:
    if isinstance(exc, sqlite3.IntegrityError):
        return "UNIQUE" in str(exc).upper()
    if _is_postgres():
        from psycopg.errors import UniqueViolation

        return isinstance(exc, UniqueViolation)
    return False


# --- schema ---


def _table_columns_sqlite(conn, table: str):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def _pg_column_exists(conn, table: str, column: str) -> bool:
    row = conn.execute(
        """
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = 'public' AND table_name = %s AND column_name = %s
        LIMIT 1
        """,
        (table, column),
    ).fetchone()
    return row is not None


def _ensure_user_id_column_sqlite(conn, table: str):
    if "user_id" in _table_columns_sqlite(conn, table):
        return
    conn.execute(f"ALTER TABLE {table} ADD COLUMN user_id INTEGER REFERENCES users(id)")


def _ensure_user_id_column_pg(conn, table: str):
    if _pg_column_exists(conn, table, "user_id"):
        return
    conn.execute(
        f"ALTER TABLE {table} ADD COLUMN user_id BIGINT REFERENCES users(id)"
    )


def _ensure_legacy_migration_user_sqlite(conn):
    needs_user = False
    for table in ("expenses", "banks", "credit_bills"):
        if "user_id" not in _table_columns_sqlite(conn, table):
            continue
        n = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE user_id IS NULL").fetchone()[0]
        if n:
            needs_user = True
            break
    if not needs_user:
        return

    if conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 0:
        email = os.environ.get("MIGRATION_ADMIN_EMAIL", "legacy@migrated.local").strip().lower()
        password = os.environ.get("MIGRATION_ADMIN_PASSWORD", "ChangeThisPassword1!")
        conn.execute(
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email, generate_password_hash(password)),
        )

    uid = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()[0]
    for table in ("expenses", "banks", "credit_bills"):
        if "user_id" not in _table_columns_sqlite(conn, table):
            continue
        conn.execute(f"UPDATE {table} SET user_id=? WHERE user_id IS NULL", (uid,))


def _ensure_legacy_migration_user_pg(conn):
    for table in ("expenses", "banks", "credit_bills"):
        if not _pg_column_exists(conn, table, "user_id"):
            continue
        r = conn.execute(
            f"SELECT COUNT(*) AS c FROM {table} WHERE user_id IS NULL"
        ).fetchone()
        cnt = int(r["c"] if isinstance(r, dict) else r[0])
        if cnt == 0:
            continue
        ur = conn.execute("SELECT COUNT(*) AS c FROM users").fetchone()
        if int(ur["c"] if isinstance(ur, dict) else ur[0]) == 0:
            email = os.environ.get("MIGRATION_ADMIN_EMAIL", "legacy@migrated.local").strip().lower()
            password = os.environ.get("MIGRATION_ADMIN_PASSWORD", "ChangeThisPassword1!")
            conn.execute(
                _q("INSERT INTO users (email, password_hash) VALUES (?, ?)"),
                (email, generate_password_hash(password)),
            )
            conn.commit()
        row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
        uid = int(row["id"] if isinstance(row, dict) else row[0])
        conn.execute(
            _q(f"UPDATE {table} SET user_id = ? WHERE user_id IS NULL"),
            (uid,),
        )
    conn.commit()


def _init_schema_sqlite(conn):
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE COLLATE NOCASE,
            password_hash TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            category TEXT,
            description TEXT,
            amount REAL,
            payment_method TEXT
        );
        CREATE TABLE IF NOT EXISTS banks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT,
            balance REAL
        );
        CREATE TABLE IF NOT EXISTS credit_bills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            card_name TEXT,
            bill_date TEXT,
            bill_amount REAL,
            paid_amount REAL,
            paid_date TEXT,
            from_bank TEXT
        );
        """
    )
    conn.commit()
    _ensure_user_id_column_sqlite(conn, "expenses")
    _ensure_user_id_column_sqlite(conn, "banks")
    _ensure_user_id_column_sqlite(conn, "credit_bills")
    conn.commit()
    _ensure_legacy_migration_user_sqlite(conn)
    conn.commit()


def _init_schema_pg(conn):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id BIGSERIAL PRIMARY KEY AUTOINCREMENT,
            email TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS expenses (
            id BIGSERIAL PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            category TEXT,
            description TEXT,
            amount DOUBLE PRECISION,
            payment_method TEXT,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS banks (
            id BIGSERIAL PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT,
            balance DOUBLE PRECISION,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS credit_bills (
            id BIGSERIAL PRIMARY KEY AUTOINCREMENT,
            card_name TEXT,
            bill_date TEXT,
            bill_amount DOUBLE PRECISION,
            paid_amount DOUBLE PRECISION,
            paid_date TEXT,
            from_bank TEXT,
            user_id BIGINT REFERENCES users(id) ON DELETE CASCADE
        )
        """
    )
    conn.commit()
    for t in ("expenses", "banks", "credit_bills"):
        _ensure_user_id_column_pg(conn, t)
    conn.commit()
    _ensure_legacy_migration_user_pg(conn)
    conn.commit()


def _csv_owner_user_id_sqlite(conn):
    row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    if row:
        return row[0]
    if not (
        (os.path.isfile(CSV_EXPENSES) and _csv_row_count(CSV_EXPENSES) > 0)
        or (os.path.isfile(CSV_BANKS) and _csv_row_count(CSV_BANKS) > 0)
        or (os.path.isfile(CSV_BILLS) and _csv_row_count(CSV_BILLS) > 0)
    ):
        return None
    email = os.environ.get("MIGRATION_ADMIN_EMAIL", "legacy@migrated.local").strip().lower()
    password = os.environ.get("MIGRATION_ADMIN_PASSWORD", "ChangeThisPassword1!")
    conn.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (email, generate_password_hash(password)),
    )
    conn.commit()
    return conn.execute("SELECT last_insert_rowid()").fetchone()[0]


def _csv_owner_user_id_pg(conn):
    row = conn.execute("SELECT id FROM users ORDER BY id LIMIT 1").fetchone()
    if row:
        return int(row["id"] if isinstance(row, dict) else row[0])
    if os.environ.get("ENABLE_CSV_IMPORT", "").lower() not in ("1", "true", "yes"):
        return None
    if not (
        (os.path.isfile(CSV_EXPENSES) and _csv_row_count(CSV_EXPENSES) > 0)
        or (os.path.isfile(CSV_BANKS) and _csv_row_count(CSV_BANKS) > 0)
        or (os.path.isfile(CSV_BILLS) and _csv_row_count(CSV_BILLS) > 0)
    ):
        return None
    email = os.environ.get("MIGRATION_ADMIN_EMAIL", "legacy@migrated.local").strip().lower()
    password = os.environ.get("MIGRATION_ADMIN_PASSWORD", "ChangeThisPassword1!")
    conn.execute(
        _q("INSERT INTO users (email, password_hash) VALUES (?, ?)"),
        (email, generate_password_hash(password)),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM users ORDER BY id DESC LIMIT 1").fetchone()
    return int(row["id"] if isinstance(row, dict) else row[0])


def _csv_row_count(path):
    try:
        df = pd.read_csv(path)
        return len(df)
    except (ValueError, pd.errors.EmptyDataError):
        return 0


def _migrate_from_csv_if_empty(conn):
    if os.environ.get("DISABLE_CSV_IMPORT", "").lower() in ("1", "true", "yes"):
        conn.commit()
        return
    if _is_postgres() and os.environ.get("ENABLE_CSV_IMPORT", "").lower() not in ("1", "true", "yes"):
        conn.commit()
        return

    def count(table):
        r = conn.execute(_q(f"SELECT COUNT(*) AS c FROM {table}")).fetchone()
        return int(r["c"] if isinstance(r, dict) else r[0])

    if _is_postgres():
        csv_uid = _csv_owner_user_id_pg(conn)
    else:
        csv_uid = _csv_owner_user_id_sqlite(conn)
    if csv_uid is None:
        conn.commit()
        return

    if count("expenses") == 0 and os.path.isfile(CSV_EXPENSES):
        try:
            df = pd.read_csv(CSV_EXPENSES).fillna("")
            for _, r in df.iterrows():
                conn.execute(
                    _q(
                        """
                    INSERT INTO expenses (id, date, category, description, amount, payment_method, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """
                    ),
                    (
                        int(r["id"]),
                        str(r.get("date", "")),
                        str(r.get("category", "")),
                        str(r.get("description", "")),
                        float(r["amount"]) if str(r.get("amount", "")).strip() != "" else 0.0,
                        str(r.get("payment_method", "")),
                        csv_uid,
                    ),
                )
        except (ValueError, KeyError, pd.errors.EmptyDataError):
            pass

    if count("banks") == 0 and os.path.isfile(CSV_BANKS):
        try:
            df = pd.read_csv(CSV_BANKS).fillna("")
            for _, r in df.iterrows():
                conn.execute(
                    _q("INSERT INTO banks (id, bank_name, balance, user_id) VALUES (?, ?, ?, ?)"),
                    (
                        int(r["id"]),
                        str(r.get("bank_name", "")),
                        float(r["balance"]) if str(r.get("balance", "")).strip() != "" else 0.0,
                        csv_uid,
                    ),
                )
        except (ValueError, KeyError, pd.errors.EmptyDataError):
            pass

    if count("credit_bills") == 0 and os.path.isfile(CSV_BILLS):
        try:
            df = pd.read_csv(CSV_BILLS).fillna("")
            for _, r in df.iterrows():
                conn.execute(
                    _q(
                        """
                    INSERT INTO credit_bills
                    (id, card_name, bill_date, bill_amount, paid_amount, paid_date, from_bank, user_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """
                    ),
                    (
                        int(r["id"]),
                        str(r.get("card_name", "")),
                        str(r.get("bill_date", "")),
                        float(r["bill_amount"]) if str(r.get("bill_amount", "")).strip() != "" else 0.0,
                        float(r["paid_amount"]) if str(r.get("paid_amount", "")).strip() != "" else 0.0,
                        str(r.get("paid_date", "")),
                        str(r.get("from_bank", "")),
                        csv_uid,
                    ),
                )
        except (ValueError, KeyError, pd.errors.EmptyDataError):
            pass

    conn.commit()


def init_db():
    conn = _connect()
    try:
        if _is_postgres():
            _init_schema_pg(conn)
        else:
            _init_schema_sqlite(conn)
        _migrate_from_csv_if_empty(conn)
    finally:
        conn.close()


# --- users ---


def user_create(email: str, password_hash: str) -> int:
    conn = _connect()
    try:
        rid = _insert_return_id(
            conn,
            "INSERT INTO users (email, password_hash) VALUES (?, ?)",
            (email.strip().lower(), password_hash),
        )
        conn.commit()
        return rid
    except Exception as e:
        conn.rollback()
        if _is_duplicate_email_error(e):
            raise ValueError("email_taken") from e
        raise
    finally:
        conn.close()


def user_by_email(email: str):
    conn = _connect()
    try:
        if _is_postgres():
            return conn.execute(
                _q("SELECT id, email, password_hash FROM users WHERE email = ?"),
                (email.strip().lower(),),
            ).fetchone()
        return conn.execute(
            "SELECT id, email, password_hash FROM users WHERE email = ? COLLATE NOCASE",
            (email.strip().lower(),),
        ).fetchone()
    finally:
        conn.close()


def user_by_id(user_id: int):
    conn = _connect()
    try:
        return conn.execute(
            _q("SELECT id, email FROM users WHERE id = ?"),
            (user_id,),
        ).fetchone()
    finally:
        conn.close()


# --- expenses ---


def _expense_from_row(row):
    d = _row_dict(row)
    d.pop("user_id", None)
    for k in ("date", "category", "description", "payment_method"):
        if d.get(k) is None:
            d[k] = ""
    if d.get("amount") is None:
        d["amount"] = 0.0
    else:
        d["amount"] = float(d["amount"])
    return d


def expenses_list(user_id: int):
    conn = _connect()
    try:
        rows = conn.execute(
            _q("SELECT * FROM expenses WHERE user_id = ? ORDER BY id"),
            (user_id,),
        ).fetchall()
        return [_expense_from_row(r) for r in rows]
    finally:
        conn.close()


def expenses_analytics(user_id: int):
    conn = _connect()
    try:
        total_row = conn.execute(
            _q("SELECT COALESCE(SUM(amount), 0) AS s FROM expenses WHERE user_id = ?"),
            (user_id,),
        ).fetchone()
        v = total_row["s"] if isinstance(total_row, dict) else total_row[0]
        total = float(v or 0)
        cur = conn.execute(
            _q(
                "SELECT category AS cat, COALESCE(SUM(amount), 0) AS s FROM expenses WHERE user_id = ? GROUP BY category"
            ),
            (user_id,),
        )
        categories = {}
        for r in cur.fetchall():
            k = r["cat"] if isinstance(r, dict) else r[0]
            val = r["s"] if isinstance(r, dict) else r[1]
            categories[k or ""] = float(val or 0)
        return total, categories
    finally:
        conn.close()


def expense_add(user_id: int, data):
    conn = _connect()
    try:
        new_id = _insert_return_id(
            conn,
            """
            INSERT INTO expenses
            (date, category, description, amount, payment_method, user_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("date"),
                data.get("category"),
                data.get("description", ""),
                float(data.get("amount", 0)),
                data.get("payment_method", ""),
                user_id,
            ),
        )
        conn.commit()
        return new_id
    finally:
        conn.close()


def expense_delete(user_id: int, expense_id):
    conn = _connect()
    try:
        cur = conn.execute(
            _q("DELETE FROM expenses WHERE id = ? AND user_id = ?"),
            (expense_id, user_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def expense_update(user_id: int, expense_id, data):
    conn = _connect()
    try:
        cur = conn.execute(
            _q(
                """
            UPDATE expenses SET date=?, category=?, description=?, amount=?, payment_method=?
            WHERE id=? AND user_id=?
            """
            ),
            (
                data.get("date"),
                data.get("category"),
                data.get("description"),
                float(data.get("amount", 0)),
                data.get("payment_method"),
                expense_id,
                user_id,
            ),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- banks ---


def _bank_from_row(row):
    d = _row_dict(row)
    d.pop("user_id", None)
    if d.get("bank_name") is None:
        d["bank_name"] = ""
    if d.get("balance") is None:
        d["balance"] = 0.0
    else:
        d["balance"] = float(d["balance"])
    return d


def banks_list(user_id: int):
    conn = _connect()
    try:
        rows = conn.execute(
            _q("SELECT * FROM banks WHERE user_id = ? ORDER BY id"),
            (user_id,),
        ).fetchall()
        return [_bank_from_row(r) for r in rows]
    finally:
        conn.close()


def bank_add(user_id: int, data):
    conn = _connect()
    try:
        new_id = _insert_return_id(
            conn,
            """
            INSERT INTO banks (bank_name, balance, user_id)
            VALUES (?, ?, ?)
            """,
            (
                data.get("bank_name", ""),
                float(data.get("balance", 0)),
                user_id,
            ),
        )
        conn.commit()
        return new_id
    finally:
        conn.close()


def bank_delete(user_id: int, bank_id):
    conn = _connect()
    try:
        cur = conn.execute(
            _q("DELETE FROM banks WHERE id = ? AND user_id = ?"),
            (bank_id, user_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def bank_update(user_id: int, bank_id, data):
    conn = _connect()
    try:
        cur = conn.execute(
            _q("UPDATE banks SET bank_name=?, balance=? WHERE id=? AND user_id=?"),
            (data.get("bank_name"), float(data.get("balance", 0)), bank_id, user_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


# --- bills ---


def _bill_from_row(row):
    d = _row_dict(row)
    d.pop("user_id", None)
    for k in ("card_name", "bill_date", "paid_date", "from_bank"):
        if d.get(k) is None:
            d[k] = ""
    for k in ("bill_amount", "paid_amount"):
        if d.get(k) is None:
            d[k] = 0.0
        else:
            d[k] = float(d[k])
    return d


def bills_list(user_id: int):
    conn = _connect()
    try:
        rows = conn.execute(
            _q("SELECT * FROM credit_bills WHERE user_id = ? ORDER BY id"),
            (user_id,),
        ).fetchall()
        return [_bill_from_row(r) for r in rows]
    finally:
        conn.close()


def bill_add(user_id: int, data):
    conn = _connect()
    try:
        new_id = _insert_return_id(
            conn,
            """
            INSERT INTO credit_bills
            (card_name, bill_date, bill_amount, paid_amount, paid_date, from_bank, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("card_name", ""),
                data.get("bill_date", ""),
                float(data.get("bill_amount", 0)),
                float(data.get("paid_amount", 0)),
                data.get("paid_date", ""),
                data.get("from_bank", ""),
                user_id,
            ),
        )
        conn.commit()
        return new_id
    finally:
        conn.close()


def bill_delete(user_id: int, bill_id):
    conn = _connect()
    try:
        cur = conn.execute(
            _q("DELETE FROM credit_bills WHERE id = ? AND user_id = ?"),
            (bill_id, user_id),
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def bill_update(user_id: int, bill_id, data):
    conn = _connect()
    try:
        cur = conn.execute(
            _q(
                """
            UPDATE credit_bills SET
                card_name=?, bill_date=?, bill_amount=?, paid_amount=?, paid_date=?, from_bank=?
            WHERE id=? AND user_id=?
            """
            ),
            (
                data.get("card_name", ""),
                data.get("bill_date", ""),
                float(data.get("bill_amount", 0)),
                float(data.get("paid_amount", 0)),
                data.get("paid_date", ""),
                data.get("from_bank", ""),
                bill_id,
                user_id,
            ),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()
