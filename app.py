import os
import json
import base64
import requests
import schedule
import time as tlib
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ── Write credentials from environment variables if running on Railway ────────
if os.environ.get("CREDENTIALS_JSON_B64"):
    with open("credentials.json", "w") as f:
        f.write(base64.b64decode(os.environ["CREDENTIALS_JSON_B64"]).decode())
if os.environ.get("TOKEN_JSON_B64"):
    with open("token.json", "w") as f:
        f.write(base64.b64decode(os.environ["TOKEN_JSON_B64"]).decode())

# ── Configuration ─────────────────────────────────────────────────────────────
SERPAPI_KEY      = os.environ.get("SERPAPI_KEY", "YOUR_SERPAPI_KEY")
PLACES_API_KEY   = os.environ.get("PLACES_API_KEY", "YOUR_PLACES_KEY")
TRIPADVISOR_KEY  = os.environ.get("TRIPADVISOR_KEY", "YOUR_TA_KEY")
RECIPIENTS       = os.environ.get("RECIPIENTS", "you@gmail.com").split(",")
REPORT_TIME      = os.environ.get("REPORT_TIME", "08:00")
REPORT_FREQ      = os.environ.get("REPORT_FREQ", "every2days")
TIMEZONE         = os.environ.get("TIMEZONE", "Asia/Tokyo")
PRICE_THRESHOLD  = int(os.environ.get("PRICE_THRESHOLD", "10"))
SENIORS          = os.environ.get("SENIORS", "true").lower() == "true"
VEGETARIAN_ONLY  = os.environ.get("VEGETARIAN_ONLY", "true").lower() == "true"
FLAG_NINTENDO    = os.environ.get("FLAG_NINTENDO", "true").lower() == "true"
GOOGLE_MIN       = float(os.environ.get("GOOGLE_MIN", "4.0"))
TA_MIN           = float(os.environ.get("TA_MIN", "4.0"))
LARGE_ROOMS      = os.environ.get("LARGE_ROOMS", "true").lower() == "true"
ACCESSIBLE       = os.environ.get("ACCESSIBLE", "true").lower() == "true"
ELEVATOR         = os.environ.get("ELEVATOR", "true").lower() == "true"
SECRET_KEY       = os.environ.get("SECRET_KEY", "change-me-in-production")
SCOPES           = ["https://www.googleapis.com/auth/gmail.send"]
PRICE_FILE       = "previous_prices.json"
PROFILES_FILE    = "profiles.json"

DEFAULT_ITINERARY = [
    {
        "city": "Tokyo", "hotel": "", "check_in": "2026-04-10",
        "check_out": "2026-04-14", "nights": 4, "tier": "mixed",
        "rooms": [
            {"room": 1, "adults": 2, "children": [], "notes": ""},
            {"room": 2, "adults": 1, "children": [12], "notes": ""}
        ]
    },
    {
        "city": "Kyoto", "hotel": "", "check_in": "2026-04-14",
        "check_out": "2026-04-17", "nights": 3, "tier": "luxury",
        "rooms": [
            {"room": 1, "adults": 2, "children": [], "notes": ""},
            {"room": 2, "adults": 1, "children": [12], "notes": ""}
        ]
    },
    {
        "city": "Osaka", "hotel": "", "check_in": "2026-04-17",
        "check_out": "2026-04-20", "nights": 3, "tier": "midrange",
        "rooms": [
            {"room": 1, "adults": 2, "children": [], "notes": ""},
            {"room": 2, "adults": 1, "children": [12], "notes": ""}
        ]
    }
]

