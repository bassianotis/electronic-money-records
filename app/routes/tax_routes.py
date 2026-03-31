"""Tax estimation routes — quarterly payments, due dates, config."""
from datetime import datetime, date
from flask import Blueprint, render_template, request, redirect, url_for, flash
from .. import models

tax_bp = Blueprint('taxes', __name__, url_prefix='/taxes')

JURISDICTIONS = {
    'federal': {
        'name': 'Federal',
        'pay_url': 'https://www.irs.gov/payments/pay-personal-taxes-from-your-bank-account',
    },
    'michigan': {
        'name': 'Michigan',
        'pay_url': 'https://mitreasury-eservices.michigan.gov/CitizenPortal/_/',
    },
    'grand_rapids': {
        'name': 'Grand Rapids',
        'pay_url': 'https://michigan-grand-rapids.insourcetax.com/#/',
    },
}


@tax_bp.route('/')
def dashboard():
    year = request.args.get('year', datetime.now().year, type=int)
    config = models.get_tax_config(year)
    due_dates = models.get_quarterly_due_dates(year)
    paid = models.get_tax_payment_totals(year)
    paid_by_q = models.get_tax_payment_totals_by_quarter(year)
    payments = models.get_tax_payments(year)

    # Build quarterly breakdown
    quarters = []
    for q_num in range(1, 5):
        q_key = f'Q{q_num}'
        due = due_dates[q_key]
        is_past = date.today() > due
        is_next = not is_past and (not quarters or quarters[-1]['is_past'])

        q_data = {
            'label': q_key,
            'due_date': due,
            'is_past': is_past,
            'is_next': is_next,
            'federal': {
                'target': config.get('quarterly_federal', 0),
                'paid': paid_by_q.get(('federal', q_key), 0),
            },
            'michigan': {
                'target': config.get('quarterly_state', 0),
                'paid': paid_by_q.get(('michigan', q_key), 0),
            },
            'grand_rapids': {
                'target': config.get('quarterly_city', 0),
                'paid': paid_by_q.get(('grand_rapids', q_key), 0),
            },
        }
        quarters.append(q_data)

    # YTD totals
    ytd = {
        'federal': paid.get('federal', 0),
        'michigan': paid.get('michigan', 0),
        'grand_rapids': paid.get('grand_rapids', 0),
    }
    annual_targets = {
        'federal': config.get('quarterly_federal', 0) * 4,
        'michigan': config.get('quarterly_state', 0) * 4,
        'grand_rapids': config.get('quarterly_city', 0) * 4,
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
    # 1. Start with AGI (Net Income minus 1/2 SE Tax minus Health Insurance Deduction)
    health_totals = models.get_health_insurance_totals(year)
    health_deduction_ytd = health_totals['deductible']
    projected_health_deduction = health_deduction_ytd * annualize_factor
    
    agi = taxable_after_se - projected_health_deduction
    
    # 2. Subtract Standard Deduction (MFJ ~ $30,000 for 2025/2026)
    standard_deduction = 30000
    
    # 3. Subtract QBI Deduction (20% of QBI, limited to 20% of taxable income before QBI)
    qbi = max(projected_net - se_deduction, 0)
    qbi_deduction = qbi * 0.20
    
    # 4. Taxable Income
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
    
    # Michigan: 4.25% flat tax, minus $5,600 exemption per person (2 spouses + dependents)
    mi_exemptions = (2 + dependents) * 5600
    mi_taxable = max(agi - mi_exemptions, 0)
    projected_michigan = mi_taxable * 0.0425
    
    # Grand Rapids: 1.5% flat tax, minus $600 exemption per person
    gr_exemptions = (2 + dependents) * 600
    gr_taxable = max(agi - gr_exemptions, 0)
    projected_grand_rapids = gr_taxable * 0.015

    # Safe harbor — threshold based on PRIOR YEAR AGI, not current year
    from ..reports import get_pl_report_owner_adjusted as get_pl
    prior_year_pl = get_pl(f'{year-1}-01-01', f'{year-1}-12-31')
    prior_year_agi = prior_year_pl['total_income']
    prior_year_over_150k = prior_year_agi >= 150000
    safe_harbor_pct = 1.10 if prior_year_over_150k else 1.00
    safe_harbor = {
        'federal': config.get('prior_year_federal', 0) * safe_harbor_pct,
        'michigan': config.get('prior_year_state', 0) * safe_harbor_pct,
        'grand_rapids': config.get('prior_year_city', 0) * safe_harbor_pct,
        'pct_label': '110%' if prior_year_over_150k else '100%',
        'prior_year_agi': prior_year_agi,
        'prior_year_over_150k': prior_year_over_150k,
    }

    # Current year $150k flag (heads-up, not used for safe harbor calc)
    on_track_150k = projected_income >= 150000

    # Minimum to avoid penalties = lower of:
    #   (a) safe harbor (100% or 110% of prior year tax)
    #   (b) 90% of current year projected tax
    # If no prior year data, use 90% of projected as fallback
    def min_required(projected, sh):
        if sh > 0:
            return min(sh, projected * 0.9)
        return projected * 0.9

    recommended = {
        'federal': min_required(projected_federal, safe_harbor['federal']) / 4,
        'michigan': min_required(projected_michigan, safe_harbor['michigan']) / 4,
        'grand_rapids': min_required(projected_grand_rapids, safe_harbor['grand_rapids']) / 4,
    }

    april_deficit = {
        'federal': max(0, projected_federal - (recommended['federal'] * 4)),
        'michigan': max(0, projected_michigan - (recommended['michigan'] * 4)),
        'grand_rapids': max(0, projected_grand_rapids - (recommended['grand_rapids'] * 4)),
    }
    april_deficit['total'] = april_deficit['federal'] + april_deficit['michigan'] + april_deficit['grand_rapids']

    projection = {
        'ytd_income': ytd_income,
        'projected_income': projected_income,
        'projected_net': projected_net,
        'projected_federal': projected_federal,
        'projected_michigan': projected_michigan,
        'projected_grand_rapids': projected_grand_rapids,
        'projected_se_tax': projected_se_tax,
        'annualize_factor': annualize_factor,
        'on_track_150k': on_track_150k,
        'agi': agi,
        'health_deduction': projected_health_deduction,
        'standard_deduction': standard_deduction,
        'qbi_deduction': qbi_deduction,
        'federal_taxable': federal_taxable,
        'child_tax_credit': child_tax_credit,
        'mi_exemptions': mi_exemptions,
        'mi_taxable': mi_taxable,
        'gr_exemptions': gr_exemptions,
        'gr_taxable': gr_taxable,
    }

    return render_template('taxes/dashboard.html',
        year=year, config=config, quarters=quarters,
        ytd=ytd, annual_targets=annual_targets,
        payments=payments, jurisdictions=JURISDICTIONS,
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
