# Admin Scanner Alpha Scaffold

This is a deliberately small alpha scaffold for turning a personal email scanner into a multi-user product prototype.

The goal is not to build the final SaaS app yet. The goal is to prove that another person can connect/import emails, see extracted admin items, review them, and get value from the dashboard.

## What this scaffold includes

- Streamlit app shell
- SQLite storage
- Users table
- Gmail accounts table
- Admin items table
- Review queue statuses
- CSV importer for early testing
- Rule-based extraction fallback
- Gmail OAuth placeholder files
- Dashboard ranked by urgency

## What this scaffold does not include yet

- Production OAuth verification
- Hosted authentication
- Encrypted token vault
- Background sync
- Payment flow
- Mobile app
- Full LLM extraction pipeline

## Quick start

```bash
cd admin_alpha_scaffold
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\\Scripts\\activate
pip install -r requirements.txt
streamlit run app.py
```

## Recommended alpha flow

1. Start with CSV import using your existing `admin_emails_v3.csv` or exported scanner output.
2. Confirm the database/dashboard/review queue works.
3. Move your existing email scanner logic into `extraction/extractor.py`.
4. Wire Gmail OAuth only after the core app flow feels useful.

## Expected CSV columns

The CSV importer is intentionally forgiving. It will look for common columns such as:

- `sender`, `from`, `from_email`
- `subject`, `email_subject`
- `date`, `received_at`, `date_received`
- `snippet`, `body`, `email_body`
- `source_name`, `admin_type`, `due_date`, `amount`, `confidence_score`

If extracted fields already exist in your CSV, it will use them. If not, it will apply a basic rule-based extractor.

## Data principle

For alpha testing, aim to store only extracted admin metadata and email identifiers. Avoid storing full raw email bodies unless you need them for debugging.
