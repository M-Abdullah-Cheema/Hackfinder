# QuestHub — Exact steps (Vercel live + scrape on your PC)

Goal:

- Website **always online** on Vercel (free `*.vercel.app` link)
- Data comes from **Supabase** (already your database)
- Your **PC** only scrapes Instagram when it’s on (at login + every 10 hours)
- If PC is **off**, visitors still see the **last scraped** data

You do **not** need a paid domain.

---

## Part 0 — What you need open

1. This project folder: `C:\Users\muham\Hackathon_Scraper`
2. Browser tabs:
   - https://supabase.com/dashboard (your project)
   - https://vercel.com (sign in with GitHub)
   - https://github.com/M-Abdullah-Cheema/Hackfinder
3. PowerShell (Windows Terminal is fine)
4. Docker Desktop (for Redis) — install if missing: https://www.docker.com/products/docker-desktop/

---

## Part 1 — Get Supabase keys (5 minutes)

### Where
Supabase Dashboard → your project → **Project Settings** (gear) → **API**

### What to copy

| Name on page | What you’ll call it |
|--------------|---------------------|
| **Project URL** (looks like `https://abcdefgh.supabase.co`) | `NEXT_PUBLIC_SUPABASE_URL` |
| **`service_role`** secret (Reveal / copy) | `SUPABASE_SERVICE_ROLE_KEY` |

⚠️ Use **service_role**, not the anon key, for the server.  
⚠️ Never commit service_role to GitHub. Never put it in a `NEXT_PUBLIC_` variable.

---

## Part 2 — Local frontend env file

### Where
Create this file (new file):

`C:\Users\muham\Hackathon_Scraper\frontend\.env.local`

### What to put inside (paste your real values)

```env
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_ROLE_KEY=eyJhbGciOi...your_real_service_role_key
```

Save the file.

### Test locally (optional but recommended)

In PowerShell:

```powershell
cd C:\Users\muham\Hackathon_Scraper\frontend
npm install
npm run dev -- --port 3000 --hostname 127.0.0.1
```

Open: http://127.0.0.1:3000  

If cards load → Supabase keys are correct.  
If error about missing Supabase / 503 → keys wrong or not saved in `.env.local`.

Stop with `Ctrl+C` when done testing.

---

## Part 3 — Tell the PC scraper to run every 10 hours

### Where
Root env file:

`C:\Users\muham\Hackathon_Scraper\.env`

### What to add or change

Find or add this line:

```env
SCRAPE_INTERVAL_SECONDS=36000
```

(`36000` seconds = 10 hours)

Save.

---

## Part 4 — Redis (required for Celery on your PC)

### Where
PowerShell on your PC (Docker must be running)

### Commands

```powershell
docker ps
```

If you don’t already see a Redis container:

```powershell
docker run -d --name hackfinder-redis -p 6379:6379 redis:7
```

If it says name already in use:

```powershell
docker start hackfinder-redis
```

---

## Part 5 — Instagram login session (required for scraping)

### Where
PowerShell:

```powershell
cd C:\Users\muham\Hackathon_Scraper
$env:PLAYWRIGHT_BROWSERS_PATH = "$env:LOCALAPPDATA\ms-playwright"
python scrapers\auth_states\login.py
```

### What happens
1. A Chrome window opens
2. Log into Instagram (password / OTP / “confirm you’re human” if asked)
3. Wait until the normal home feed shows
4. Come back to PowerShell → press **Enter**
5. It saves `scrapers\auth_states\state.json` (private; already gitignored)

If Instagram blocks you later, run this same command again.

---

## Part 6 — Start scrape backend + auto-start on Windows login

### 6A — Register “start when I log in” (do once)

```powershell
cd C:\Users\muham\Hackathon_Scraper
powershell -ExecutionPolicy Bypass -File scripts\install_startup_task.ps1
```

You should see: `Scheduled task 'QuestHubBackend' registered`

### 6B — Start it now

```powershell
powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1
```

This starts:

- Celery **worker** (does scrapes / OCR / AI)
- Celery **Beat** (triggers scrape every 10 hours)

