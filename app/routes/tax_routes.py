"""Tax estimation routes — quarterly payments, due dates, config."""
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import models

tax_bp = Blueprint('taxes', __name__, url_prefix='/taxes')


def _get_jurisdictions_dict():
    """Build a jurisdictions dict from DB for template use."""
    rows = models.get_tax_jurisdictions()
    result = {}
    for row in rows:
        result[row['id']] = {
            'name': row['name'],
            'pay_url': row['pay_url'] or '',
            'tax_rate': row['tax_rate'],
            'exemption_per_person': row['exemption_per_person'],
            'enabled': row['enabled'],
        }
    return result


@tax_bp.route('/')
def dashboard():
    year = request.args.get('year', datetime.now().year, type=int)
    config = models.get_tax_config(year)
    due_dates = models.get_quarterly_due_dates(year)
    paid = models.get_tax_payment_totals(year)
    paid_by_q = models.get_tax_payment_totals_by_quarter(year)
    payments = models.get_tax_payments(year)
    jurisdictions = _get_jurisdictions_dict()

    state_j = jurisdictions.get('state', {})
    city_j = jurisdictions.get('city', {})
    state_enabled = state_j.get('enabled', 0)
    city_enabled = city_j.get('enabled', 0)

    # Build quarterly breakdown
    quarters = []
    for q_num in range(1, 5):
        q_key = f'Q{q_num}'
        due = due_dates[q_key]
        is_past = date.today() > due

        fed_target = config.get('quarterly_federal', 0)
        fed_paid = paid_by_q.get(('federal', q_key), 0)
        state_target = config.get('quarterly_state', 0)
        state_paid = paid_by_q.get(('state', q_key), 0)
        city_target = config.get('quarterly_city', 0)
        city_paid = paid_by_q.get(('city', q_key), 0)

        # Quarter is "done" if date is past OR all enabled jurisdictions are fully paid
        fed_ok = fed_paid >= fed_target if fed_target > 0 else True
        state_ok = (state_paid >= state_target if state_target > 0 else True) if state_enabled else True
        city_ok = (city_paid >= city_target if city_target > 0 else True) if city_enabled else True
        is_paid = fed_ok and state_ok and city_ok and (fed_target > 0 or state_target > 0 or city_target > 0)
        is_done = is_past or is_paid
        is_next = not is_done and (not quarters or quarters[-1].get('is_done', False))

        q_data = {
            'label': q_key,
            'due_date': due,
            'is_past': is_past,
            'is_paid': is_paid,
            'is_done': is_done,
            'is_next': is_next,
            'federal': {
                'target': fed_target,
                'paid': fed_paid,
            },
            'state': {
                'target': state_target,
                'paid': state_paid,
            },
            'city': {
                'target': city_target,
                'paid': city_paid,
            },
        }
        quarters.append(q_data)

    # YTD totals
    ytd = {
        'federal': paid.get('federal', 0),
        'state': paid.get('state', 0),
        'city': paid.get('city', 0),
    }
    annual_targets = {
        'federal': config.get('quarterly_federal', 0) * 4,
        'state': config.get('quarterly_state', 0) * 4,
        'city': config.get('quarterly_city', 0) * 4,
    }

    # ── Income-Based Projection ──
    from ..reports import get_tax_summary
    tax_summary = get_tax_summary(year)
    ytd_income = tax_summary['total_income']
    ytd_deductible_expenses = tax_summary['total_deductible_expenses']

    # Annualize based on how far into the year we are
    today = date.today()
    if today.year == year:
        day_of_year = (today - date(year, 1, 1)).days + 1
        days_in_year = 366 if (year % 4 == 0 and (year % 100 != 0 or year % 400 == 0)) else 365
        annualize_factor = days_in_year / max(day_of_year, 1)
    else:
        annualize_factor = 1.0

    projected_income = ytd_income * annualize_factor
    projected_expenses = ytd_deductible_expenses * annualize_factor
    projected_net = projected_income - projected_expenses - tax_summary['home_office_deduction']

    # Tax estimates on projected net
    se_taxable = projected_net * 0.9235
    projected_se_tax = max(se_taxable * 0.153, 0)
    se_deduction = projected_se_tax / 2
    taxable_after_se = projected_net - se_deduction

    # Federal Income Tax Calculation
    health_totals = models.get_health_insurance_totals(year)
    health_deduction_ytd = health_totals['deductible']
    projected_health_deduction = health_deduction_ytd * annualize_factor
    
    agi = taxable_after_se - projected_health_deduction
    standard_deduction = 30000
    qbi = max(projected_net - se_deduction, 0)
    qbi_deduction = qbi * 0.20
    federal_taxable = max(agi - standard_deduction - qbi_deduction, 0)

    dependents = config.get('dependents', 0)
    
    # Simplified progressive brackets — married filing jointly 2025/2026
    def federal_tax(income):
        brackets = [
            (23850, 0.10), (96950, 0.12), (206700, 0.22),
            (394600, 0.24), (501050, 0.32), (751600, 0.35), (float('inf'), 0.37),
        ]
        tax = 0
        prev = 0
        for limit, rate in brackets:
            if income <= prev:
                break
            taxable = min(income, limit) - prev
            tax += taxable * rate
            prev = limit
        return tax

    # Federal Tax: Income tax (minus Child Tax Credit) + SE tax
    child_tax_credit = dependents * 2000
    federal_income_tax_after_credits = max(federal_tax(federal_taxable) - child_tax_credit, 0)
    projected_federal = federal_income_tax_after_credits + projected_se_tax
    
    # State tax: flat rate with per-person exemptions
    state_rate = state_j.get('tax_rate', 0)
    state_exemption = state_j.get('exemption_per_person', 0)
    state_exemptions_total = (2 + dependents) * state_exemption
    state_taxable = max(agi - state_exemptions_total, 0)
    projected_state = state_taxable * state_rate if state_enabled else 0
    
    # City tax: flat rate with per-person exemptions
    city_rate = city_j.get('tax_rate', 0)
    city_exemption = city_j.get('exemption_per_person', 0)
    city_exemptions_total = (2 + dependents) * city_exemption
    city_taxable = max(agi - city_exemptions_total, 0)
    projected_city = city_taxable * city_rate if city_enabled else 0

    # Safe harbor
    from ..reports import get_pl_report_owner_adjusted as get_pl
    prior_year_pl = get_pl(f'{year-1}-01-01', f'{year-1}-12-31')
    prior_year_agi = prior_year_pl['total_income']
    prior_year_over_150k = prior_year_agi >= 150000
    safe_harbor_pct = 1.10 if prior_year_over_150k else 1.00
    safe_harbor = {
        'federal': config.get('prior_year_federal', 0) * safe_harbor_pct,
        'state': config.get('prior_year_state', 0) * safe_harbor_pct,
        'city': config.get('prior_year_city', 0) * safe_harbor_pct,
        'pct_label': '110%' if prior_year_over_150k else '100%',
        'prior_year_agi': prior_year_agi,
        'prior_year_over_150k': prior_year_over_150k,
    }

    on_track_150k = projected_income >= 150000

    def min_required(projected, sh):
        if sh > 0:
            return min(sh, projected * 0.9)
        return projected * 0.9

    recommended = {
        'federal': min_required(projected_federal, safe_harbor['federal']) / 4,
        'state': min_required(projected_state, safe_harbor['state']) / 4,
        'city': min_required(projected_city, safe_harbor['city']) / 4,
    }

    april_deficit = {
        'federal': max(0, projected_federal - (recommended['federal'] * 4)),
        'state': max(0, projected_state - (recommended['state'] * 4)),
        'city': max(0, projected_city - (recommended['city'] * 4)),
    }
    april_deficit['total'] = april_deficit['federal'] + april_deficit['state'] + april_deficit['city']

    projection = {
        'ytd_income': ytd_income,
        'projected_income': projected_income,
        'projected_net': projected_net,
        'projected_federal': projected_federal,
        'projected_state': projected_state,
        'projected_city': projected_city,
        'projected_se_tax': projected_se_tax,
        'annualize_factor': annualize_factor,
        'on_track_150k': on_track_150k,
        'agi': agi,
        'health_deduction': projected_health_deduction,
        'standard_deduction': standard_deduction,
        'qbi_deduction': qbi_deduction,
        'federal_taxable': federal_taxable,
        'child_tax_credit': child_tax_credit,
        'state_exemptions': state_exemptions_total,
        'state_taxable': state_taxable,
        'city_exemptions': city_exemptions_total,
        'city_taxable': city_taxable,
    }

    return render_template('taxes/dashboard.html',
        year=year, config=config, quarters=quarters,
        ytd=ytd, annual_targets=annual_targets,
        payments=payments, jurisdictions=jurisdictions,
        state_enabled=state_enabled, city_enabled=city_enabled,
        projection=projection, safe_harbor=safe_harbor,
        recommended=recommended, april_deficit=april_deficit)