# ── Profile helpers ───────────────────────────────────────────────────────────
def load_profiles():
    try:
        with open(PROFILES_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_profiles(profiles):
    with open(PROFILES_FILE, "w") as f:
        json.dump(profiles, f, indent=2)

def get_itinerary_for_user(user=None):
    if user:
        profiles = load_profiles()
        profile  = profiles.get(user, {})
        segs     = profile.get("segs", [])
        if segs:
            return segs
    return DEFAULT_ITINERARY

# ── Price history ─────────────────────────────────────────────────────────────
def load_prices():
    try:
        with open(PRICE_FILE) as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def save_prices(data):
    with open(PRICE_FILE, "w") as f:
        json.dump(data, f, indent=2)

# ── Hotel search ──────────────────────────────────────────────────────────────
def fetch_hotels(seg, room):
    q = f"{seg['tier']} hotel {seg['city']}"
    if SENIORS:     q += " accessible"
    if LARGE_ROOMS: q += " spacious room"
    params = {
        "engine":         "google_hotels",
        "q":              q,
        "check_in_date":  seg.get("check_in") or seg.get("ci"),
        "check_out_date": seg.get("check_out") or seg.get("co"),
        "adults":         room["adults"],
        "children":       len(room["children"]),
        "currency":       "USD",
        "api_key":        SERPAPI_KEY,
    }
    try:
        resp    = requests.get("https://serpapi.com/search", params=params, timeout=15)
        results = []
        for h in resp.json().get("properties", []):
            if h.get("overall_rating", 0) < GOOGLE_MIN:
                continue
            raw = h.get("rate_per_night", {}).get("lowest", 0)
            if isinstance(raw, str):
                raw = int(raw.replace("$", "").replace(",", ""))
            results.append({
                "name":          h.get("name", "Unknown"),
                "price":         int(raw),
                "google_rating": h.get("overall_rating", 0),
                "reviews":       h.get("reviews", 0),
            })
            if len(results) >= 3:
                break
        return results
    except Exception as e:
        print(f"fetch_hotels error: {e}")
        return []

# ── TripAdvisor ───────────────────────────────────────────────────────────────
def get_ta_rating(name, city):
    try:
        r = requests.get(
            "https://api.content.tripadvisor.com/api/v1/location/search",
            params={"key": TRIPADVISOR_KEY, "searchQuery": f"{name} {city}",
                    "category": "hotels", "language": "en"},
            timeout=10
        )
        data = r.json().get("data", [])
        if data:
            detail = requests.get(
                f"https://api.content.tripadvisor.com/api/v1/location/{data[0]['location_id']}/details",
                params={"key": TRIPADVISOR_KEY, "language": "en"},
                timeout=10
            ).json()
            rating = float(detail.get("rating", 0))
            return rating if rating >= TA_MIN else None
    except Exception:
        pass
    return None

# ── Google Places ─────────────────────────────────────────────────────────────
def get_coords(name, city):
    try:
        resp = requests.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json",
            params={"query": f"{name} {city}", "key": PLACES_API_KEY},
            timeout=10
        )
        results = resp.json().get("results", [])
        if results:
            loc = results[0]["geometry"]["location"]
            return loc["lat"], loc["lng"]
    except Exception:
        pass
    return None, None

def get_restaurants(lat, lng):
    if lat is None:
        return {}
    kw    = "vegetarian restaurant" if VEGETARIAN_ONLY else "restaurant"
    meals = {}
    for meal in ["breakfast", "lunch", "dinner"]:
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params={"location": f"{lat},{lng}", "radius": 600,
                        "keyword": kw, "type": "restaurant",
                        "key": PLACES_API_KEY},
                timeout=10
            )
            meals[meal] = [p["name"] for p in resp.json().get("results", [])[:3]]
        except Exception:
            meals[meal] = []
    return meals

def get_gaming(lat, lng):
    if not FLAG_NINTENDO or lat is None:
        return []
    spots = []
    for kw in ["Nintendo", "arcade", "gaming"]:
        try:
            resp = requests.get(
                "https://maps.googleapis.com/maps/api/place/nearbysearch/json",
                params={"location": f"{lat},{lng}", "radius": 2000,
                        "keyword": kw, "key": PLACES_API_KEY},
                timeout=10
            )
            for p in resp.json().get("results", [])[:1]:
                spots.append(p["name"])
        except Exception:
            pass
    return spots

# ── Threshold & trend ─────────────────────────────────────────────────────────
def check_threshold(price, prev):
    if prev == 0:
        return False, 0
    pct = abs(price - prev) / prev * 100
    return pct >= PRICE_THRESHOLD, round(pct, 1)

