"""Dashboard routes."""
from datetime import datetime
from flask import Blueprint, render_template
from .. import models

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    year = datetime.now().year
    return render_template('dashboard.html',
        year=year,
        ytd_income=models.get_ytd_income(year),
        ytd_expenses=models.get_ytd_expenses(year),
        uncategorized=models.get_uncategorized_count(),
        outstanding_invoices=models.get_outstanding_invoice_count(),
    )
