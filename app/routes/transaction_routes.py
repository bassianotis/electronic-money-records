"""Transaction routes — list, filter, categorize."""
from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from .. import models

transaction_bp = Blueprint('transactions', __name__, url_prefix='/transactions')


@transaction_bp.route('/')
def index():
    # Parse filters
    account_id = request.args.get('account_id', type=int)
    category_id = request.args.get('category_id', type=int)
    uncategorized = request.args.get('uncategorized') == '1'
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search = request.args.get('search', '')
    page = request.args.get('page', 1, type=int)
    limit = 100
    offset = (page - 1) * limit

    transactions = models.get_transactions(
        account_id=account_id,
        category_id=category_id,
        uncategorized=uncategorized,
        start_date=start_date or None,
        end_date=end_date or None,
        search=search or None,
        limit=limit,
        offset=offset,
    )

    total = models.get_transaction_count(
        account_id=account_id,
        category_id=category_id,
        uncategorized=uncategorized,
        start_date=start_date or None,
        end_date=end_date or None,
        search=search or None,
    )

    db = models.get_db()
    open_invoices_raw = db.execute("""
        SELECT i.id, i.invoice_number, 
               (SELECT SUM(amount) FROM invoice_line_items WHERE invoice_id = i.id) as total_amount
        FROM invoices i 
        WHERE i.status = 'sent' AND i.matched_transaction_id IS NULL
    """).fetchall()
    open_invoices = [{'id': r['id'], 'invoice_number': r['invoice_number'], 'total_amount': r['total_amount'] or 0.0} for r in open_invoices_raw]

    # Auto-detect Bank Transfers via Self-Join
    txn_ids = [t['id'] for t in transactions]
    transfer_matches = {}
    if txn_ids:
        placeholders = ','.join('?' for _ in txn_ids)
        query = f"""
            SELECT t1.id as out_id, t2.id as in_id, t2.date as in_date, a2.name as in_account
            FROM transactions t1
            JOIN transactions t2 
              ON abs(t1.amount) = abs(t2.amount)
              AND (t1.amount * t2.amount) < 0
              AND t1.account_id != t2.account_id
              AND abs(julianday(t1.date) - julianday(t2.date)) <= 4
            JOIN accounts a2 ON t2.account_id = a2.id
            WHERE t1.linked_transfer_id IS NULL 
              AND t2.linked_transfer_id IS NULL
              AND t1.id IN ({placeholders})
        """
        pairs = db.execute(query, txn_ids).fetchall()
        for p in pairs:
            # We map the currently viewed txn_id to its highest probability match
            transfer_matches[p['out_id']] = {
                'id': p['in_id'],
                'date': p['in_date'],
                'account': p['in_account']
            }

    return render_template('transactions.html',
        transactions=transactions,
        total=total,
        accounts=models.get_accounts(),
        categories=models.get_categories(),
        contractors=models.get_all_contractors(),
        open_invoices=open_invoices,
        transfer_matches=transfer_matches,
        locked_years={r['year'] for r in models.get_locked_years()}
    )


@transaction_bp.route('/<int:id>/category', methods=['POST'])
def update_category(id):
    """HTMX endpoint: update a single transaction's category."""
    txn = models.get_transaction_by_id(id)
    if txn and models.is_year_locked(txn['date'][:4]):
        return 'Year is locked', 403
    category_id = request.form.get('category_id', type=int)
    models.update_transaction_category(id, category_id if category_id else None)
    return '', 204


@transaction_bp.route('/bulk-categorize', methods=['POST'])
def bulk_categorize():
    """Bulk assign category to multiple transactions."""
    transaction_ids = request.form.getlist('transaction_ids', type=int)
    category_id = request.form.get('category_id', type=int)

    if not transaction_ids or not category_id:
        flash('Select transactions and a category.', 'error')
        return redirect(url_for('transactions.index'))

    models.bulk_update_category(transaction_ids, category_id)
    flash(f'Categorized {len(transaction_ids)} transactions.', 'success')
    return redirect(url_for('transactions.index'))