def trend_html(price, prev):
    if prev == 0:
        return '<span style="color:#888">— first reading</span>'
    diff  = price - prev
    pct   = round(abs(diff) / prev * 100, 1)
    alert = pct >= PRICE_THRESHOLD
    if diff < 0:
        s = "background:#EAF3DE;color:#27500A;border-radius:6px;padding:2px 8px;" if alert else "color:#3B6D11;"
        return f'<span style="{s}">▼ {pct}% drop{"  ⚠ ALERT" if alert else ""}</span>'
    elif diff > 0:
        s = "background:#FCEBEB;color:#791F1F;border-radius:6px;padding:2px 8px;" if alert else "color:#A32D2D;"
        return f'<span style="{s}">▲ {pct}% rise{"  ⚠ ALERT" if alert else ""}</span>'
    return '<span style="color:#888">— unchanged</span>'

# ── Email ─────────────────────────────────────────────────────────────────────
def room_lines(rooms):
    out = []
    for r in rooms:
        s = f"Room {r['room']}: {r['adults']} adult{'s' if r['adults'] != 1 else ''}"
        if r["children"]:
            ages = ", ".join(str(a) for a in r["children"])
            s += f", {len(r['children'])} child{'ren' if len(r['children']) > 1 else ''} (ages: {ages})"
        if r.get("notes"):
            s += f" — {r['notes']}"
        out.append(s)
    return out

def build_email(report, is_alert=False, alert_details=None):
    sections = ""
    for seg in report:
        lines    = room_lines(seg["rooms"])
        tot_a    = sum(r["adults"] for r in seg["rooms"])
        all_kids = [a for r in seg["rooms"] for a in r["children"]]
        guest_str = f"{tot_a} adult{'s' if tot_a != 1 else ''}"
        if all_kids:
            guest_str += f", {len(all_kids)} child{'ren' if len(all_kids) > 1 else ''} (ages: {', '.join(str(a) for a in all_kids)})"
        ci = seg.get("check_in") or seg.get("ci", "")
        co = seg.get("check_out") or seg.get("co", "")
        sections += f"""
        <h2 style='font-size:17px;margin:24px 0 2px'>{seg['city']}</h2>
        <p style='font-size:12px;color:#888;margin-bottom:4px'>
            {ci} → {co} &middot; {seg.get('nights','')} nights
            &middot; {seg['tier']} &middot; {len(seg['rooms'])} room(s)
        </p>
        <p style='font-size:12px;color:#888;margin-bottom:3px'>{guest_str}</p>
        <p style='font-size:11px;color:#aaa;margin-bottom:14px'>{"<br>".join(lines)}</p>"""

        for h in seg.get("hotels", []):
            prev  = h.get("prev_price", h["price"])
            grand = h["price"] * seg.get("nights", 1) * len(seg["rooms"])
            ta_str  = f" &nbsp; TA {h['ta_rating']:.1f}" if h.get("ta_rating") else ""
            gaming  = ("<br>🎮 " + ", ".join(h["gaming"])) if h.get("gaming") else ""
            veg     = "".join(
                f"<div>{m.title()}: {', '.join(r)}</div>"
                for m, r in h.get("restaurants", {}).items()
            )
            sections += f"""
            <div style='border:1px solid #eee;border-radius:8px;padding:14px;margin-bottom:12px;'>
              <div style='display:flex;justify-content:space-between;align-items:flex-start'>
                <div>
                  <b style='font-size:14px'>{h['name']}</b><br>
                  <span style='font-size:12px;color:#555'>
                    ★ {h['google_rating']} Google ({h['reviews']} reviews){ta_str}
                  </span>
                </div>
                <div style='text-align:right'>
                  <b style='font-size:15px'>${h['price']}</b>
                  <span style='font-size:11px;color:#aaa'>/room/night</span><br>
                  <span style='font-size:12px;color:#aaa'>${grand} total</span><br>
                  {trend_html(h['price'], prev)}
                </div>
              </div>
              <div style='margin-top:10px;font-size:12px;line-height:1.8;color:#555'>
                <div>📍 {h.get('area_notes', '')}</div>
                {gaming}
                <div style='color:#3B6D11'>🌿 Vegetarian nearby:</div>
                {veg}
              </div>
            </div>"""

    banner = ""
    if is_alert and alert_details:
        banner = f'<div style="background:#FCEBEB;border-radius:8px;padding:12px;margin-bottom:20px;color:#791F1F;font-weight:500">{alert_details}</div>'
    tag = "⚠ PRICE ALERT" if is_alert else "Hotel Report"
    return f"""
    <html><body style='font-family:sans-serif;max-width:640px;margin:auto;padding:24px;color:#222'>
      <h1 style='font-size:20px;margin-bottom:4px'>{tag}</h1>
      <p style='color:#888;font-size:13px;margin-bottom:20px'>
        {datetime.now().strftime("%A, %B %d %Y")} &middot; Threshold ±{PRICE_THRESHOLD}%
      </p>
      {banner}{sections}
      <p style='margin-top:28px;font-size:11px;color:#ccc'>hotel_tracker.py</p>
    </body></html>"""

