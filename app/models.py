"""Data access layer — direct SQL queries, no ORM."""
from .database import get_db


# ── Accounts ──────────────────────────────────────────────

def get_accounts(active_only=True):
    db = get_db()
    if active_only:
        return db.execute(
            'SELECT * FROM accounts WHERE is_active = 1 ORDER BY name'
        ).fetchall()
    return db.execute('SELECT * FROM accounts ORDER BY name').fetchall()


def get_account_by_id(account_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM accounts WHERE id = ?', (account_id,)
    ).fetchone()


def get_account_by_ccu_id(ccu_account_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM accounts WHERE account_id = ?', (ccu_account_id,)
    ).fetchone()


def create_account(name, account_id, description=''):
    db = get_db()
    db.execute(
        'INSERT INTO accounts (name, account_id, description) VALUES (?, ?, ?)',
        (name, account_id, description)
    )
    db.commit()


def update_account(id, name, description, is_active):
    db = get_db()
    db.execute(
        'UPDATE accounts SET name = ?, description = ?, is_active = ? WHERE id = ?',
        (name, description, is_active, id)
    )
    db.commit()


# ── Categories ────────────────────────────────────────────

def get_categories(type_filter=None):
    db = get_db()
    if type_filter:
        return db.execute(
            'SELECT * FROM categories WHERE type = ? ORDER BY name',
            (type_filter,)
        ).fetchall()
    return db.execute('SELECT * FROM categories ORDER BY type, name').fetchall()


def get_category_by_id(category_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM categories WHERE id = ?', (category_id,)
    ).fetchone()


def create_category(name, type, schedule_c_line=None, deductible_pct=1.0):
    db = get_db()
    db.execute(
        'INSERT INTO categories (name, type, schedule_c_line, deductible_pct) VALUES (?, ?, ?, ?)',
        (name, type, schedule_c_line, deductible_pct)
    )
    db.commit()


def update_category(id, name, type, schedule_c_line=None, deductible_pct=1.0):
    db = get_db()
    db.execute(
        'UPDATE categories SET name = ?, type = ?, schedule_c_line = ?, deductible_pct = ? WHERE id = ?',
        (name, type, schedule_c_line, deductible_pct, id)
    )
    db.commit()


def delete_category(id):
    db = get_db()
    # Unlink transactions first
    db.execute('UPDATE transactions SET category_id = NULL WHERE category_id = ?', (id,))
    db.execute('DELETE FROM categorization_rules WHERE category_id = ?', (id,))
    db.execute('DELETE FROM categories WHERE id = ?', (id,))
    db.commit()


# ── Transactions ──────────────────────────────────────────

def get_transactions(account_id=None, category_id=None, uncategorized=False,
                     start_date=None, end_date=None, search=None,
                     limit=100, offset=0):
    db = get_db()
    query = """
        SELECT t.*, a.name as account_name, c.name as category_name, i.invoice_number as linked_invoice, i.id as linked_invoice_id
        FROM transactions t
        JOIN accounts a ON t.account_id = a.id
        LEFT JOIN categories c ON t.category_id = c.id
        LEFT JOIN invoices i ON t.id = i.matched_transaction_id
        WHERE 1=1
    """
    params = []

    if account_id:
        query += ' AND t.account_id = ?'
        params.append(account_id)
    if category_id:
        query += ' AND t.category_id = ?'
        params.append(category_id)
    if uncategorized:
        query += ' AND t.category_id IS NULL AND t.is_transfer = 0'
    if start_date:
        query += ' AND t.date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND t.date <= ?'
        params.append(end_date)
    if search:
        query += ' AND (t.description LIKE ? OR t.notes LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    query += ' ORDER BY t.date DESC, t.id DESC LIMIT ? OFFSET ?'
    params.extend([limit, offset])

    return db.execute(query, params).fetchall()


def get_transaction_count(account_id=None, category_id=None, uncategorized=False,
                          start_date=None, end_date=None, search=None):
    db = get_db()
    query = 'SELECT COUNT(*) FROM transactions t WHERE 1=1'
    params = []

    if account_id:
        query += ' AND t.account_id = ?'
        params.append(account_id)
    if category_id:
        query += ' AND t.category_id = ?'
        params.append(category_id)
    if uncategorized:
        query += ' AND t.category_id IS NULL AND t.is_transfer = 0'
    if start_date:
        query += ' AND t.date >= ?'
        params.append(start_date)
    if end_date:
        query += ' AND t.date <= ?'
        params.append(end_date)
    if search:
        query += ' AND (t.description LIKE ? OR t.notes LIKE ?)'
        params.extend([f'%{search}%', f'%{search}%'])

    return db.execute(query, params).fetchone()[0]


