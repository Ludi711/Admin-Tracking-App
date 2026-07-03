# Next steps for turning V3 into alpha

## 1. Run the scaffold

```bash
pip install -r requirements.txt
streamlit run app.py
```

Create yourself as the first alpha user, then import `sample_data/sample_admin_emails.csv`.

## 2. Import your existing V3 CSV

Upload `admin_emails_v3.csv` through the Import CSV tab. The importer should accept flexible column names. If fields do not map cleanly, adjust `extraction/import_csv.py`.

## 3. Move your existing extraction logic

Replace the simple rule-based logic in:

```text
extraction/extractor.py
```

with your V3 extraction/classification logic. Keep the function interface stable:

```python
extract_admin_item(sender, subject, snippet, body, existing_fields) -> ExtractedAdminItem | None
```

## 4. Keep the data model simple

For alpha, aim to store:

- source/company
- subject
- admin type
- description
- due date
- amount
- urgency score
- confidence score
- review status

Avoid storing full raw email bodies unless debugging.

## 5. Add Gmail only after the dashboard flow is useful

Once CSV import feels good, wire your Gmail scanner into:

```text
gmail_client/sync.py
```

Start with a manual query such as:

```text
newer_than:6m
```

Then narrow it with targeted searches for renewals, bills, subscriptions, appointments, and deadlines.

## 6. Alpha acceptance criteria

The first alpha is good enough when:

- A second user can be created without changing code.
- Their imported/scanned emails create useful admin items.
- Bad extractions can be corrected or ignored.
- The dashboard ranks items by urgency.
- You can export or inspect the SQLite database.
