"""Settings routes — accounts, categories, rules, backup."""
import os
import io
from flask import Blueprint, render_template, request, flash, redirect, url_for, send_file, current_app
from .. import models
from ..categorize import auto_categorize_uncategorized, categorize_transfers

settings_bp = Blueprint('settings', __name__, url_prefix='/settings')


@settings_bp.route('/')
def index():
    bconfig = models.get_business_config()
    return render_template('settings/index.html', business_type=bconfig.get('business_type', 'sole_prop'))


# ── Categories ──

@settings_bp.route('/categories')
def categories():
    return render_template('settings/categories.html',
        categories=models.get_categories())


@settings_bp.route('/categories/create', methods=['POST'])
def create_category():
    name = request.form.get('name', '').strip()
    type_ = request.form.get('type', 'expense')
    schedule_c_line = request.form.get('schedule_c_line', '').strip() or None
    deductible_pct = request.form.get('deductible_pct', 100, type=float) / 100.0

    if name:
        try:
            models.create_category(name, type_, schedule_c_line, deductible_pct)
            flash(f'Category "{name}" created.', 'success')
        except Exception as e:
            flash(f'Error: {e}', 'error')
    return redirect(url_for('settings.categories'))


@settings_bp.route('/categories/<int:id>/update', methods=['POST'])
def update_category(id):
    name = request.form.get('name', '').strip()
    type_ = request.form.get('type', 'expense')
    schedule_c_line = request.form.get('schedule_c_line', '').strip() or None
    deductible_pct = request.form.get('deductible_pct', 100, type=float) / 100.0
    if name:
        models.update_category(id, name, type_, schedule_c_line, deductible_pct)
        flash('Category updated.', 'success')
    return redirect(url_for('settings.categories'))


@settings_bp.route('/categories/<int:id>/delete', methods=['POST'])
def delete_category(id):
    models.delete_category(id)
    flash('Category deleted.', 'success')
    return redirect(url_for('settings.categories'))


# ── Rules ──

@settings_bp.route('/rules')
def rules():
    return render_template('settings/rules.html',
        rules=models.get_rules(),
        categories=models.get_categories())


@settings_bp.route('/rules/create', methods=['POST'])
def create_rule():
    keyword = request.form.get('keyword', '').strip()
    category_id = request.form.get('category_id', type=int)
    priority = request.form.get('priority', 10, type=int)

    if keyword and category_id:
        models.create_rule(keyword, category_id, priority)
        flash(f'Rule "{keyword}" created.', 'success')
    return redirect(url_for('settings.rules'))


@settings_bp.route('/rules/<int:id>/delete', methods=['POST'])
def delete_rule(id):
    models.delete_rule(id)
    flash('Rule deleted.', 'success')
    return redirect(url_for('settings.rules'))


@settings_bp.route('/rules/auto-categorize', methods=['POST'])
def run_auto_categorize():
    count = auto_categorize_uncategorized()
    transfer_count = categorize_transfers()
    flash(f'Auto-categorized {count} transactions, {transfer_count} transfers.', 'success')
    return redirect(url_for('settings.rules'))


# ── Accounts ──

@settings_bp.route('/accounts')
def accounts():
    return render_template('settings/accounts.html',
        accounts=models.get_accounts(active_only=False))


@settings_bp.route('/accounts/create', methods=['POST'])
def create_account():
    name = request.form.get('name', '').strip()
    account_id = request.form.get('account_id', '').strip()
    description = request.form.get('description', '').strip()

    if name:
        models.create_account(name, account_id, description)
        flash(f'Account "{name}" created.', 'success')
    return redirect(url_for('settings.accounts'))


@settings_bp.route('/accounts/<int:id>/update', methods=['POST'])
def update_account(id):
    name = request.form.get('name', '').strip()
    description = request.form.get('description', '').strip()
    is_active = request.form.get('is_active') == '1'
    if name:
        models.update_account(id, name, description, int(is_active))
        flash('Account updated.', 'success')
    return redirect(url_for('settings.accounts'))


# ── Clients ──

@settings_bp.route('/clients')
def clients():
    return render_template('settings/clients.html',
        clients=models.get_clients())


@settings_bp.route('/clients/create', methods=['POST'])
def create_client():
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    email = request.form.get('email', '').strip()
    if name:
        models.create_client(name, address, email)
        flash(f'Client "{name}" created.', 'success')
    return redirect(url_for('settings.clients'))


@settings_bp.route('/clients/<int:id>/update', methods=['POST'])
def update_client(id):
    name = request.form.get('name', '').strip()
    address = request.form.get('address', '').strip()
    email = request.form.get('email', '').strip()
    if name:
        models.update_client(id, name, address, email)
        flash('Client updated.', 'success')
    return redirect(url_for('settings.clients'))


