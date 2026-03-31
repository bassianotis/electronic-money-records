"""SQLite database connection and schema management."""
import sqlite3
from flask import g, current_app


def get_db():
    """Get database connection for current request."""
    if 'db' not in g:
        g.db = sqlite3.connect(
            current_app.config['DATABASE'],
            detect_types=sqlite3.PARSE_DECLTYPES
        )
        g.db.row_factory = sqlite3.Row
        g.db.execute('PRAGMA journal_mode=WAL')
        g.db.execute('PRAGMA foreign_keys=ON')
    return g.db


def close_db(e=None):
    """Close database connection at end of request."""
    db = g.pop('db', None)
    if db is not None:
        db.close()


def init_db(app):
    """Create tables if they don't exist and run migrations."""
    with app.app_context():
        db = get_db()
        db.executescript(SCHEMA)
        # Run migrations (safe to re-run — silently skip if column exists)
        for migration in MIGRATIONS:
            try:
                db.execute(migration)
            except Exception:
                pass  # Column already exists
        _seed_defaults(db)
        db.commit()
        close_db()


def init_app(app):
    """Register database lifecycle with Flask app."""
    app.teardown_appcontext(close_db)
    init_db(app)


def _seed_defaults(db):
    """Seed default categories, rules, and accounts if tables are empty."""
    from . import config

    # Seed categories
    count = db.execute('SELECT COUNT(*) FROM categories').fetchone()[0]
    if count == 0:
        for cat in config.DEFAULT_CATEGORIES:
            db.execute(
                'INSERT INTO categories (name, type, schedule_c_line) VALUES (?, ?, ?)',
                (cat['name'], cat['type'], cat.get('schedule_c_line'))
            )

    # Seed accounts
    count = db.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]
    if count == 0:
        for acct in config.DEFAULT_ACCOUNTS:
            db.execute(
                'INSERT INTO accounts (name, account_id, description, is_active) '
                'VALUES (?, ?, ?, 1)',
                (acct['name'], acct['account_id'], acct['description'])
            )

    # Seed categorization rules
    count = db.execute('SELECT COUNT(*) FROM categorization_rules').fetchone()[0]
    if count == 0:
        for rule in config.DEFAULT_RULES:
            cat_row = db.execute(
                'SELECT id FROM categories WHERE name = ?',
                (rule['category'],)
            ).fetchone()
            if cat_row:
                db.execute(
                    'INSERT INTO categorization_rules (keyword, category_id, priority) '
                    'VALUES (?, ?, ?)',
                    (rule['keyword'], cat_row[0], rule['priority'])
                )


SCHEMA = """
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    account_id TEXT UNIQUE,
    description TEXT,
    is_active INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    type TEXT NOT NULL CHECK(type IN ('income', 'expense', 'transfer')),
    schedule_c_line TEXT
);

CREATE TABLE IF NOT EXISTS transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    transaction_id TEXT UNIQUE,
    date TEXT NOT NULL,
    description TEXT NOT NULL,
    amount REAL NOT NULL,
    balance REAL,
    category_id INTEGER REFERENCES categories(id),
    is_transfer INTEGER NOT NULL DEFAULT 0,
    linked_transfer_id INTEGER REFERENCES transactions(id),
    notes TEXT,
    source TEXT NOT NULL DEFAULT 'manual',
    is_reconciled INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (account_id) REFERENCES accounts(id),
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS categorization_rules (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    keyword TEXT NOT NULL,
    category_id INTEGER NOT NULL REFERENCES categories(id),
    priority INTEGER NOT NULL DEFAULT 10,
    FOREIGN KEY (category_id) REFERENCES categories(id)
);

CREATE TABLE IF NOT EXISTS clients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    address TEXT,
    email TEXT
);

CREATE TABLE IF NOT EXISTS invoices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_number INTEGER NOT NULL UNIQUE,
    client_id INTEGER NOT NULL REFERENCES clients(id),
    date TEXT NOT NULL,
    due_date TEXT NOT NULL,
    terms TEXT NOT NULL DEFAULT 'Net 15',
    status TEXT NOT NULL DEFAULT 'draft' CHECK(status IN ('draft', 'sent', 'paid')),
    matched_transaction_id INTEGER REFERENCES transactions(id),
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    FOREIGN KEY (client_id) REFERENCES clients(id)
);

CREATE TABLE IF NOT EXISTS invoice_line_items (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id INTEGER NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    description TEXT NOT NULL,
    quantity REAL NOT NULL DEFAULT 1,
    rate REAL NOT NULL,
    amount REAL NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_transactions_date ON transactions(date);
CREATE INDEX IF NOT EXISTS idx_transactions_category ON transactions(category_id);
CREATE INDEX IF NOT EXISTS idx_transactions_account ON transactions(account_id);
CREATE INDEX IF NOT EXISTS idx_transactions_source ON transactions(source);

CREATE TABLE IF NOT EXISTS contractors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    address TEXT,
    ein_ssn_last4 TEXT,
    w9_received INTEGER NOT NULL DEFAULT 0,
    w9_file TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS health_insurance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    year INTEGER NOT NULL,
    month INTEGER NOT NULL,
    premium REAL NOT NULL,
    advance_ptc REAL DEFAULT 0,
    notes TEXT,
    UNIQUE(year, month)
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL DEFAULT (datetime('now')),
    action TEXT NOT NULL,
    transaction_id INTEGER,
    field_name TEXT,
    old_value TEXT,
    new_value TEXT,
    detail TEXT
);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_transaction ON audit_log(transaction_id);

CREATE TABLE IF NOT EXISTS locked_years (
    year INTEGER PRIMARY KEY,
    locked_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS owners (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    ssn_last4 TEXT,
    is_primary INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS tax_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    jurisdiction TEXT NOT NULL CHECK(jurisdiction IN ('federal','michigan','grand_rapids')),
    quarter TEXT NOT NULL,
    year INTEGER NOT NULL,
    confirmation_number TEXT,
    receipt_file TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_tax_payments_year ON tax_payments(year);

CREATE TABLE IF NOT EXISTS tax_config (
    year INTEGER PRIMARY KEY,
    prior_year_federal REAL NOT NULL DEFAULT 0,
    prior_year_state REAL NOT NULL DEFAULT 0,
    prior_year_city REAL NOT NULL DEFAULT 0,
    agi_over_150k INTEGER NOT NULL DEFAULT 0,
    include_expenses INTEGER NOT NULL DEFAULT 1,
    quarterly_federal REAL NOT NULL DEFAULT 0,
    quarterly_state REAL NOT NULL DEFAULT 0,
    quarterly_city REAL NOT NULL DEFAULT 0
);
"""


# Schema migrations for existing databases
MIGRATIONS = [
    "ALTER TABLE transactions ADD COLUMN owner_split REAL DEFAULT 0.5",
    "ALTER TABLE transactions ADD COLUMN business_use_pct REAL",
    "ALTER TABLE categories ADD COLUMN deductible_pct REAL DEFAULT 1.0",
    "ALTER TABLE transactions ADD COLUMN business_purpose TEXT",
    "ALTER TABLE transactions ADD COLUMN attendees TEXT",
    "ALTER TABLE transactions ADD COLUMN contractor_id INTEGER",
    "ALTER TABLE transactions ADD COLUMN is_reconciled INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE invoices ADD COLUMN matched_transaction_id INTEGER REFERENCES transactions(id)",
    "ALTER TABLE transactions ADD COLUMN linked_transfer_id INTEGER REFERENCES transactions(id)",
]
