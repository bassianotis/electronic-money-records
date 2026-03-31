"""CCU CSV import parser."""
import csv
import io
import re
from datetime import datetime


def parse_ccu_csv(file_content):
    """Parse a Consumers Credit Union CSV export.

    Format: Account ID,Transaction ID,Date,Description,Check Number,Category,Tags,Amount,Balance

    Returns:
        dict with keys: account_id, transactions (list of dicts)
    """
    reader = csv.DictReader(io.StringIO(file_content))

    account_id = None
    transactions = []

    for row in reader:
        # Extract account ID from first row
        raw_account_id = row.get('Account ID', '').strip()
        if raw_account_id and not account_id:
            account_id = raw_account_id

        # Parse transaction
        txn = {
            'transaction_id': row.get('Transaction ID', '').strip(),
            'date': _parse_date(row.get('Date', '').strip()),
            'description': _clean_description(row.get('Description', '').strip()),
            'amount': _parse_amount(row.get('Amount', '').strip()),
            'balance': _parse_amount(row.get('Balance', '').strip()),
        }

        # Detect transfers
        desc = txn['description']
        txn['is_transfer'] = bool(
            'Transfer Withdrawal' in desc or
            'Transfer Deposit' in desc or
            desc.startswith('Tfr to') or
            desc.startswith('Tfr from') or
            'Dividend Credit' in desc
        )

        transactions.append(txn)

    return {
        'account_id': account_id,
        'transactions': transactions,
    }


def _parse_date(date_str):
    """Parse MM/DD/YY date format to YYYY-MM-DD."""
    if not date_str:
        return None
    try:
        dt = datetime.strptime(date_str, '%m/%d/%y')
        return dt.strftime('%Y-%m-%d')
    except ValueError:
        return date_str


def _parse_amount(amount_str):
    """Parse amount string like '$1,234.56' or '-$1,234.56' to float."""
    if not amount_str:
        return None
    # Remove $, commas, quotes
    cleaned = amount_str.replace('$', '').replace(',', '').replace('"', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return None


def _clean_description(desc):
    """Clean up transaction description."""
    # Remove trailing backslashes
    desc = desc.rstrip('\\')
    # Collapse multiple spaces
    desc = re.sub(r'\s+', ' ', desc)
    return desc.strip()