def gmail_service():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        flow  = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
        creds = flow.run_local_server(port=0)
        with open("token.json", "w") as f:
            f.write(creds.to_json())
    return build("gmail", "v1", credentials=creds)

def send_email(html, subject):
    svc = gmail_service()
    for recipient in RECIPIENTS:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["To"]      = recipient.strip()
        msg.attach(MIMEText(html, "html"))
        raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
        svc.users().messages().send(userId="me", body={"raw": raw}).execute()
    print(f"[{datetime.now().strftime('%H:%M')}] Sent to {len(RECIPIENTS)} recipient(s).")

# ── Main report job ───────────────────────────────────────────────────────────
def run_report(user=None):
    print(f"[{datetime.now().strftime('%H:%M')}] Starting report for user: {user or 'default'}")
    itinerary = get_itinerary_for_user(user)
    prev      = load_prices()
    report    = []
    alerts    = []

    for seg in itinerary:
        print(f"  Fetching hotels for {seg['city']}...")
        seen = {}
        for room in seg["rooms"]:
            for h in fetch_hotels(seg, room):
                if h["name"] in seen:
                    continue
                key        = f"{seg['city']}:{h['name']}"
                prev_price = prev.get(key, h["price"])
                h["prev_price"] = prev_price
                triggered, pct = check_threshold(h["price"], prev_price)
                if triggered and prev_price != h["price"]:
                    direction = "dropped" if h["price"] < prev_price else "rose"
                    alerts.append(
                        f"{h['name']} in {seg['city']} {direction} {pct}% "
                        f"(was ${prev_price}, now ${h['price']})"
                    )
                prev[key] = h["price"]
                lat, lng = get_coords(h["name"], seg["city"])
                h["ta_rating"]   = get_ta_rating(h["name"], seg["city"])
                h["gaming"]      = get_gaming(lat, lng)
                h["restaurants"] = get_restaurants(lat, lng)
                h["area_notes"]  = f"{seg['city']} — area & transit info via Google Places"
                seen[h["name"]]  = h
                print(f"    Found: {h['name']} at ${h['price']}/night")

        seg["hotels"] = list(seen.values())
        report.append(seg)

    save_prices(prev)
    print(f"[{datetime.now().strftime('%H:%M')}] Report complete. {sum(len(s['hotels']) for s in report)} hotels found.")

    # Send email — wrapped in try/except so dashboard still works if Gmail not configured
    try:
        send_email(build_email(report), f"Hotel Report — {datetime.now().strftime('%b %d')}")
        if alerts:
            send_email(
                build_email(report, True, "<br>".join(alerts)),
                f"⚠ PRICE ALERT — {datetime.now().strftime('%b %d %H:%M')}"
            )
    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M')}] Email skipped (Gmail not configured): {e}")

    return report

# ── Scheduler ─────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    freq = REPORT_FREQ
    t    = REPORT_TIME

    if freq == "daily":
        schedule.every().day.at(t).do(run_report)
    elif freq == "every2days":
        schedule.every(2).days.at(t).do(run_report)
    elif freq == "weekdays":
        for day in [schedule.every().monday, schedule.every().tuesday,
                    schedule.every().wednesday, schedule.every().thursday,
                    schedule.every().friday]:
            day.at(t).do(run_report)
    elif freq == "weekly":
        schedule.every().monday.at(t).do(run_report)

    print(f"Hotel tracker running — {freq} at {t}. Press Ctrl+C to stop.")
    run_report()
    while True:
        schedule.run_pending()
        tlib.sleep(30)