# Electronic Money Records

A self-hosted, IRS-compliant accounting suite built for small LLCs. Runs on a Raspberry Pi via Docker — no SaaS fees, no cloud dependency, full control over your financial data.

## Features

- **Transaction Ledger** — CSV import, inline categorization, bulk actions, receipt attachments
- **Bank Reconciliation** — Statement-based reconciliation with target-lock balance matching
- **Invoice Management** — Create, send, and track invoices with auto-deposit matching
- **Tax Engine** — Federal + State + City estimated tax calculations with safe harbor tracking
- **Schedule C Generator** — Per-owner tax-ready output for Qualified Joint Ventures (QJV)
- **1099 Contractor Tracking** — YTD payment monitoring with automatic $600 threshold flagging
- **W-9 PDF Vault** — Secure document storage for contractor compliance
- **Health Insurance Tracking** — ACA premium and PTC tracking for self-employed deductions
- **Year-End Lock** — Prevent accidental edits to finalized tax years
- **Multi-Year Reports** — Year-over-year income/expense comparison
- **Full Backup & Restore** — One-click ZIP export/import of all data, receipts, and documents
- **Audit Trail** — Every change logged with timestamps

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python / Flask |
| Database | SQLite |
| Frontend | Vanilla HTML/CSS/JS, HTMX |
| PDF | WeasyPrint |
| Auth | bcrypt (hashed) or env-var credentials |
| Server | Gunicorn |
| Deploy | Docker |

## Quick Start

```bash
# Clone
git clone https://github.com/YOUR_USERNAME/electronic-money-records.git
cd electronic-money-records

# Configure credentials
cp .env.example .env
nano .env  # set AUTH_USERNAME, AUTH_PASSWORD, SECRET_KEY

# Run
docker compose up -d --build

# Access
open http://localhost:5001
```

## Environment Variables

| Variable | Description | Default |
|---|---|---|
| `AUTH_USERNAME` | Login username | `admin` |
| `AUTH_PASSWORD` | Login password | `admin` |
| `SECRET_KEY` | Flask session encryption key | (random) |

## Data Persistence

All data is stored in the `data/` directory (mounted as a Docker volume):
- `accounting.db` — SQLite database
- `receipts/` — Uploaded receipt files
- `w9s/` — Contractor W-9 documents

To back up, use the in-app **Settings → Backup** feature or simply copy the `data/` directory.

## Raspberry Pi Deployment

This runs natively on ARM hardware. On your Pi:

```bash
git clone <your-repo-url>
cd electronic-money-records
cp .env.example .env && nano .env
docker compose up -d --build
```

Access from any device on your network at `http://<pi-ip>:5001`.

## License

Licensed under the GNU General Public License v3.0 (GPLv3). See the `LICENSE` file for details.
