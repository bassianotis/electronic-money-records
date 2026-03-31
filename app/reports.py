"""Report generation — P&L, category detail, tax summary."""
from .database import get_db
from . import models


def get_pl_report(start_date, end_date, owner=None):
    """Generate Profit & Loss report for a date range.

    Args:
        owner: 'primary', 'spouse', or None (combined).
              Applies owner_split multiplier to amounts.

    Returns:
        dict with income_items, expense_items, total_income, total_expenses, net_income
    """
    db = get_db()
    split = _get_split_multiplier(owner)

    # Income by category
    income_items = db.execute(
        """SELECT c.id as category_id, c.name, c.schedule_c_line,
           SUM(t.amount * COALESCE(t.owner_split, 0.5) * ?) as total
           FROM transactions t
           JOIN categories c ON t.category_id = c.id
           WHERE c.type = 'income' AND t.date >= ? AND t.date <= ?
           GROUP BY c.id ORDER BY total DESC""",
        (split, start_date, end_date)
    ).fetchall()

    # Expenses by category
    expense_items = db.execute(
        """SELECT c.id as category_id, c.name, c.schedule_c_line,
           COALESCE(c.deductible_pct, 1.0) as deductible_pct,
           SUM(ABS(t.amount) * COALESCE(t.owner_split, 0.5) * ?) as total
           FROM transactions t
           JOIN categories c ON t.category_id = c.id
           WHERE c.type = 'expense' AND t.date >= ? AND t.date <= ?
           GROUP BY c.id ORDER BY total DESC""",
        (split, start_date, end_date)
    ).fetchall()

    total_income = sum(row['total'] for row in income_items)
    total_expenses = sum(row['total'] for row in expense_items)

    return {
        'start_date': start_date,
        'end_date': end_date,
        'income_items': income_items,
        'expense_items': expense_items,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_income': total_income - total_expenses,
        'owner': owner,
    }


def _get_split_multiplier(owner):
    """Return SQL multiplier for owner filtering.

    For 'primary': multiply by owner_split (e.g. 0.5)
    For 'spouse': multiply by (1 - owner_split)
    For None (combined): multiply by 1.0 (full amount)
    """
    if owner == 'primary':
        return 1.0  # SQL already uses owner_split
    elif owner == 'spouse':
        return 1.0  # SQL already uses (1 - owner_split)
    return 2.0  # Cancel out the 0.5 split to get full amount


def get_pl_report_owner_adjusted(start_date, end_date, owner=None):
    """Generate P&L with proper owner split math."""
    db = get_db()

    if owner == 'primary':
        income_sql = "SUM(t.amount * COALESCE(t.owner_split, 0.5))"
        expense_sql = "SUM(ABS(t.amount) * COALESCE(t.owner_split, 0.5))"
    elif owner == 'spouse':
        income_sql = "SUM(t.amount * (1.0 - COALESCE(t.owner_split, 0.5)))"
        expense_sql = "SUM(ABS(t.amount) * (1.0 - COALESCE(t.owner_split, 0.5)))"
    else:
        income_sql = "SUM(t.amount)"
        expense_sql = "SUM(ABS(t.amount))"

    income_items = db.execute(
        f"""SELECT c.id as category_id, c.name, c.schedule_c_line,
           {income_sql} as total
           FROM transactions t
           JOIN categories c ON t.category_id = c.id
           WHERE c.type = 'income' AND t.date >= ? AND t.date <= ?
           GROUP BY c.id ORDER BY total DESC""",
        (start_date, end_date)
    ).fetchall()

    expense_items = db.execute(
        f"""SELECT c.id as category_id, c.name, c.schedule_c_line,
           COALESCE(c.deductible_pct, 1.0) as deductible_pct,
           {expense_sql} as total
           FROM transactions t
           JOIN categories c ON t.category_id = c.id
           WHERE c.type = 'expense' AND t.date >= ? AND t.date <= ?
           GROUP BY c.id ORDER BY total DESC""",
        (start_date, end_date)
    ).fetchall()

    total_income = sum(row['total'] for row in income_items)
    total_expenses = sum(row['total'] for row in expense_items)

    return {
        'start_date': start_date,
        'end_date': end_date,
        'income_items': income_items,
        'expense_items': expense_items,
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_income': total_income - total_expenses,
        'owner': owner,
    }


