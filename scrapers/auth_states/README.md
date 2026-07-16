# Instagram Authentication

The scraper uses Playwright's **storage state** (session cookies + localStorage) to
authenticate with Instagram. You must complete this one-time login step before the
pipeline will extract real post data.

## How to Generate `state.json`

Run this one-time helper script:

```bash
python scrapers/auth_states/login.py
```

A Chromium window will open. Log in to Instagram normally. Once you see your feed,
press Enter in the terminal. The session is saved to `state.json` automatically.

**Do not commit `state.json` to git** (it is already in `.gitignore`).

## Manual Export (Alternative)

1. Log in at https://www.instagram.com in any browser.
2. Export your cookies using the "Cookie-Editor" browser extension.
3. Paste the JSON into `state.json` in the format Playwright expects:
   ```json
   {
     "cookies": [...],
     "origins": []
   }
   ```