### 6C — Force one scrape now (so Vercel has fresh data)

```powershell
cd C:\Users\muham\Hackathon_Scraper
$env:PLAYWRIGHT_BROWSERS_PATH = "$env:LOCALAPPDATA\ms-playwright"
python scripts\trigger_pipeline.py
```

Wait until it finishes (can take several minutes). Use hotspot if campus WiFi blocks Supabase.

---

## Part 7 — Push latest code to GitHub (so Vercel can deploy it)

If you haven’t pushed the Vercel/Supabase frontend changes yet, in Cursor ask:

> commit and push to GitHub

Or in PowerShell (after reviewing changes):

```powershell
cd C:\Users\muham\Hackathon_Scraper
git status
git add frontend scripts DEPLOY_VERCEL.md core/pipeline_config.py .env.example
git commit -m "Add Vercel Supabase frontend and PC scrape startup scripts"
git push
```

Do **not** commit `.env`, `.env.local`, or `state.json`.

---

## Part 8 — Deploy QuestHub on Vercel (public site)

### 8.1 Sign in
1. Open https://vercel.com
2. **Continue with GitHub**
3. Authorize Vercel if asked

### 8.2 Import project
1. **Add New…** → **Project**
2. Find **Hackfinder** (your repo) → **Import**

### 8.3 Configure (IMPORTANT)

On the configure screen:

| Setting | Value |
|---------|--------|
| **Framework Preset** | Next.js |
| **Root Directory** | Click **Edit** → choose **`frontend`** → Continue |
| **Build Command** | leave default (`next build`) |
| **Output** | leave default |

### 8.4 Environment Variables (before Deploy)

Click **Environment Variables** and add **two**:

1. Name: `NEXT_PUBLIC_SUPABASE_URL`  
   Value: same as in `.env.local`  
   Environments: Production + Preview + Development (check all)

2. Name: `SUPABASE_SERVICE_ROLE_KEY`  
   Value: your service_role key  
   Environments: Production + Preview + Development

### 8.5 Deploy
Click **Deploy**. Wait 1–3 minutes.

### 8.6 Your live link
On success you’ll get something like:

`https://hackfinder-xxxx.vercel.app`

That URL is public. Rename the project in Vercel settings later if you want `questhub` in the name (still free).

---

## Part 9 — Verify the full loop

| Check | How |
|-------|-----|
| Site loads | Open your `*.vercel.app` link |
| Data shows | Cards appear (from last scrape in Supabase) |
| PC off test | Shut Celery / sleep PC → refresh Vercel → **same cards still there** |
| New data | PC on + wait for Beat (10h) or run `trigger_pipeline.py` → refresh Vercel |

---

## Day-to-day cheat sheet

```powershell
# Start Redis if needed
docker start hackfinder-redis

# Start scrape backend manually
cd C:\Users\muham\Hackathon_Scraper
powershell -ExecutionPolicy Bypass -File scripts\start_backend.ps1

# Scrape once now
python scripts\trigger_pipeline.py

# Instagram OTP / human check again
python scrapers\auth_states\login.py
```

Remove auto-start later (if you want):

```powershell
Unregister-ScheduledTask -TaskName 'QuestHubBackend' -Confirm:$false
```

---

## Common problems

| Problem | Fix |
|---------|-----|
| Vercel site empty / 503 | Env vars missing on Vercel → re-add + **Redeploy** |
| Local site 503 | Missing `frontend/.env.local` |
| Scrape fails / login wall | Re-run `login.py` |
| Redis errors | `docker start hackfinder-redis` |
| Supabase timeout on campus | Use phone hotspot |
| Vercel built wrong folder | Root Directory must be **`frontend`** |

---

## What you do NOT need

- ❌ Buying a domain  
- ❌ Hosting FastAPI on the internet  
- ❌ Leaving FastAPI `:8002` running for the public site  
- ❌ Netlify (Vercel is enough; Netlify is optional alternative)

FastAPI on your PC is only for optional local debugging. The public site talks to Supabase via Next.js API routes.
