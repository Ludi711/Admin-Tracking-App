# Hosted Gmail Web Alpha

This build is designed to answer the key product bottleneck:

> Can another person open a hosted web link, grant Gmail read-only access in the browser, and run an admin scan?

Use `app_hosted.py` as the Streamlit entry point.

## What changed from the local alpha

The original `app.py` uses a local/Desktop Google OAuth flow. That is useful for development, but it does not prove the hosted-user journey.

This hosted version adds:

- `app_hosted.py`
- `gmail_client/web_oauth.py`
- `ui/hosted_gmail.py`
- `.streamlit/secrets.example.toml`

The hosted flow is:

```text
User opens Streamlit app URL
→ clicks Connect Gmail
→ Google consent screen opens
→ user approves Gmail read-only access
→ Google redirects back to the Streamlit app
→ app saves encrypted token
→ user runs manual Gmail scan
→ dashboard/review queue populates
```

## Google Cloud setup

1. Create/open a Google Cloud project.
2. Enable the Gmail API.
3. Configure the OAuth consent screen.
4. Keep the app in Testing mode for alpha.
5. Add each tester's Gmail address as a test user.
6. Create OAuth credentials with application type **Web application**.
7. Add an Authorized redirect URI matching your deployed Streamlit URL exactly, for example:

```text
https://your-streamlit-app.streamlit.app/
```

The value must exactly match `GOOGLE_REDIRECT_URI` in Streamlit secrets.

## Streamlit Cloud setup

1. Push this folder to a GitHub repo.
2. Create a new Streamlit Community Cloud app.
3. Set the main file to:

```text
app_hosted.py
```

4. Deploy the app and copy its public URL.
5. In Google Cloud, add that exact URL as an Authorized redirect URI.
6. In Streamlit Cloud, open App settings > Secrets.
7. Copy the structure from `.streamlit/secrets.example.toml` and fill in real values.
8. Restart/reboot the app.
9. Send the link to a Gmail test user.

## Important alpha caveats

This is not production-ready SaaS yet. It is deliberately a web-link OAuth proof.

Known caveats:

- Google OAuth testing mode is limited to named test users.
- Gmail read-only access is a restricted scope.
- A public production app will need Google verification.
- If you store/transmit restricted Gmail data on servers, Google may require a security assessment.
- Streamlit Community Cloud local SQLite storage is not a durable production database.
- This app stores OAuth credentials in SQLite, encrypted only when `TOKEN_ENCRYPTION_KEY` is set.
- Raw email bodies are fetched for extraction in memory and not intentionally persisted.

## Testing checklist

For each tester, record:

- Did the hosted URL open?
- Did Google consent open?
- Did the warning screen block them?
- Could they approve read-only Gmail access?
- Did the app redirect back successfully?
- Could they scan 30/90 days?
- How many matched messages were inspected?
- How many admin items were imported?
- What did it miss?
- What false positives appeared?
- Did the dashboard/review queue make sense?

## What success looks like

The bottleneck is answered positively if:

```text
A tester opens only a web link, connects Gmail in their browser, runs a scan, and sees useful admin items without running local code.
```