@tax_bp.route('/config', methods=['POST'])
def save_config():
    year = request.form.get('year', type=int)
    models.save_tax_config(year,
        quarterly_federal=request.form.get('quarterly_federal', 0, type=float),
        quarterly_state=request.form.get('quarterly_state', 0, type=float),
        quarterly_city=request.form.get('quarterly_city', 0, type=float),
        prior_year_federal=request.form.get('prior_year_federal', 0, type=float),
        prior_year_state=request.form.get('prior_year_state', 0, type=float),
        prior_year_city=request.form.get('prior_year_city', 0, type=float),
        dependents=request.form.get('dependents', 0, type=int),
    )
    flash('Tax configuration saved.', 'success')
    return redirect(url_for('taxes.dashboard', year=year))


@tax_bp.route('/payment', methods=['POST'])
def add_payment():
    import os
    from werkzeug.utils import secure_filename
    year = request.form.get('year', type=int)

    # Handle receipt upload
    receipt_file = None
    uploaded = request.files.get('receipt')
    if uploaded and uploaded.filename:
        ext = uploaded.filename.rsplit('.', 1)[-1].lower()
        if ext in ('pdf', 'png', 'jpg', 'jpeg', 'webp'):
            ts = datetime.now().strftime('%Y%m%d%H%M%S')
            filename = f"{request.form.get('jurisdiction')}_{request.form.get('quarter')}_{year}_{ts}.{ext}"
            receipts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'receipts')
            os.makedirs(receipts_dir, exist_ok=True)
            uploaded.save(os.path.join(receipts_dir, filename))
            receipt_file = filename

    models.create_tax_payment(
        date=request.form.get('date'),
        amount=request.form.get('amount', type=float),
        jurisdiction=request.form.get('jurisdiction'),
        quarter=request.form.get('quarter'),
        year=year,
        confirmation_number=request.form.get('confirmation_number', '').strip() or None,
        receipt_file=receipt_file,
        notes=request.form.get('notes', '').strip() or None,
    )
    models.log_change('tax_payment',
        detail=f"Recorded ${request.form.get('amount')} {request.form.get('jurisdiction')} "
               f"payment for {request.form.get('quarter')} {year}")
    flash('Payment recorded.', 'success')
    return redirect(url_for('taxes.dashboard', year=year))


@tax_bp.route('/payment/<int:id>/delete', methods=['POST'])
def delete_payment(id):
    year = request.args.get('year', datetime.now().year, type=int)
    models.delete_tax_payment(id)
    flash('Payment deleted.', 'success')
    return redirect(url_for('taxes.dashboard', year=year))


@tax_bp.route('/receipt/<filename>')
def receipt(filename):
    import os
    from flask import send_from_directory
    receipts_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'data', 'receipts')
    return send_from_directory(receipts_dir, filename)
