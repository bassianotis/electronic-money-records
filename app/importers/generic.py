import csv
import io
import re
import hashlib
from datetime import datetime

def parse_generic_csv(file_content):
    """Parse a generic bank CSV export using fuzzy header mapping.
    
    Attempts to auto-detect Date, Description, and Amount columns.
    Generates a deterministic MD5 hash for the transaction_id if missing.
    """
    reader = csv.reader(io.StringIO(file_content))
    try:
        headers = next(reader)
    except StopIteration:
        raise ValueError("CSV file is empty.")
        
    # Clean headers for simpler matching
    clean_headers = [h.strip().lower() for h in headers]
    
    # 1. Map columns
    date_idx, desc_idx, amount_idx = _map_columns(clean_headers)
    credit_idx, debit_idx = None, None
    
    if amount_idx is None:
        # Check for split credit/debit columns
        credit_idx = _find_column(clean_headers, ['credit', 'deposit', 'in'])
        debit_idx = _find_column(clean_headers, ['debit', 'withdrawal', 'out'])
        if credit_idx is None and debit_idx is None:
            raise ValueError(
                "Could not auto-detect an Amount column. "
                "Please ensure your CSV has an 'Amount', or 'Credit' and 'Debit' headers."
            )
            
    # Check for an explicit transaction ID column just in case
    id_idx = _find_column(clean_headers, ['transaction id', 'reference', 'ref number', 'id'])
    
    transactions = []
    
    for row in reader:
        if not any(row):  # Skip empty rows
            continue
            
        try:
            date_str = row[date_idx].strip() if date_idx is not None else ""
            desc = row[desc_idx].strip() if desc_idx is not None else "Unknown"
            
            # Aggregate amount
            if amount_idx is not None:
                amount_str = row[amount_idx]
                amount = _parse_amount(amount_str)
            else:
                amount = 0.0
                if credit_idx is not None and row[credit_idx].strip():
                    amount += abs(_parse_amount(row[credit_idx]) or 0.0)
                if debit_idx is not None and row[debit_idx].strip():
                    amount -= abs(_parse_amount(row[debit_idx]) or 0.0)

            # Skip rows with completely null/unparseable amounts or dates
            if amount is None or not date_str:
                continue
                
            parsed_date = _parse_date(date_str)
            clean_desc = _clean_description(desc)
            
            # Determine Transaction ID
            if id_idx is not None and row[id_idx].strip():
                txn_id = row[id_idx].strip()
            else:
                # Generate deterministic hash to prevent duplicates (Idempotent)
                hash_input = f"{parsed_date}|{clean_desc}|{amount}".encode('utf-8')
                txn_id = "gen_" + hashlib.md5(hash_input).hexdigest()[:16]

            txn = {
                'transaction_id': txn_id,
                'date': parsed_date,
                'description': clean_desc,
                'amount': amount,
                'balance': None, # Generic parser cannot confidently infer rolling balances
                'is_transfer': _detect_transfer(clean_desc)
            }
            transactions.append(txn)
            
        except IndexError:
            continue  # Malformed row
            
    return {
        'account_id': None, # Enforce manual UI selection
        'transactions': transactions
    }

def _map_columns(headers):
    # Synonyms for Auto-Detection
    date_synonyms = ['date', 'posting date', 'transaction date', 'effective date', 'post date']
    desc_synonyms = ['description', 'name', 'payee', 'memo', 'title', 'transaction description']
    amount_synonyms = ['amount', 'amount (usd)', 'transaction amount', 'value']
    
    date_idx = _find_column(headers, date_synonyms)
    if date_idx is None:
        raise ValueError("Could not auto-detect a Date column. Please rename it to 'Date'.")
        
    desc_idx = _find_column(headers, desc_synonyms)
    if desc_idx is None:
        raise ValueError("Could not auto-detect a Description/Payee column. Please rename it to 'Description'.")
        
    amount_idx = _find_column(headers, amount_synonyms)
    
    return date_idx, desc_idx, amount_idx

def _find_column(headers, synonyms):
    for idx, header in enumerate(headers):
        if header in synonyms:
            return idx
    # Fallback partial matching
    for idx, header in enumerate(headers):
        for syn in synonyms:
            if syn in header:
                return idx
    return None

def _parse_date(date_str):
    if not date_str:
        return '2099-01-01' # Fallback to prevent DB crash, will be highly visible
    # Try multiple common formats
    formats = ['%m/%d/%Y', '%m/%d/%y', '%Y-%m-%d', '%d/%m/%Y', '%d/%m/%y']
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return date_str # Return raw if all fail

def _parse_amount(amount_str):
    if not amount_str:
        return None
    cleaned = amount_str.replace('$', '').replace(',', '').replace('"', '').strip()
    try:
        return float(cleaned)
    except ValueError:
        return None

def _clean_description(desc):
    desc = desc.rstrip('\\')
    desc = re.sub(r'\s+', ' ', desc)
    return desc.strip()

def _detect_transfer(desc):
    desc_lower = desc.lower()
    return bool(
        'transfer' in desc_lower or
        'tfr' in desc_lower or
        'zelle' in desc_lower or
        'venmo' in desc_lower
    )