@transaction_bp.route('/<int:id>/notes', methods=['POST'])
def update_notes(id):
    """HTMX endpoint: update transaction notes."""
    txn = models.get_transaction_by_id(id)
    if txn and models.is_year_locked(txn['date'][:4]):
        return 'Year is locked', 403
    notes = request.form.get('notes', '')
    models.update_transaction_notes(id, notes)
    return '', 204

@transaction_bp.route('/<int:id>/contractor', methods=['POST'])
def update_contractor(id):
    """HTMX endpoint: assign a contractor to a transaction."""
    txn = models.get_transaction_by_id(id)
    if txn and models.is_year_locked(txn['date'][:4]):
        return 'Year is locked', 403
    
    contractor_id = request.form.get('contractor_id')
    # If empty string, pass None to clear the contractor
    if not contractor_id:
        contractor_id = None
    else:
        contractor_id = int(contractor_id)
        
    models.update_transaction_contractor(id, contractor_id)
    return '', 204

import os
from werkzeug.utils import secure_filename
from flask import send_from_directory, current_app

@transaction_bp.route('/<int:id>/receipt', methods=['POST'])
def upload_receipt(id):
    """Endpoint for asynchronous file upload from the main grid inline."""
    txn = models.get_transaction_by_id(id)
    if not txn:
        return 'Transaction not found', 404
    if models.is_year_locked(txn['date'][:4]):
        return 'Year is locked', 403

    if 'receipt' not in request.files:
        return 'No file part', 400
    file = request.files['receipt']
    if file.filename == '':
        return 'No selected file', 400

    if file:
        filename = secure_filename(file.filename)
        # Prefix with txn id to ensure uniqueness
        unique_filename = f"txn_{id}_{filename}"
        
        # Ensure receipts dir exists
        receipts_dir = os.path.join(current_app.root_path, '..', 'data', 'receipts')
        os.makedirs(receipts_dir, exist_ok=True)
        
        file_path = os.path.join(receipts_dir, unique_filename)
        file.save(file_path)
        
        models.update_transaction_receipt(id, unique_filename)
        return url_for('transactions.view_receipt', filename=unique_filename), 200

@transaction_bp.route('/<int:id>/receipt', methods=['DELETE'])
def delete_receipt(id):
    """Endpoint to remove an attached receipt from a transaction."""
    txn = models.get_transaction_by_id(id)
    if not txn:
        return 'Transaction not found', 404
    if models.is_year_locked(txn['date'][:4]):
        return 'Year is locked', 403

    if txn['receipt_file']:
        # Delete from disk
        receipts_dir = os.path.join(current_app.root_path, '..', 'data', 'receipts')
        file_path = os.path.join(receipts_dir, txn['receipt_file'])
        if os.path.exists(file_path):
            os.remove(file_path)
            
        # Remove from DB
        models.update_transaction_receipt(id, None)
        
    return '', 204

@transaction_bp.route('/receipt/<path:filename>')
def view_receipt(filename):
    """Securely serve uploaded receipt files."""
    receipts_dir = os.path.join(current_app.root_path, '..', 'data', 'receipts')
    return send_from_directory(receipts_dir, filename)

@transaction_bp.route('/reconcile', methods=['GET', 'POST'])
def reconcile():
    from ..database import get_db
    db = get_db()
    
    if request.method == 'POST':
        txn_ids = request.form.getlist('transaction_ids[]')
        account_id = request.form.get('account_id')
        statement_date = request.form.get('statement_date')
        
        if txn_ids:
            # Safely bind the IN clause
            placeholders = ','.join('?' for _ in txn_ids)
            db.execute(f"UPDATE transactions SET is_reconciled = 1 WHERE id IN ({placeholders})", txn_ids)
            
            # Add an audit log entry natively
            message = f"Reconciled {len(txn_ids)} transactions for account #{account_id} up to {statement_date}"
            db.execute(
                "INSERT INTO audit_log (action, detail) VALUES (?, ?)",
                ("Reconcile", message)
            )
            db.commit()
            
            flash(f'Successfully locked and reconciled {len(txn_ids)} transactions to the bank statement.', 'success')
            return redirect(url_for('transactions.reconcile'))
        else:
            flash('No transactions selected to reconcile.', 'error')
            return redirect(url_for('transactions.reconcile'))

    accounts = db.execute("SELECT * FROM accounts WHERE is_active = 1").fetchall()
    
    account_id = request.args.get('account_id', type=int)
    statement_date = request.args.get('statement_date')
    statement_balance = request.args.get('statement_balance', type=float)
    
    unreconciled_txns = []
    cleared_balance = 0.0
    
    if account_id and statement_date and statement_balance is not None:
        cleared_row = db.execute(
            """SELECT SUM(amount) as total FROM transactions 
               WHERE account_id = ? AND date <= ? AND is_reconciled = 1""",
            (account_id, statement_date)
        ).fetchone()
        cleared_balance = cleared_row['total'] or 0.0
        
        unreconciled_txns = db.execute(
            """SELECT t.*, c.name as category_name 
               FROM transactions t
               LEFT JOIN categories c ON t.category_id = c.id
               WHERE t.account_id = ? AND t.date <= ? AND t.is_reconciled = 0
               ORDER BY t.date ASC""",
            (account_id, statement_date)
        ).fetchall()
        
    return render_template('reconcile.html',
        accounts=accounts,
        account_id=account_id,
        statement_date=statement_date,
        statement_balance=statement_balance,
        unreconciled_txns=unreconciled_txns,
        cleared_balance=cleared_balance
    )