def get_transaction_by_id(id):
    db = get_db()
    return db.execute(
        """SELECT t.*, a.name as account_name, c.name as category_name
           FROM transactions t
           JOIN accounts a ON t.account_id = a.id
           LEFT JOIN categories c ON t.category_id = c.id
           WHERE t.id = ?""",
        (id,)
    ).fetchone()


def create_transaction(account_id, transaction_id, date, description,
                       amount, balance=None, category_id=None,
                       is_transfer=False, notes=None, source='manual'):
    db = get_db()
    db.execute(
        """INSERT OR IGNORE INTO transactions
           (account_id, transaction_id, date, description, amount, balance,
            category_id, is_transfer, notes, source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (account_id, transaction_id, date, description, amount, balance,
         category_id, int(is_transfer), notes, source)
    )
    db.commit()


def update_transaction_category(id, category_id):
    db = get_db()
    old = db.execute('SELECT category_id FROM transactions WHERE id = ?', (id,)).fetchone()
    old_val = str(old['category_id']) if old and old['category_id'] else None
    new_val = str(category_id) if category_id else None
    db.execute(
        'UPDATE transactions SET category_id = ? WHERE id = ?',
        (category_id, id)
    )
    if old_val != new_val:
        log_change('category_change', transaction_id=id, field='category_id',
                   old_value=old_val, new_value=new_val)
    db.commit()


def bulk_update_category(transaction_ids, category_id):
    db = get_db()
    # Log each change
    for tid in transaction_ids:
        old = db.execute('SELECT category_id FROM transactions WHERE id = ?', (tid,)).fetchone()
        old_val = str(old['category_id']) if old and old['category_id'] else None
        log_change('bulk_categorize', transaction_id=tid, field='category_id',
                   old_value=old_val, new_value=str(category_id),
                   detail=f'Bulk action on {len(transaction_ids)} transactions')
    placeholders = ','.join('?' for _ in transaction_ids)
    db.execute(
        f'UPDATE transactions SET category_id = ? WHERE id IN ({placeholders})',
        [category_id] + list(transaction_ids)
    )
    db.commit()


def update_transaction_notes(id, notes):
    db = get_db()
    old = db.execute('SELECT notes FROM transactions WHERE id = ?', (id,)).fetchone()
    old_val = old['notes'] if old else None
    db.execute(
        'UPDATE transactions SET notes = ? WHERE id = ?',
        (notes, id)
    )
    if old_val != notes:
        log_change('note_edit', transaction_id=id, field='notes',
                   old_value=old_val, new_value=notes)
    db.commit()


# ── Categorization Rules ─────────────────────────────────

def get_rules():
    db = get_db()
    return db.execute(
        """SELECT r.*, c.name as category_name
           FROM categorization_rules r
           JOIN categories c ON r.category_id = c.id
           ORDER BY r.priority DESC, r.keyword""",
    ).fetchall()


def create_rule(keyword, category_id, priority=10):
    db = get_db()
    db.execute(
        'INSERT INTO categorization_rules (keyword, category_id, priority) VALUES (?, ?, ?)',
        (keyword, category_id, priority)
    )
    db.commit()


def update_rule(id, keyword, category_id, priority):
    db = get_db()
    db.execute(
        'UPDATE categorization_rules SET keyword = ?, category_id = ?, priority = ? WHERE id = ?',
        (keyword, category_id, priority, id)
    )
    db.commit()


def delete_rule(id):
    db = get_db()
    db.execute('DELETE FROM categorization_rules WHERE id = ?', (id,))
    db.commit()


# ── Clients ───────────────────────────────────────────────

def get_clients():
    db = get_db()
    return db.execute('SELECT * FROM clients ORDER BY name').fetchall()


def get_client_by_id(id):
    db = get_db()
    return db.execute('SELECT * FROM clients WHERE id = ?', (id,)).fetchone()


def create_client(name, address='', email=''):
    db = get_db()
    cursor = db.execute(
        'INSERT INTO clients (name, address, email) VALUES (?, ?, ?)',
        (name, address, email)
    )
    db.commit()
    return cursor.lastrowid


def update_client(id, name, address, email):
    db = get_db()
    db.execute(
        'UPDATE clients SET name = ?, address = ?, email = ? WHERE id = ?',
        (name, address, email, id)
    )
    db.commit()


# ── Invoices ──────────────────────────────────────────────

def get_next_invoice_number():
    db = get_db()
    row = db.execute('SELECT MAX(invoice_number) FROM invoices').fetchone()
    if row[0] is None:
        bconfig = get_business_config()
        return int(bconfig.get('invoice_start_number', 1001))
    return row[0] + 1


def get_invoices(status=None):
    db = get_db()
    query = """
        SELECT i.*, c.name as client_name,
               COALESCE(SUM(li.amount), 0) as total
        FROM invoices i
        JOIN clients c ON i.client_id = c.id
        LEFT JOIN invoice_line_items li ON li.invoice_id = i.id
    """
    params = []
    if status:
        query += ' WHERE i.status = ?'
        params.append(status)
    query += ' GROUP BY i.id ORDER BY i.date DESC'
    return db.execute(query, params).fetchall()


def get_invoice_by_id(id):
    db = get_db()
    invoice = db.execute(
        """SELECT i.*, c.name as client_name, c.address as client_address,
                  c.email as client_email
           FROM invoices i
           JOIN clients c ON i.client_id = c.id
           WHERE i.id = ?""",
        (id,)
    ).fetchone()
    return invoice


def get_invoice_line_items(invoice_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM invoice_line_items WHERE invoice_id = ? ORDER BY sort_order',
        (invoice_id,)
    ).fetchall()


def create_invoice(invoice_number, client_id, date, due_date, terms, notes=''):
    db = get_db()
    cursor = db.execute(
        """INSERT INTO invoices (invoice_number, client_id, date, due_date, terms, notes)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (invoice_number, client_id, date, due_date, terms, notes)
    )
    db.commit()
    return cursor.lastrowid