# ── Business Profile ──

@settings_bp.route('/business')
def business_profile():
    config = models.get_business_config()
    return render_template('settings/business.html', config=config)

@settings_bp.route('/business/save', methods=['POST'])
def save_business_profile():
    data = {
        'business_name': request.form.get('business_name', '').strip(),
        'business_type': request.form.get('business_type', 'sole_prop').strip(),
        'address_line1': request.form.get('address_line1', '').strip(),
        'address_line2': request.form.get('address_line2', '').strip(),
        'email': request.form.get('email', '').strip(),
        'phone': request.form.get('phone', '').strip(),
        'invoice_terms': request.form.get('invoice_terms', '').strip(),
        'invoice_start_number': request.form.get('invoice_start_number', '1001').strip(),
        'services': request.form.get('services', '').strip(),
    }
    models.set_business_config_bulk(data)
    models.log_change('business_profile', detail='Updated business profile')
    flash('Business profile saved.', 'success')
    return redirect(url_for('settings.business_profile'))


# ── Tax Jurisdictions ──

@settings_bp.route('/tax-setup')
def tax_setup():
    jurisdictions = models.get_tax_jurisdictions()
    return render_template('settings/tax_setup.html', jurisdictions=jurisdictions)

@settings_bp.route('/tax-setup/save', methods=['POST'])
def save_tax_jurisdiction():
    jid = request.form.get('id', '').strip()
    name = request.form.get('name', '').strip()
    tax_rate = request.form.get('tax_rate', 0, type=float) / 100.0  # Convert % to decimal
    exemption = request.form.get('exemption_per_person', 0, type=float)
    pay_url = request.form.get('pay_url', '').strip()
    enabled = 1 if request.form.get('enabled') == '1' else 0

    if jid == 'federal':
        # Only save the payment URL for federal
        j = models.get_tax_jurisdiction('federal')
        models.save_tax_jurisdiction('federal', j['name'], j['tax_rate'], j['exemption_per_person'], pay_url, 1)
    elif jid:
        if enabled:
            if name:
                models.save_tax_jurisdiction(jid, name, tax_rate, exemption, pay_url, 1)
        else:
            # Disable and erase data to reset the jurisdiction
            fallback_name = "State" if jid == "state" else "City"
            models.save_tax_jurisdiction(jid, fallback_name, 0, 0, "", 0)

    models.log_change('tax_jurisdiction', detail=f'Updated jurisdiction: {name or jid}')
    flash(f'Tax jurisdiction updated.', 'success')
    return redirect(url_for('settings.tax_setup'))


# ── Owners (QJV) ──

@settings_bp.route('/owners')
def owners():
    return render_template('settings/owners.html',
        owners=models.get_owners())


@settings_bp.route('/owners/create', methods=['POST'])
def create_owner():
    name = request.form.get('name', '').strip()
    ssn_last4 = request.form.get('ssn_last4', '').strip() or None
    existing = models.get_owners()
    is_primary = len(existing) == 0  # First owner is primary
    if name and len(existing) < 2:
        models.create_owner(name, ssn_last4, is_primary)
        flash(f'Owner "{name}" added.', 'success')
    return redirect(url_for('settings.owners'))


@settings_bp.route('/owners/<int:id>/update', methods=['POST'])
def update_owner(id):
    name = request.form.get('name', '').strip()
    ssn_last4 = request.form.get('ssn_last4', '').strip() or None
    if name:
        models.update_owner(id, name, ssn_last4)
        flash('Owner updated.', 'success')
    return redirect(url_for('settings.owners'))


# ── Backup ──

@settings_bp.route('/backup')
def backup():
    return render_template('settings/backup.html')


@settings_bp.route('/year-lock')
def year_lock():
    from ..database import get_db
    db = get_db()
    # Get all years that have transactions
    year_rows = db.execute(
        "SELECT DISTINCT strftime('%Y', date) as year FROM transactions ORDER BY year DESC"
    ).fetchall()
    locked = {row['year'] for row in models.get_locked_years()}
    years = []
    for row in year_rows:
        y = row['year']
        lock_info = None
        if int(y) in locked:
            lock_info = db.execute(
                'SELECT locked_at FROM locked_years WHERE year = ?', (int(y),)
            ).fetchone()
        years.append({
            'year': y,
            'locked': int(y) in locked,
            'locked_at': lock_info['locked_at'] if lock_info else None,
        })
    return render_template('settings/year_lock.html', years=years)


@settings_bp.route('/year-lock/toggle', methods=['POST'])
def toggle_year_lock():
    year = request.form.get('year', type=int)
    action = request.form.get('action')
    if year and action == 'lock':
        models.lock_year(year)
        models.log_change('year_lock', detail=f'Locked year {year}')
        flash(f'Year {year} locked.', 'success')
    elif year and action == 'unlock':
        models.unlock_year(year)
        models.log_change('year_unlock', detail=f'Unlocked year {year}')
        flash(f'Year {year} unlocked.', 'success')
    return redirect(url_for('settings.year_lock'))