@transaction_bp.route('/<int:id>/match_invoice', methods=['POST'])
def match_invoice(id):
    invoice_id = request.form.get('invoice_id', type=int)
    if not invoice_id:
        flash('Invalid invoice selection.', 'error')
        return redirect(url_for('transactions.index'))
        
    from ..database import get_db
    db = get_db()
    
    # Verify invoice exists and is open
    inv = db.execute("SELECT * FROM invoices WHERE id = ? AND status = 'sent'", (invoice_id,)).fetchone()
    if not inv:
        flash('Invoice not found or not in sent status.', 'error')
        return redirect(url_for('transactions.index'))
        
    db.execute(
        "UPDATE invoices SET status = 'paid', matched_transaction_id = ? WHERE id = ?",
        (id, invoice_id)
    )
    # Lock an audit record confirming the resolution
    db.execute(
        "INSERT INTO audit_log (action, transaction_id, detail) VALUES (?, ?, ?)",
        ("Invoice Map", id, f"Mapped deposit securely to Invoice #{inv['invoice_number']}")
    )
    db.commit()
    
    flash(f"Success: Invoice #{inv['invoice_number']} is officially fully paid and mapped.", 'success')
    return redirect(url_for('transactions.index') + f'#txn-{id}')

@transaction_bp.route('/<int:id>/match_transfer', methods=['POST'])
def match_transfer(id):
    linked_id = request.form.get('linked_transfer_id', type=int)
    if not linked_id:
        flash('Invalid transfer selection.', 'error')
        return redirect(url_for('transactions.index'))
        
    from ..database import get_db
    db = get_db()
    
    # Verify both transactions exist
    t1 = db.execute("SELECT * FROM transactions WHERE id = ?", (id,)).fetchone()
    t2 = db.execute("SELECT * FROM transactions WHERE id = ?", (linked_id,)).fetchone()
    
    if not t1 or not t2:
        flash('One of the transactions could not be verified.', 'error')
        return redirect(url_for('transactions.index'))
        
    # Execute a two-way lock and aggressively override the category to 'Transfer'
    cat_row = db.execute("SELECT id FROM categories WHERE name='Transfer' LIMIT 1").fetchone()
    transfer_cat_id = cat_row['id'] if cat_row else None

    db.execute(
        "UPDATE transactions SET is_transfer = 1, linked_transfer_id = ?, category_id = ? WHERE id = ?",
        (linked_id, transfer_cat_id, id)
    )
    db.execute(
        "UPDATE transactions SET is_transfer = 1, linked_transfer_id = ?, category_id = ? WHERE id = ?",
        (id, transfer_cat_id, linked_id)
    )
    
    db.execute(
        "INSERT INTO audit_log (action, transaction_id, detail) VALUES (?, ?, ?)",
        ("Transfer Map", id, "Locked mathematical transfer pair across accounts.")
    )
    db.commit()
    
    flash("Internal bank transfers mapped and netted out securely.", 'success')
    return redirect(url_for('transactions.index') + f'#txn-{id}')
