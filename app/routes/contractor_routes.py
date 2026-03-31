from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_from_directory
from datetime import date
from werkzeug.utils import secure_filename
import os
from .. import models

contractor_bp = Blueprint('contractors', __name__, url_prefix='/contractors')

@contractor_bp.route('/')
def index():
    year = request.args.get('year', date.today().year, type=int)
    raw_contractors = models.get_all_contractors()
    
    # Calculate YTD payments and 1099 flag
    contractors = []
    for c in raw_contractors:
        c_dict = dict(c)
        c_dict['ytd_payments'] = models.get_contractor_ytd_payments(c['id'], year)
        # Flag if over $600 IRS threshold
        c_dict['needs_1099'] = c_dict['ytd_payments'] >= 600.0
        contractors.append(c_dict)
        
    return render_template('contractors/index.html', contractors=contractors, year=year)

@contractor_bp.route('/save', methods=['POST'])
def save():
    try:
        id_val = request.form.get('id')
        contractor_id = int(id_val) if id_val else None
        
        name = request.form.get('name', '').strip()
        address = request.form.get('address', '').strip()
        ein_ssn_last4 = request.form.get('ein_ssn_last4', '').strip()
        notes = request.form.get('notes', '').strip()
        
        if not name:
            flash("Contractor name is required.", "error")
            return redirect(url_for('contractors.index'))
        
        # Preserve w9_received during updates
        w9_received = 0
        if contractor_id:
            existing = models.get_contractor(contractor_id)
            if existing:
                w9_received = existing['w9_received']
            
        models.save_contractor(name, address, ein_ssn_last4, w9_received, notes, contractor_id)
        
        if contractor_id:
            models.log_change('contractor', detail=f"Updated contractor: {name}")
        else:
            models.log_change('contractor', detail=f"Added new contractor: {name}")
            flash(f"Added contractor: {name}", "success")
            
    except Exception as e:
        flash(f"Error saving contractor: {str(e)}", "error")
        
    return redirect(url_for('contractors.index'))

@contractor_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    contractor = models.get_contractor(id)
    if contractor:
        models.delete_contractor(id)
        models.log_change('contractor', detail=f"Deleted contractor: {contractor['name']}")
        flash(f"Deleted contractor: {contractor['name']}", "success")
    return redirect(url_for('contractors.index'))

@contractor_bp.route('/<int:id>/w9', methods=['POST'])
def upload_w9(id):
    if 'w9_file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(url_for('contractors.index'))
    file = request.files['w9_file']
    if file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('contractors.index'))
    if file:
        filename = secure_filename(file.filename)
        w9_dir = os.path.join(current_app.root_path, '..', 'data', 'w9s')
        os.makedirs(w9_dir, exist_ok=True)
        file.save(os.path.join(w9_dir, filename))
        
        db = models.get_db()
        db.execute('UPDATE contractors SET w9_file = ?, w9_received = 1 WHERE id = ?', (filename, id))
        db.commit()
        models.log_change('contractor', detail=f"Uploaded W-9 for contractor #{id}")
        flash('W-9 uploaded successfully', 'success')
    return redirect(url_for('contractors.index'))

@contractor_bp.route('/<int:id>/w9', methods=['DELETE'])
def delete_w9(id):
    db = models.get_db()
    c = db.execute('SELECT w9_file FROM contractors WHERE id = ?', (id,)).fetchone()
    if c and c['w9_file']:
        w9_dir = os.path.join(current_app.root_path, '..', 'data', 'w9s')
        file_path = os.path.join(w9_dir, c['w9_file'])
        if os.path.exists(file_path):
            os.remove(file_path)
        db.execute('UPDATE contractors SET w9_file = NULL, w9_received = 0 WHERE id = ?', (id,))
        db.commit()
        models.log_change('contractor', detail=f"Deleted W-9 for contractor #{id}")
    return '', 204

@contractor_bp.route('/w9/<path:filename>')
def view_w9(filename):
    """Securely serve uploaded W-9 PDFs."""
    w9_dir = os.path.join(current_app.root_path, '..', 'data', 'w9s')
    return send_from_directory(w9_dir, filename)