@settings_bp.route('/activity-log')
def activity_log():
    page = request.args.get('page', 1, type=int)
    limit = 100
    offset = (page - 1) * limit
    entries = models.get_audit_log(limit=limit, offset=offset)
    total = models.get_audit_log_count()
    # Build category ID → name map for display
    categories = models.get_categories()
    category_map = {cat['id']: cat['name'] for cat in categories}
    return render_template('settings/activity_log.html',
        entries=entries, total=total, category_map=category_map)


@settings_bp.route('/backup/download')
def download_backup():
    import zipfile
    import io
    db_path = current_app.config['DATABASE']
    data_dir = os.path.dirname(db_path)
    receipts_dir = os.path.join(data_dir, 'receipts')
    
    if not os.path.exists(db_path):
        flash('Database file not found.', 'error')
        return redirect(url_for('settings.backup'))
        
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        zf.write(db_path, arcname=os.path.basename(db_path))
        if os.path.exists(receipts_dir):
            for root, dirs, files in os.walk(receipts_dir):
                for f in files:
                    file_path = os.path.join(root, f)
                    arcname = f"receipts/{f}"
                    zf.write(file_path, arcname=arcname)
                    
    memory_file.seek(0)
    return send_file(memory_file,
        as_attachment=True,
        download_name='big-tech-accounting-backup.zip',
        mimetype='application/zip')


@settings_bp.route('/backup/restore', methods=['POST'])
def restore_backup():
    """Replace the current database and receipts with an uploaded backup."""
    import sqlite3 as sqlite3_mod
    import tempfile
    import zipfile
    import shutil
    from ..database import close_db

    file = request.files.get('backup_file')
    if not file or not file.filename:
        flash('No file selected.', 'error')
        return redirect(url_for('settings.backup'))

    is_zip = file.filename.endswith('.zip')
    
    try:
        if is_zip:
            with zipfile.ZipFile(file) as zf:
                db_filename = next((name for name in zf.namelist() if name.endswith('.db') and '/' not in name), None)
                if not db_filename:
                    flash('Invalid ZIP backup — no database file found at root.', 'error')
                    return redirect(url_for('settings.backup'))
                db_data = zf.read(db_filename)
        else:
            db_data = file.read()
            
        if not db_data.startswith(b'SQLite format 3'):
            flash('Invalid file — not a SQLite database.', 'error')
            return redirect(url_for('settings.backup'))

        # Validate it has the expected tables
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp:
            tmp.write(db_data)
            tmp_path = tmp.name
        conn = sqlite3_mod.connect(tmp_path)
        tables = {row[0] for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()}
        conn.close()
        os.unlink(tmp_path)

        required = {'accounts', 'categories', 'transactions'}
        if not required.issubset(tables):
            flash(f'Invalid backup — missing tables: {required - tables}', 'error')
            return redirect(url_for('settings.backup'))

        # Validation passed. Now perform destructive replace:
        close_db()
        db_path = current_app.config['DATABASE']
        data_dir = os.path.dirname(db_path)
        
        with open(db_path, 'wb') as f:
            f.write(db_data)
            
        # If ZIP, also replace receipts
        if is_zip:
            receipts_dir = os.path.join(data_dir, 'receipts')
            if os.path.exists(receipts_dir):
                shutil.rmtree(receipts_dir)
            os.makedirs(receipts_dir, exist_ok=True)
            
            # Reset file pointer to reread zip
            file.seek(0)
            with zipfile.ZipFile(file) as zf:
                for item in zf.namelist():
                    if item.startswith('receipts/') and not item.endswith('/'):
                        filename = os.path.basename(item)
                        if filename:
                            extracted_path = os.path.join(receipts_dir, filename)
                            with open(extracted_path, 'wb') as out_f:
                                out_f.write(zf.read(item))
                                
        flash('Full backup restored successfully. Page will reload.', 'success')
        
        # Re-run schema + migrations to ensure restored DB has all current columns
        from ..database import init_db
        init_db(current_app)
        
    except Exception as e:
        flash(f'Failed to restore backup: {e}', 'error')
        
    return redirect(url_for('settings.backup'))


@settings_bp.route('/backup/wipe', methods=['POST'])
def wipe_database():
    """Delete the database and start fresh."""
    from ..database import close_db, init_db

    close_db()
    db_path = current_app.config['DATABASE']
    if os.path.exists(db_path):
        os.remove(db_path)
    init_db(current_app)

    flash('Database wiped. Fresh database created with default categories and rules.', 'success')
    return redirect(url_for('settings.backup'))
