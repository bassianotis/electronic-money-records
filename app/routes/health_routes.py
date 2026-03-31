from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash

from .. import models

health_bp = Blueprint('health', __name__, url_prefix='/health')

@health_bp.route('/')
def index():
    year = request.args.get('year', datetime.now().year, type=int)
    records = models.get_health_insurance(year)
    
    # Pad records so there are exactly 12 months, filling in gaps
    months = [
        'January', 'February', 'March', 'April', 'May', 'June',
        'July', 'August', 'September', 'October', 'November', 'December'
    ]
    
    # Create dictionary of existing records
    existing = {r['month']: dict(r) for r in records}
    
    # Build complete list
    monthly_data = []
    for i, month_name in enumerate(months, start=1):
        if i in existing:
            monthly_data.append(existing[i])
        else:
            monthly_data.append({
                'month': i,
                'month_name': month_name,
                'premium': 0.0,
                'advance_ptc': 0.0,
                'notes': ''
            })
            
    totals = models.get_health_insurance_totals(year)
    
    return render_template('health/index.html', 
        year=year,
        months=months,
        monthly_data=monthly_data,
        totals=totals)

@health_bp.route('/save', methods=['POST'])
def save():
    year = request.form.get('year', type=int)
    month = request.form.get('month', type=int)
    premium = request.form.get('premium', 0, type=float)
    notes = request.form.get('notes', '').strip()
    
    models.save_health_insurance(year, month, premium, 0, notes)
    
    models.log_change('health_insurance', 
        detail=f"Updated {year}-{month:02d} health insurance: ${premium:,.2f} premium")
    
    flash(f'Health insurance for month {month} saved.', 'success')
    return redirect(url_for('health.index', year=year))
