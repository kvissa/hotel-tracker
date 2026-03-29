# Hotel Price Tracker

Multi-city hotel price tracker with daily email reports, Google + TripAdvisor reviews,
vegetarian restaurant recommendations, Nintendo/gaming spots for kids, and senior-friendly
accessibility filters.

---

## Files in this package

| File | Purpose |
|------|---------|
| `hotel_tracker.py` | Core logic — fetches prices, sends emails, runs scheduler |
| `app.py` | Flask web dashboard — multi-user, hosted on Railway |
| `requirements.txt` | Python dependencies |
| `Procfile` | Tells Railway how to start the app |
| `railway.toml` | Railway build configuration |
| `.gitignore` | Keeps credentials out of GitHub |

---

## Step 1 — Get your API keys (do this first)

You need four API keys before deploying. All have free tiers.

### SerpAPI (hotel prices + Google ratings)
1. Go to https://serpapi.com and sign up
2. Copy your API key from the dashboard
3. Free tier: 100 searches/month

### Google Places API (restaurants, transit, gaming spots)
1. Go to https://console.cloud.google.com
2. Create a new project (or use existing)
3. Go to APIs & Services → Enable APIs → search "Places API" → Enable
4. Go to APIs & Services → Credentials → Create Credentials → API Key
5. Copy the key
6. Free tier: 28,500 calls/month

### TripAdvisor Content API
1. Go to https://tripadvisor.com/developers
2. Sign up and create an app
3. Copy your API key
4. Free tier available

### Gmail API (for sending emails)
1. In the same Google Cloud project as above
2. Go to APIs & Services → Enable APIs → search "Gmail API" → Enable
3. Go to APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID
4. Application type: Desktop app
5. Download the JSON file — **rename it to `credentials.json`**
6. Run `python hotel_tracker.py` once locally — a browser window opens, log in with Gmail
7. This creates `token.json` — keep this file, you'll need it for Railway

---

## Step 2 — Test locally first

```bash
pip install -r requirements.txt
python app.py
```

Open http://localhost:5000 — you should see the login screen.

---

## Step 3 — Push to GitHub

```bash
git init
git add .
git commit -m "Initial hotel tracker"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/hotel-tracker.git
git push -u origin main
```

Make sure `.gitignore` is committed first so `credentials.json` and `token.json` are NOT pushed.

---

## Step 4 — Deploy to Railway

1. Go to https://railway.app and sign in with GitHub
2. Click **New Project** → **Deploy from GitHub repo** → select `hotel-tracker`
3. Railway will detect the `Procfile` and start building automatically

### Add environment variables

In Railway dashboard → your project → **Variables** tab, add:

| Variable | Value |
|----------|-------|
| `SERPAPI_KEY` | Your SerpAPI key |
| `PLACES_API_KEY` | Your Google Places API key |
| `TRIPADVISOR_KEY` | Your TripAdvisor key |
| `RECIPIENTS` | you@gmail.com,family@gmail.com (comma-separated) |
| `SECRET_KEY` | Any random string, e.g. `my-secret-xyz-123` |
| `PRICE_THRESHOLD` | `10` |
| `REPORT_TIME` | `08:00` |
| `REPORT_FREQ` | `every2days` (or: daily, weekdays, weekly) |
| `TIMEZONE` | `Asia/Tokyo` |
| `SENIORS` | `true` |
| `VEGETARIAN_ONLY` | `true` |
| `FLAG_NINTENDO` | `true` |

### Upload credentials and token files

Railway doesn't let you upload files directly through the UI. Use one of these methods:

**Option A — Base64 encode (recommended):**
```bash
# On your computer, encode both files:
base64 -i credentials.json | pbcopy   # copies to clipboard on Mac
base64 -i token.json | pbcopy
```
Add two more Railway variables:
- `CREDENTIALS_JSON_B64` — paste the base64 of credentials.json
- `TOKEN_JSON_B64` — paste the base64 of token.json

Then add this to the top of `hotel_tracker.py` before the app starts:
```python
import base64
if os.environ.get("CREDENTIALS_JSON_B64"):
    with open("credentials.json","w") as f:
        f.write(base64.b64decode(os.environ["CREDENTIALS_JSON_B64"]).decode())
if os.environ.get("TOKEN_JSON_B64"):
    with open("token.json","w") as f:
        f.write(base64.b64decode(os.environ["TOKEN_JSON_B64"]).decode())
```

**Option B — Railway Volume:**
In Railway dashboard → your project → **Add Volume** → mount at `/app`
Then use the Railway CLI to upload the files:
```bash
npm install -g @railway/cli
railway login
railway up
```

---

## Step 5 — Get your public URL

1. In Railway dashboard → your project → **Settings** tab → **Domains**
2. Click **Generate Domain** — you'll get a URL like `hotel-tracker-production.up.railway.app`
3. Share this URL with family

---

## How family members use it

1. Everyone opens the same URL
2. Each person types their name on the login screen (no password)
3. Their profile (cities, dates, rooms, preferences) is saved separately on the server
4. Click **Refresh prices** to run a report on demand
5. The scheduled email still goes out automatically at `REPORT_TIME`

---

## Updating your itinerary

The easiest way to update cities and dates is to edit `ITINERARY` in `hotel_tracker.py`,
commit and push to GitHub — Railway redeploys automatically within ~30 seconds.

The full UI-based save/load system (from the Claude widget) can be integrated by
extending the `/save_profile` endpoint and connecting it to the form fields in
`DASHBOARD_TMPL` in `app.py`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| "No module named flask" | Run `pip install -r requirements.txt` |
| Gmail auth fails on Railway | Make sure `token.json` is uploaded correctly |
| No hotels returned | Check your SerpAPI key and quota |
| App crashes on start | Check Railway logs → Variables tab → confirm all keys are set |
| Port error | Railway sets `$PORT` automatically — the Procfile already handles this |
