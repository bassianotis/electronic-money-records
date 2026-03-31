"""Report routes."""
from datetime import datetime
from flask import Blueprint, render_template, request
from ..reports import get_pl_report, get_pl_report_owner_adjusted, get_category_detail, get_tax_summary
from .. import models

report_bp = Blueprint('reports', __name__, url_prefix='/reports')


@report_bp.route('/')
def index():
    return render_template('reports/index.html')


@report_bp.route('/pl')
def pl():
    year = request.args.get('year', datetime.now().year, type=int)
    quarter = request.args.get('quarter', type=int)
    owner = request.args.get('owner')  # 'primary', 'spouse', or None

    if quarter:
        month_start = (quarter - 1) * 3 + 1
        month_end = quarter * 3
        start_date = f'{year}-{month_start:02d}-01'
        if month_end == 12:
            end_date = f'{year}-12-31'
        else:
            end_date = f'{year}-{month_end + 1:02d}-01'
            # Adjust to last day of quarter
            from datetime import date, timedelta
            end_date = (date(year, month_end + 1, 1) - timedelta(days=1)).isoformat()
        period_label = f'Q{quarter} {year}'
    else:
        start_date = f'{year}-01-01'
        end_date = f'{year}-12-31'
        period_label = str(year)

    report = get_pl_report_owner_adjusted(start_date, end_date, owner=owner)
    report['period_label'] = period_label

    owners = models.get_owners()
    locked = models.is_year_locked(year)

    return render_template('reports/pl.html',
        report=report,
        year=year,
        quarter=quarter,
        owner=owner,
        owners=owners,
        locked=locked,
    )


@report_bp.route('/category/<int:category_id>')
def category_detail(category_id):
    year = request.args.get('year', datetime.now().year, type=int)
    start_date = request.args.get('start_date', f'{year}-01-01')
    end_date = request.args.get('end_date', f'{year}-12-31')

    detail = get_category_detail(category_id, start_date, end_date)
    return render_template('reports/category_detail.html',
        detail=detail,
        start_date=start_date,
        end_date=end_date,
    )


@report_bp.route('/schedule-c')
def schedule_c():
    from ..reports import get_schedule_c_report
    year = request.args.get('year', datetime.now().year, type=int)
    owner = request.args.get('owner', 'primary')
    
    report = get_schedule_c_report(year, owner)
    owners_list = models.get_owners()
    
    owner_name = "Primary Owner"
    for o in owners_list:
        if owner == 'primary' and o['is_primary']:
            owner_name = o['name']
        elif owner == 'spouse' and not o['is_primary']:
            owner_name = o['name']
            
    return render_template('reports/schedule_c.html',
        report=report,
        year=year,
        owner=owner,
        owner_name=owner_name,
        owners=owners_list
    )

@report_bp.route('/multi-year')
def multi_year():
    from ..reports import get_multi_year_report
    year_current = request.args.get('year_current', datetime.now().year, type=int)
    year_prior = request.args.get('year_prior', year_current - 1, type=int)
    owner = request.args.get('owner')
    
    report = get_multi_year_report(year_current, year_prior, owner)
    owners = models.get_owners()
    
    return render_template('reports/multi_year.html',
        report=report,
        year_current=year_current,
        year_prior=year_prior,
        owner=owner,
        owners=owners
    )
