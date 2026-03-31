"""Import routes — CSV upload and processing."""
from flask import Blueprint, render_template, request, flash, redirect, url_for
from .. import models
from ..importers import IMPORTERS
from ..categorize import categorize_transaction, categorize_transfers

import_bp = Blueprint('import', __name__, url_prefix='/import')


@import_bp.route('/')
def index():
    accounts = models.get_accounts()
    return render_template('import.html', results=None, importers=IMPORTERS, accounts=accounts)


@import_bp.route('/upload', methods=['POST'])
def upload():
    file = request.files.get('csv_file')
    if not file or not file.filename.endswith('.csv'):
        flash('Please upload a CSV file.', 'error')
        return redirect(url_for('import.index'))

    importer_id = request.form.get('importer_id')
    if not importer_id or importer_id not in IMPORTERS:
        flash('Invalid bank format selected.', 'error')
        return redirect(url_for('import.index'))
        
    target_account_id = request.form.get('target_account_id')

    importer = IMPORTERS[importer_id]

    try:
        content = file.read().decode('utf-8')
        parsed = importer['parse_function'](content)
    except Exception as e:
        flash(f'Error reading CSV format ({importer["name"]}): {e}', 'error')
        return redirect(url_for('import.index'))

    # Find or create account
    account = None
    
    # 1. Fallback prioritizing explicit target_account_id
    if target_account_id and target_account_id != 'auto':
        account = models.get_account_by_id(target_account_id)
        
    # 2. Try the parser's auto-detected account ID
    elif parsed.get('account_id'):
        account = models.get_account_by_ccu_id(parsed['account_id'])
    
    if not account:
        if parsed.get('account_id'):
            flash(f"Unknown matched account ID: {parsed['account_id']}. Please select an explicit target account or add the CCU ID in Settings first.", 'error')
        elif not target_account_id or target_account_id == 'auto':
            flash(f"This bank format does not auto-detect the account. Please explicitly select the target account.", 'error')
        else:
             flash(f"Unknown matching account error.", 'error')
        return redirect(url_for('import.index'))

    # Import transactions
    imported = 0
    skipped = 0
    categorized = 0
    errors = []

    for txn in parsed.get('transactions', []):
        if not txn.get('transaction_id'):
            errors.append(f"Row missing transaction ID: {txn.get('description', 'Unknown')}")
            continue

        # Auto-categorize
        category_id = None
        if txn.get('is_transfer', False):
            from ..database import get_db
            db = get_db()
            transfer_cat = db.execute(
                "SELECT id FROM categories WHERE name = 'Transfer'"
            ).fetchone()
            if transfer_cat:
                category_id = transfer_cat['id']
        else:
            category_id = categorize_transaction(txn.get('description', ''))

        from ..database import get_db as _get_db
        db = _get_db()
        cursor = db.execute(
            """INSERT OR IGNORE INTO transactions
               (account_id, transaction_id, date, description, amount, balance,
                category_id, is_transfer, notes, source)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (account['id'], txn['transaction_id'], txn['date'],
             txn['description'], txn['amount'], txn.get('balance'),
             category_id, int(txn.get('is_transfer', False)), None, importer_id)
        )
        db.commit()
        if cursor.rowcount > 0:
            imported += 1
            if category_id:
                categorized += 1
        else:
            skipped += 1

    # Check actual import count
    results = {
        'account_name': account['name'],
        'total': len(parsed.get('transactions', [])),
        'imported': imported,
        'skipped': skipped,
        'categorized': categorized,
        'errors': errors,
    }

    if imported > 0:
        flash(f'Imported {imported} transactions into {account["name"]}.', 'success')
    if skipped > 0:
        flash(f'Skipped {skipped} duplicate transactions.', 'info')

    accounts = models.get_accounts()
    return render_template('import.html', results=results, importers=IMPORTERS, accounts=accounts)