def get_category_detail(category_id, start_date, end_date):
    """Get all transactions for a specific category in a date range."""
    db = get_db()

    category = db.execute(
        'SELECT * FROM categories WHERE id = ?', (category_id,)
    ).fetchone()

    transactions = db.execute(
        """SELECT t.*, a.name as account_name
           FROM transactions t
           JOIN accounts a ON t.account_id = a.id
           WHERE t.category_id = ? AND t.date >= ? AND t.date <= ?
           ORDER BY t.date DESC""",
        (category_id, start_date, end_date)
    ).fetchall()

    total = sum(abs(t['amount']) for t in transactions)

    return {
        'category': category,
        'transactions': transactions,
        'total': total,
        'count': len(transactions),
    }


def get_tax_summary(year, owner=None):
    """Generate tax summary for a year.

    Applies deductible_pct to each expense category.
    """
    start_date = f'{year}-01-01'
    end_date = f'{year}-12-31'

    pl = get_pl_report_owner_adjusted(start_date, end_date, owner=owner)

    # Build expense items with deductible amounts
    expense_details = []
    total_deductible_expenses = 0
    for item in pl['expense_items']:
        pct = item['deductible_pct'] if item['deductible_pct'] is not None else 1.0
        deductible = item['total'] * pct
        expense_details.append({
            'name': item['name'],
            'schedule_c_line': item['schedule_c_line'],
            'gross': item['total'],
            'deductible_pct': pct,
            'deductible': deductible,
        })
        total_deductible_expenses += deductible

    # Home office: $750 per owner (half of $1,500), or $1,500 combined
    if owner:
        home_office_deduction = 750.00
    else:
        home_office_deduction = 1500.00

    total_deductions = total_deductible_expenses + home_office_deduction
    taxable_income = pl['total_income'] - total_deductions

    # SE tax estimate
    se_taxable = taxable_income * 0.9235
    se_tax = se_taxable * 0.153 if se_taxable > 0 else 0
    se_deduction = se_tax / 2

    return {
        'year': year,
        'owner': owner,
        'total_income': pl['total_income'],
        'total_gross_expenses': pl['total_expenses'],
        'total_deductible_expenses': total_deductible_expenses,
        'home_office_deduction': home_office_deduction,
        'total_deductions': total_deductions,
        'taxable_income': taxable_income,
        'se_tax': se_tax,
        'se_deduction': se_deduction,
        'expense_items': expense_details,
    }

def get_schedule_c_report(year, owner='primary'):
    """Generate Schedule C output for a specific owner."""
    db = get_db()
    
    if owner == 'primary':
        income_sql = "SUM(t.amount * COALESCE(t.owner_split, 0.5))"
        expense_sql = "SUM(ABS(t.amount) * COALESCE(t.owner_split, 0.5) * COALESCE(c.deductible_pct, 1.0))"
    elif owner == 'spouse':
        income_sql = "SUM(t.amount * (1.0 - COALESCE(t.owner_split, 0.5)))"
        expense_sql = "SUM(ABS(t.amount) * (1.0 - COALESCE(t.owner_split, 0.5)) * COALESCE(c.deductible_pct, 1.0))"
    else:
        income_sql = "SUM(t.amount)"
        expense_sql = "SUM(ABS(t.amount) * COALESCE(c.deductible_pct, 1.0))"

    start_date = f'{year}-01-01'
    end_date = f'{year}-12-31'

    # Gross Receipts (Line 1)
    gross_receipts_row = db.execute(
        f"""SELECT {income_sql} as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE c.type = 'income' AND t.date >= ? AND t.date <= ? 
            AND t.is_transfer = 0""",
        (start_date, end_date)
    ).fetchone()
    gross_receipts = gross_receipts_row['total'] or 0.0

    # Expenses grouped by schedule_c_line
    expense_items = db.execute(
        f"""SELECT c.schedule_c_line, 
            {expense_sql} as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE c.type = 'expense' AND t.date >= ? AND t.date <= ?
            AND t.is_transfer = 0 AND c.schedule_c_line IS NOT NULL AND c.schedule_c_line != ''
            GROUP BY c.schedule_c_line
            ORDER BY c.schedule_c_line""",
        (start_date, end_date)
    ).fetchall()
    
    # Also fetch full details for UI drill down
    detail_items = db.execute(
        f"""SELECT c.schedule_c_line, c.name,
            {expense_sql} as total
            FROM transactions t
            JOIN categories c ON t.category_id = c.id
            WHERE c.type = 'expense' AND t.date >= ? AND t.date <= ?
            AND t.is_transfer = 0 AND c.schedule_c_line IS NOT NULL AND c.schedule_c_line != ''
            GROUP BY c.schedule_c_line, c.name
            ORDER BY c.schedule_c_line, c.name""",
        (start_date, end_date)
    ).fetchall()

    lines = {}
    for row in expense_items:
        if row['total'] and row['total'] > 0:
            lines[row['schedule_c_line']] = {'total': row['total'], 'categories': []}
            
    for row in detail_items:
        if row['total'] and row['total'] > 0 and row['schedule_c_line'] in lines:
            lines[row['schedule_c_line']]['categories'].append({
                'name': row['name'], 
                'amount': row['total']
            })

    total_expenses = sum(line_data['total'] for line_data in lines.values())
    
    # Add Home Office deduction (Line 30) - Safe Harbor $1500 total
    if owner in ('primary', 'spouse'):
        home_office_deduction = 750.00
    else:
        home_office_deduction = 1500.00
        
    total_expenses += home_office_deduction
    net_profit = gross_receipts - total_expenses

    return {
        'year': year,
        'owner': owner,
        'gross_receipts': gross_receipts,
        'lines': lines,
        'home_office_deduction': home_office_deduction,
        'total_expenses': total_expenses,
        'net_profit': net_profit
    }

