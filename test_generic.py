from app.importers.generic import parse_generic_csv
csv_data = """Transaction Date,Payee,Memo,Deposit,Withdrawal
10/01/2025,Acme Corp,Test,,150.00
10/02/2025,Venmo,Transfer,500.25,
"""
print(parse_generic_csv(csv_data))