def add_invoice_line_item(invoice_id, description, quantity, rate, sort_order=0):
    db = get_db()
    amount = round(quantity * rate, 2)
    db.execute(
        """INSERT INTO invoice_line_items
           (invoice_id, description, quantity, rate, amount, sort_order)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (invoice_id, description, quantity, rate, amount, sort_order)
    )
    db.commit()


def update_invoice_status(id, status):
    db = get_db()
    db.execute('UPDATE invoices SET status = ? WHERE id = ?', (status, id))
    db.commit()


def update_invoice(id, client_id, date, due_date, terms, notes=''):
    db = get_db()
    db.execute(
        """UPDATE invoices SET client_id = ?, date = ?, due_date = ?, terms = ?, notes = ?
           WHERE id = ?""",
        (client_id, date, due_date, terms, notes, id)
    )
    db.commit()


def delete_invoice_line_items(invoice_id):
    db = get_db()
    db.execute('DELETE FROM invoice_line_items WHERE invoice_id = ?', (invoice_id,))
    db.commit()


def delete_invoice(id):
    db = get_db()
    db.execute('DELETE FROM invoice_line_items WHERE invoice_id = ?', (id,))
    db.execute('DELETE FROM invoices WHERE id = ?', (id,))
    db.commit()


# ── Summary / Dashboard ──────────────────────────────────

def get_ytd_income(year):
    db = get_db()
    row = db.execute(
        """SELECT COALESCE(SUM(t.amount), 0)
           FROM transactions t
           JOIN categories c ON t.category_id = c.id
           WHERE c.type = 'income' AND strftime('%Y', t.date) = ?""",
        (str(year),)
    ).fetchone()
    return row[0]


def get_ytd_expenses(year):
    db = get_db()
    row = db.execute(
        """SELECT COALESCE(SUM(ABS(t.amount)), 0)
           FROM transactions t
           JOIN categories c ON t.category_id = c.id
           WHERE c.type = 'expense' AND strftime('%Y', t.date) = ?""",
        (str(year),)
    ).fetchone()
    return row[0]


def get_uncategorized_count():
    db = get_db()
    row = db.execute(
        'SELECT COUNT(*) FROM transactions WHERE category_id IS NULL AND is_transfer = 0'
    ).fetchone()
    return row[0]


def get_outstanding_invoice_count():
    db = get_db()
    row = db.execute(
        "SELECT COUNT(*) FROM invoices WHERE status IN ('draft', 'sent')"
    ).fetchone()
    return row[0]


# ── Audit Log ─────────────────────────────────────────────

def log_change(action, transaction_id=None, field=None, old_value=None,
               new_value=None, detail=None):
    from datetime import datetime
    db = get_db()
    db.execute(
        """INSERT INTO audit_log (timestamp, action, transaction_id, field_name,
           old_value, new_value, detail) VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (datetime.now().strftime('%Y-%m-%d %H:%M:%S'), action, transaction_id,
         field, old_value, new_value, detail)
    )
    db.commit()


