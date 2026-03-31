"""Invoice routes — CRUD, PDF generation."""
from datetime import datetime, timedelta
from flask import Blueprint, render_template, request, flash, redirect, url_for, make_response
from .. import models

invoice_bp = Blueprint('invoices', __name__, url_prefix='/invoices')


def _get_services():
    """Get services list from business config DB."""
    bconfig = models.get_business_config()
    raw = bconfig.get('services', 'Consulting,Services')
    return [s.strip() for s in raw.split(',') if s.strip()]


def _get_business_info():
    """Get business info dict from DB config."""
    bconfig = models.get_business_config()
    return {
        'name': bconfig.get('business_name', 'My Business LLC'),
        'address_line1': bconfig.get('address_line1', ''),
        'address_line2': bconfig.get('address_line2', ''),
        'email': bconfig.get('email', ''),
        'phone': bconfig.get('phone', ''),
    }


@invoice_bp.route('/')
def index():
    status = request.args.get('status')
    invoices = models.get_invoices(status=status)
    return render_template('invoices.html', invoices=invoices)


@invoice_bp.route('/new', methods=['GET', 'POST'])
def create():
    if request.method == 'POST':
        client_id = request.form.get('client_id', type=int)
        date = request.form.get('date')
        terms = request.form.get('terms', 'Net 15')
        notes = request.form.get('notes', '')

        # Calculate due date from terms
        days = int(terms.replace('Net ', '')) if terms.startswith('Net ') else 15
        due_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=days)).strftime('%Y-%m-%d')

        invoice_number = models.get_next_invoice_number()
        invoice_id = models.create_invoice(
            invoice_number=invoice_number,
            client_id=client_id,
            date=date,
            due_date=due_date,
            terms=terms,
            notes=notes,
        )

        # Add line items
        descriptions = request.form.getlist('line_description')
        quantities = request.form.getlist('line_quantity')
        rates = request.form.getlist('line_rate')

        for i, (desc, qty, rate) in enumerate(zip(descriptions, quantities, rates)):
            if desc and qty and rate:
                models.add_invoice_line_item(
                    invoice_id=invoice_id,
                    description=desc,
                    quantity=float(qty),
                    rate=float(rate),
                    sort_order=i,
                )

        flash(f'Invoice #{invoice_number} created.', 'success')
        return redirect(url_for('invoices.view', id=invoice_id))

    return render_template('invoice_form.html',
        clients=models.get_clients(),
        services=_get_services(),
        next_number=models.get_next_invoice_number(),
        today=datetime.now().strftime('%Y-%m-%d'),
        edit_mode=False,
        invoice=None,
        line_items=[],
    )


@invoice_bp.route('/<int:id>')
def view(id):
    invoice = models.get_invoice_by_id(id)
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('invoices.index'))

    line_items = models.get_invoice_line_items(id)
    total = sum(item['amount'] for item in line_items)

    return render_template('invoice_view.html',
        invoice=invoice,
        line_items=line_items,
        total=total,
        business=_get_business_info(),
    )


@invoice_bp.route('/<int:id>/status', methods=['POST'])
def update_status(id):
    status = request.form.get('status')
    if status in ('draft', 'sent', 'paid'):
        models.update_invoice_status(id, status)
    return redirect(url_for('invoices.view', id=id))


@invoice_bp.route('/<int:id>/pdf')
def pdf(id):
    invoice = models.get_invoice_by_id(id)
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('invoices.index'))

    line_items = models.get_invoice_line_items(id)
    total = sum(item['amount'] for item in line_items)

    html = render_template('invoice_pdf.html',
        invoice=invoice,
        line_items=line_items,
        total=total,
        business=_get_business_info(),
    )

    try:
        from weasyprint import HTML
        pdf_bytes = HTML(string=html).write_pdf()
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = (
            f'inline; filename=invoice_{invoice["invoice_number"]}.pdf'
        )
        return response
    except ImportError:
        flash('PDF generation requires WeasyPrint. Install it with: pip install weasyprint', 'error')
        return redirect(url_for('invoices.view', id=id))


@invoice_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
def edit(id):
    invoice = models.get_invoice_by_id(id)
    if not invoice:
        flash('Invoice not found.', 'error')
        return redirect(url_for('invoices.index'))
    if invoice['status'] != 'draft':
        flash('Only draft invoices can be edited.', 'error')
        return redirect(url_for('invoices.view', id=id))

    if request.method == 'POST':
        client_id = request.form.get('client_id', type=int)
        date = request.form.get('date')
        terms = request.form.get('terms', 'Net 15')
        notes = request.form.get('notes', '')

        days = int(terms.replace('Net ', '')) if terms.startswith('Net ') else 15
        due_date = (datetime.strptime(date, '%Y-%m-%d') + timedelta(days=days)).strftime('%Y-%m-%d')

        models.update_invoice(id, client_id=client_id, date=date, due_date=due_date, terms=terms, notes=notes)

        # Replace line items
        models.delete_invoice_line_items(id)
        descriptions = request.form.getlist('line_description')
        quantities = request.form.getlist('line_quantity')
        rates = request.form.getlist('line_rate')
        for i, (desc, qty, rate) in enumerate(zip(descriptions, quantities, rates)):
            if desc and qty and rate:
                models.add_invoice_line_item(
                    invoice_id=id, description=desc,
                    quantity=float(qty), rate=float(rate), sort_order=i,
                )

        flash(f'Invoice #{invoice["invoice_number"]} updated.', 'success')
        return redirect(url_for('invoices.view', id=id))

    line_items = models.get_invoice_line_items(id)
    return render_template('invoice_form.html',
        invoice=invoice,
        line_items=line_items,
        clients=models.get_clients(),
        services=_get_services(),
        next_number=invoice['invoice_number'],
        today=invoice['date'],
        edit_mode=True,
    )


@invoice_bp.route('/<int:id>/delete', methods=['POST'])
def delete(id):
    models.delete_invoice(id)
    flash('Invoice deleted.', 'success')
    return redirect(url_for('invoices.index'))
