"""Import routes — CSV upload and processing."""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from .. import models
from ..import_ccu import parse_ccu_csv
from ..categorize import categorize_transaction, categorize_transfers

import_bp = Blueprint('import', __name__, url_prefix='/import')


@import_bp.route('/')
def index():
    return render_template('import.html', results=None)


@import_bp.route('/upload-ccu', methods=['POST'])
def upload_ccu():
    file = request.files.get('csv_file')
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a CSV file.', 'error')
        return redirect(url_for('import.index'))

    try:
        content = file.read().decode('utf-8')
        parsed = parse_ccu_csv(content)
    except Exception as e:
        flash(f'Error reading CSV: {e}', 'error')
        return redirect(url_for('import.index'))

    # Find or create account
    account = models.get_account_by_ccu_id(parsed['account_id'])
    if not account:
        flash(f"Unknown account ID: {parsed['account_id']}. Add it in Settings first.", 'error')
        return redirect(url_for('import.index'))

    # Import transactions
    imported = 0
    skipped = 0
    categorized = 0
    errors = []

    for txn in parsed['transactions']:
        if not txn['transaction_id']:
            errors.append(f"Row missing transaction ID: {txn['description']}")
            continue

        # Auto-categorize
        category_id = None
        if txn['is_transfer']:
            from ..database import get_db
            db = get_db()
            transfer_cat = db.execute(
                "SELECT id FROM categories WHERE name = 'Transfer'"
            ).fetchone()
            if transfer_cat:
                category_id = transfer_cat['id']
        else:
            category_id = categorize_transaction(txn['description'])

        from ..database import get_db as _get_db
        db = _get_db()
        cursor = db.execute(
            """INSERT OR IGNORE INTO transactions
               (account_id, transaction_id, date, description, amount, balance,
                category_id, is_transfer, notes, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (account['id'], txn['transaction_id'], txn['date'],
             txn['description'], txn['amount'], txn['balance'],
             category_id, int(txn['is_transfer']), None, 'ccu_csv')
        )
        db.commit()
        if cursor.rowcount > 0:
            imported += 1
            if category_id:
                categorized += 1
        else:
            skipped += 1

    # Check actual import count (INSERT OR IGNORE means some may silently skip)
    results = {
        'account_name': account['name'],
        'total': len(parsed['transactions']),
        'imported': imported,
        'skipped': skipped,
        'categorized': categorized,
        'errors': errors,
    }

    if imported > 0:
        flash(f'Imported {imported} transactions from {account["name"]}.', 'success')
    if skipped > 0:
        flash(f'Skipped {skipped} duplicate transactions.', 'info')

    return render_template('import.html', results=results)