def get_audit_log(limit=100, offset=0):
    db = get_db()
    return db.execute(
        """SELECT al.*, t.description as txn_description
           FROM audit_log al
           LEFT JOIN transactions t ON al.transaction_id = t.id
           ORDER BY al.timestamp DESC LIMIT ? OFFSET ?""",
        (limit, offset)
    ).fetchall()


def get_audit_log_count():
    db = get_db()
    return db.execute('SELECT COUNT(*) FROM audit_log').fetchone()[0]


def get_transaction_history(transaction_id):
    db = get_db()
    return db.execute(
        'SELECT * FROM audit_log WHERE transaction_id = ? ORDER BY timestamp DESC',
        (transaction_id,)
    ).fetchall()


# ── Year Lock ─────────────────────────────────────────────

def is_year_locked(year):
    db = get_db()
    row = db.execute('SELECT 1 FROM locked_years WHERE year = ?', (int(year),)).fetchone()
    return row is not None


def get_locked_years():
    db = get_db()
    return db.execute('SELECT * FROM locked_years ORDER BY year DESC').fetchall()


def lock_year(year):
    db = get_db()
    db.execute('INSERT OR IGNORE INTO locked_years (year) VALUES (?)', (int(year),))
    db.commit()


def unlock_year(year):
    db = get_db()
    db.execute('DELETE FROM locked_years WHERE year = ?', (int(year),))
    db.commit()


# ── Owners (QJV) ─────────────────────────────────────────

def get_owners():
    db = get_db()
    return db.execute('SELECT * FROM owners ORDER BY is_primary DESC, id').fetchall()


def get_owner_by_id(id):
    db = get_db()
    return db.execute('SELECT * FROM owners WHERE id = ?', (id,)).fetchone()


def create_owner(name, ssn_last4=None, is_primary=False):
    db = get_db()
    db.execute(
        'INSERT INTO owners (name, ssn_last4, is_primary) VALUES (?, ?, ?)',
        (name, ssn_last4, int(is_primary))
    )
    db.commit()


def update_owner(id, name, ssn_last4=None):
    db = get_db()
    db.execute(
        'UPDATE owners SET name = ?, ssn_last4 = ? WHERE id = ?',
        (name, ssn_last4, id)
    )
    db.commit()


# ── Tax Payments ──────────────────────────────────────────

def get_tax_payments(year):
    db = get_db()
    return db.execute(
        'SELECT * FROM tax_payments WHERE year = ? ORDER BY date',
        (year,)
    ).fetchall()


def get_tax_payments_by_quarter(year, quarter):
    db = get_db()
    return db.execute(
        'SELECT * FROM tax_payments WHERE year = ? AND quarter = ? ORDER BY date',
        (year, quarter)
    ).fetchall()


def get_tax_payment_totals(year):
    """Get total paid per jurisdiction for a year."""
    db = get_db()
    rows = db.execute(
        """SELECT jurisdiction, SUM(amount) as total
           FROM tax_payments WHERE year = ?
           GROUP BY jurisdiction""",
        (year,)
    ).fetchall()
    return {row['jurisdiction']: row['total'] for row in rows}


def get_tax_payment_totals_by_quarter(year):
    """Get total paid per jurisdiction per quarter."""
    db = get_db()
    rows = db.execute(
        """SELECT jurisdiction, quarter, SUM(amount) as total
           FROM tax_payments WHERE year = ?
           GROUP BY jurisdiction, quarter""",
        (year,)
    ).fetchall()
    result = {}
    for row in rows:
        key = (row['jurisdiction'], row['quarter'])
        result[key] = row['total']
    return result