def get_multi_year_report(year_current, year_prior, owner=None):
    """Generate multi-year comparison for P&L between two years."""
    start_current = f'{year_current}-01-01'
    end_current = f'{year_current}-12-31'
    start_prior = f'{year_prior}-01-01'
    end_prior = f'{year_prior}-12-31'

    curr_pl = get_pl_report_owner_adjusted(start_current, end_current, owner)
    prior_pl = get_pl_report_owner_adjusted(start_prior, end_prior, owner)

    def calc_variance(curr, prior):
        diff = curr - prior
        if prior > 0:
            pct = (diff / prior) * 100.0
        else:
            pct = 100.0 if curr > 0 else 0.0
        return diff, pct

    income_map = {}
    for item in curr_pl['income_items']:
        income_map[item['name']] = {'name': item['name'], 'category_id': item['category_id'], 'curr': item['total'], 'prior': 0.0}
    for item in prior_pl['income_items']:
        if item['name'] not in income_map:
            income_map[item['name']] = {'name': item['name'], 'category_id': item['category_id'], 'curr': 0.0, 'prior': item['total']}
        else:
            income_map[item['name']]['prior'] = item['total']

    expense_map = {}
    for item in curr_pl['expense_items']:
        expense_map[item['name']] = {'name': item['name'], 'category_id': item['category_id'], 'curr': item['total'], 'prior': 0.0}
    for item in prior_pl['expense_items']:
        if item['name'] not in expense_map:
            expense_map[item['name']] = {'name': item['name'], 'category_id': item['category_id'], 'curr': 0.0, 'prior': item['total']}
        else:
            expense_map[item['name']]['prior'] = item['total']

    income_list = []
    for k in sorted(income_map.keys()):
        i = income_map[k]
        i['diff'], i['pct'] = calc_variance(i['curr'], i['prior'])
        income_list.append(i)

    expense_list = []
    for k in sorted(expense_map.keys()):
        e = expense_map[k]
        e['diff'], e['pct'] = calc_variance(e['curr'], e['prior'])
        expense_list.append(e)

    curr_total_inc = curr_pl['total_income']
    prior_total_inc = prior_pl['total_income']
    inc_diff, inc_pct = calc_variance(curr_total_inc, prior_total_inc)

    curr_total_exp = curr_pl['total_expenses']
    prior_total_exp = prior_pl['total_expenses']
    exp_diff, exp_pct = calc_variance(curr_total_exp, prior_total_exp)

    curr_net = curr_pl['net_income']
    prior_net = prior_pl['net_income']
    net_diff, net_pct = calc_variance(curr_net, prior_net)

    return {
        'year_current': year_current,
        'year_prior': year_prior,
        'owner': owner,
        'income_items': income_list,
        'expense_items': expense_list,
        'totals': {
            'income': {'curr': curr_total_inc, 'prior': prior_total_inc, 'diff': inc_diff, 'pct': inc_pct},
            'expense': {'curr': curr_total_exp, 'prior': prior_total_exp, 'diff': exp_diff, 'pct': exp_pct},
            'net': {'curr': curr_net, 'prior': prior_net, 'diff': net_diff, 'pct': net_pct}
        }
    }