def create_tax_payment(date, amount, jurisdiction, quarter, year,
                       confirmation_number=None, receipt_file=None, notes=None):
    db = get_db()
    db.execute(
        """INSERT INTO tax_payments
           (date, amount, jurisdiction, quarter, year, confirmation_number, receipt_file, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (date, amount, jurisdiction, quarter, year, confirmation_number, receipt_file, notes)
    )
    db.commit()


def delete_tax_payment(id):
    db = get_db()
    db.execute('DELETE FROM tax_payments WHERE id = ?', (id,))
    db.commit()


# ── Tax Config ────────────────────────────────────────────

def get_tax_config(year):
    db = get_db()
    row = db.execute('SELECT * FROM tax_config WHERE year = ?', (year,)).fetchone()
    if row:
        return dict(row)
    return {
        'year': year,
        'prior_year_federal': 0, 'prior_year_state': 0, 'prior_year_city': 0,
        'agi_over_150k': 0, 'include_expenses': 1,
        'quarterly_federal': 0, 'quarterly_state': 0, 'quarterly_city': 0,
        'dependents': 0,
    }


def save_tax_config(year, **kwargs):
    db = get_db()
    existing = db.execute('SELECT 1 FROM tax_config WHERE year = ?', (year,)).fetchone()
    if existing:
        sets = ', '.join(f'{k} = ?' for k in kwargs)
        vals = list(kwargs.values()) + [year]
        db.execute(f'UPDATE tax_config SET {sets} WHERE year = ?', vals)
    else:
        kwargs['year'] = year
        cols = ', '.join(kwargs.keys())
        placeholders = ', '.join('?' for _ in kwargs)
        db.execute(f'INSERT INTO tax_config ({cols}) VALUES ({placeholders})',
                   list(kwargs.values()))
    db.commit()


# ── Tax Due Dates ─────────────────────────────────────────

def get_quarterly_due_dates(year):
    """Return due dates for each quarter, bumped to next Monday if weekend."""
    from datetime import date, timedelta
    raw_dates = {
        'Q1': date(year, 4, 15),
        'Q2': date(year, 6, 15),
        'Q3': date(year, 9, 15),
        'Q4': date(year + 1, 1, 15),
    }
    due_dates = {}
    for q, d in raw_dates.items():
        while d.weekday() >= 5:  # Saturday or Sunday
            d += timedelta(days=1)
        due_dates[q] = d
    return due_dates


# ── Health Insurance ──────────────────────────────────────

def get_health_insurance(year):
    """Get all health insurance records for a year, ordered by month."""
    db = get_db()
    return db.execute('SELECT * FROM health_insurance WHERE year = ? ORDER BY month', (year,)).fetchall()

def save_health_insurance(year, month, premium, advance_ptc=0, notes=None):
    """Save or update a health insurance record for a specific year and month."""
    db = get_db()
    db.execute('''
        INSERT INTO health_insurance (year, month, premium, advance_ptc, notes)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(year, month) DO UPDATE SET
            premium=excluded.premium,
            advance_ptc=excluded.advance_ptc,
            notes=excluded.notes
    ''', (year, month, premium, advance_ptc, notes))
    db.commit()

def get_health_insurance_totals(year):
    """Get total premiums, PTC, and deductible amount (premium - PTC) for a year."""
    db = get_db()
    row = db.execute('''
        SELECT SUM(premium) as total_premium, SUM(advance_ptc) as total_ptc
        FROM health_insurance
        WHERE year = ?
    ''', (year,)).fetchone()
    
    total_premium = row['total_premium'] or 0
    total_ptc = row['total_ptc'] or 0
    return {
        'total_premium': total_premium,
        'total_ptc': total_ptc,
        'deductible': max(0, total_premium - total_ptc)
    }

# ── Contractors (1099) ────────────────────────────────────

def get_all_contractors():
    """Get all contractors, ordered by name."""
    db = get_db()
    return db.execute('SELECT * FROM contractors ORDER BY name COLLATE NOCASE').fetchall()

def get_contractor(id):
    """Get a specific contractor by ID."""
    db = get_db()
    return db.execute('SELECT * FROM contractors WHERE id = ?', (id,)).fetchone()

def save_contractor(name, address='', ein_ssn_last4='', w9_received=0, notes='', id=None):
    """Create or update a contractor."""
    db = get_db()
    if id:
        db.execute('''
            UPDATE contractors 
            SET name=?, address=?, ein_ssn_last4=?, w9_received=?, notes=?
            WHERE id=?
        ''', (name, address, ein_ssn_last4, w9_received, notes, id))
    else:
        db.execute('''
            INSERT INTO contractors (name, address, ein_ssn_last4, w9_received, notes)
            VALUES (?, ?, ?, ?, ?)
        ''', (name, address, ein_ssn_last4, w9_received, notes))
    db.commit()

def delete_contractor(id):
    """Delete a contractor and un-link any of their transactions."""
    db = get_db()
    # Un-link transactions first
    db.execute('UPDATE transactions SET contractor_id = NULL WHERE contractor_id = ?', (id,))
    # Delete contractor
    db.execute('DELETE FROM contractors WHERE id = ?', (id,))
    db.commit()

def get_contractor_ytd_payments(contractor_id, year):
    """Calculate the total payments to a specific contractor for a given year."""
    db = get_db()
    row = db.execute('''
        SELECT SUM(amount) as total
        FROM transactions
        WHERE contractor_id = ? AND strftime('%Y', date) = ?
    ''', (contractor_id, str(year))).fetchone()
    total = row['total'] if row['total'] else 0.0
    return abs(total)

def update_transaction_contractor(transaction_id, contractor_id):
    """Link or unlink a transaction to a contractor."""
    db = get_db()
    db.execute('UPDATE transactions SET contractor_id = ? WHERE id = ?', (contractor_id, transaction_id))
    db.commit()

def update_transaction_receipt(transaction_id, filename):
    """Attach a physical receipt filename to a transaction."""
    db = get_db()
    db.execute('UPDATE transactions SET receipt_file = ? WHERE id = ?', (filename, transaction_id))
    db.commit()


# ── Business Config ──

def get_business_config():
    """Get all business config as a dict with defaults."""
    db = get_db()
    rows = db.execute('SELECT key, value FROM business_config').fetchall()
    config = {row['key']: row['value'] for row in rows}
    # Merge with defaults
    defaults = {
        'business_name': 'My Business LLC',
        'business_type': 'sole_prop',
        'address_line1': '',
        'address_line2': '',
        'email': '',
        'phone': '',
        'invoice_terms': 'Net 15',
        'invoice_start_number': '1001',
        'services': 'Consulting,Services',
    }
    for k, v in defaults.items():
        if k not in config:
            config[k] = v
    return config

def set_business_config(key, value):
    """Set a single business config value."""
    db = get_db()
    db.execute(
        'INSERT INTO business_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?',
        (key, value, value)
    )
    db.commit()

def set_business_config_bulk(data):
    """Set multiple business config values at once."""
    db = get_db()
    for key, value in data.items():
        db.execute(
            'INSERT INTO business_config (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = ?',
            (key, value, value)
        )
    db.commit()


# ── Tax Jurisdictions ──

def get_tax_jurisdictions():
    """Get all tax jurisdictions."""
    db = get_db()
    rows = db.execute('SELECT * FROM tax_jurisdictions ORDER BY id').fetchall()
    if not rows:
        # Seed defaults on first access
        _seed_default_jurisdictions(db)
        rows = db.execute('SELECT * FROM tax_jurisdictions ORDER BY id').fetchall()
    return rows

def get_tax_jurisdiction(jid):
    """Get a single jurisdiction by ID."""
    db = get_db()
    return db.execute('SELECT * FROM tax_jurisdictions WHERE id = ?', (jid,)).fetchone()

def save_tax_jurisdiction(jid, name, tax_rate, exemption_per_person, pay_url, enabled):
    """Create or update a tax jurisdiction."""
    db = get_db()
    db.execute('''
        INSERT INTO tax_jurisdictions (id, name, tax_rate, exemption_per_person, pay_url, enabled)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(id) DO UPDATE SET
            name=?, tax_rate=?, exemption_per_person=?, pay_url=?, enabled=?
    ''', (jid, name, tax_rate, exemption_per_person, pay_url, enabled,
          name, tax_rate, exemption_per_person, pay_url, enabled))
    db.commit()

def delete_tax_jurisdiction(jid):
    """Delete a tax jurisdiction (cannot delete 'federal')."""
    if jid == 'federal':
        return
    db = get_db()
    db.execute('DELETE FROM tax_jurisdictions WHERE id = ?', (jid,))
    db.commit()

def _seed_default_jurisdictions(db):
    """Seed default federal/state/city jurisdictions."""
    defaults = [
        ('federal', 'Federal', 0, 0, 'https://www.irs.gov/payments', 1),
        ('state', 'State', 0.0425, 5600, '', 1),
        ('city', 'City', 0, 0, '', 0),
    ]
    for jid, name, rate, exemption, url, enabled in defaults:
        db.execute('''
            INSERT OR IGNORE INTO tax_jurisdictions (id, name, tax_rate, exemption_per_person, pay_url, enabled)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (jid, name, rate, exemption, url, enabled))
    db.commit()

