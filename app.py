import os
import json
import threading
from datetime import datetime
from flask import Flask, render_template_string, jsonify, request, session, redirect, url_for
from hotel_tracker import (
    run_report, load_profiles, save_profiles,
    PRICE_THRESHOLD, REPORT_TIME, REPORT_FREQ, SECRET_KEY
)

app = Flask(__name__)
app.secret_key = SECRET_KEY

report_cache   = {}   # keyed by username
last_updated   = {}

# ── Auth helpers ──────────────────────────────────────────────────────────────
def current_user():
    return session.get("user")

# ── Routes ────────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    user = current_user()
    if not user:
        return render_template_string(LOGIN_TMPL)
    profiles = load_profiles()
    profile  = profiles.get(user, {})
    report   = report_cache.get(user, [])
    updated  = last_updated.get(user, "Not yet run — click Refresh")
    return render_template_string(
        DASHBOARD_TMPL,
        user=user,
        profile=profile,
        report=report,
        last_updated=updated,
        threshold=PRICE_THRESHOLD,
        report_time=REPORT_TIME,
    )

@app.route("/login", methods=["POST"])
def login():
    name = request.form.get("name", "").strip()
    if name:
        session["user"] = name
    return redirect(url_for("index"))

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("index"))

@app.route("/save_profile", methods=["POST"])
def save_profile():
    user = current_user()
    if not user:
        return jsonify({"error": "not logged in"}), 401
    profiles = load_profiles()
    data = request.json or {}
    data["savedAt"] = datetime.now().isoformat()
    profiles[user]  = data
    save_profiles(profiles)
    return jsonify({"status": "saved"})

@app.route("/refresh")
def refresh():
    user = current_user()
    if not user:
        return jsonify({"error": "not logged in"}), 401
    def do_refresh():
        result = run_report(user=user)
        report_cache[user]  = result
        last_updated[user]  = datetime.now().strftime("%b %d %Y %H:%M")
    threading.Thread(target=do_refresh, daemon=True).start()
    return jsonify({"status": "refreshing"})

@app.route("/health")
def health():
    return jsonify({"status": "running", "users": list(report_cache.keys())})

# ── Templates ──────────────────────────────────────────────────────────────────
LOGIN_TMPL = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Hotel Tracker — Sign in</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:-apple-system,sans-serif;background:#f9f9f7;display:flex;
         align-items:center;justify-content:center;min-height:100vh;}
    .box{background:white;border:1px solid #eee;border-radius:14px;padding:32px 36px;
         width:100%;max-width:380px;}
    h1{font-size:20px;font-weight:500;margin-bottom:6px;}
    p{font-size:13px;color:#888;margin-bottom:24px;line-height:1.5;}
    input{width:100%;padding:10px 12px;border:1px solid #ddd;border-radius:8px;
          font-size:14px;margin-bottom:12px;}
    input:focus{outline:none;border-color:#555;}
    button{width:100%;padding:10px;border:none;border-radius:8px;
           background:#222;color:#fff;font-size:14px;font-weight:500;cursor:pointer;}
    button:hover{background:#444;}
    .hint{font-size:11px;color:#aaa;text-align:center;margin-top:14px;line-height:1.6;}
  </style>
</head>
<body>
  <div class="box">
    <h1>Hotel Price Tracker</h1>
    <p>Enter your name to access your personal report configuration. Each family member has their own saved settings.</p>
    <form method="POST" action="/login">
      <input type="text" name="name" placeholder="Your name, e.g. Mum" autofocus required />
      <button type="submit">Continue</button>
    </form>
    <div class="hint">No password needed. Your profile is saved to this server.<br>Each person's cities, dates and preferences are stored separately.</div>
  </div>
</body>
</html>
"""

DASHBOARD_TMPL = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Hotel Tracker — {{ user }}</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:-apple-system,sans-serif;background:#f9f9f7;color:#222;}
    .hdr{background:white;border-bottom:1px solid #eee;padding:14px 20px;
         display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:10px;}
    .hdr-left h1{font-size:17px;font-weight:500;}
    .hdr-left p{font-size:12px;color:#888;margin-top:2px;}
    .hdr-right{display:flex;gap:8px;align-items:center;}
    .btn{padding:7px 14px;border:1px solid #ddd;border-radius:8px;background:white;
         cursor:pointer;font-size:12px;text-decoration:none;color:#222;}
    .btn:hover{background:#f5f5f5;}
    .btn-primary{background:#222;color:white;border-color:#222;}
    .btn-primary:hover{background:#444;}
    .wrap{max-width:760px;margin:20px auto;padding:0 14px;}
    .status-bar{background:white;border:1px solid #eee;border-radius:8px;
                padding:9px 14px;margin-bottom:14px;font-size:12px;
                display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:6px;}
    .city-card{background:white;border:1px solid #eee;border-radius:12px;
               padding:18px;margin-bottom:14px;}
    .city-title{font-size:16px;font-weight:500;margin-bottom:2px;}
    .city-meta{font-size:11px;color:#888;margin-bottom:3px;line-height:1.6;}
    .hotel{border:1px solid #eee;border-radius:8px;padding:12px;margin-bottom:8px;}
    .hotel-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;}
    .hname{font-size:14px;font-weight:500;}
    .hmeta{font-size:11px;color:#888;margin-top:3px;}
    .price-block{text-align:right;flex-shrink:0;}
    .price{font-size:15px;font-weight:500;}
    .pmeta{font-size:11px;color:#aaa;}
    .extras{margin-top:8px;font-size:11px;color:#666;line-height:1.8;}
    .badge{font-size:10px;padding:2px 6px;border-radius:8px;display:inline-block;}
    .bg{background:#E6F1FB;color:#0C447C;}
    .ba{background:#FAEEDA;color:#633806;}
    .drop{background:#EAF3DE;color:#27500A;font-weight:500;}
    .rise{background:#FCEBEB;color:#791F1F;font-weight:500;}
    .empty-state{text-align:center;padding:40px 20px;color:#888;font-size:14px;}
    .profile-section{background:white;border:1px solid #eee;border-radius:12px;
                     padding:18px;margin-bottom:14px;}
    .profile-section h2{font-size:14px;font-weight:500;margin-bottom:12px;}
    .field{margin-bottom:10px;}
    .field label{display:block;font-size:11px;color:#888;margin-bottom:3px;}
    .field input,.field select{width:100%;padding:7px 10px;border:1px solid #ddd;
                               border-radius:6px;font-size:13px;}
    .save-profile-btn{padding:8px 18px;border:none;border-radius:8px;
                      background:#222;color:white;font-size:13px;cursor:pointer;}
    .refreshing{opacity:.6;pointer-events:none;}
  </style>
</head>
<body>

<div class="hdr">
  <div class="hdr-left">
    <h1>Hotel Price Tracker</h1>
    <p>Welcome, <b>{{ user }}</b> &nbsp;·&nbsp; Threshold ±{{ threshold }}% &nbsp;·&nbsp; {{ report_time }} daily</p>
  </div>
  <div class="hdr-right">
    <button class="btn btn-primary" id="refresh-btn" onclick="triggerRefresh()">Refresh prices</button>
    <a href="/logout" class="btn">Switch user</a>
  </div>
</div>

<div class="wrap">

  <div class="status-bar">
    <span>Last updated: <b id="last-updated">{{ last_updated }}</b></span>
    <span id="refresh-status" style="color:#888;font-size:11px;"></span>
  </div>

  {% if report %}
    {% for seg in report %}
    <div class="city-card">
      <div class="city-title">{{ seg.city }}</div>
      <div class="city-meta">
        {{ seg.check_in }} → {{ seg.check_out }} &middot; {{ seg.nights }} nights
        &middot; {{ seg.tier }} &middot; {{ seg.rooms|length }} room(s)<br>
        {% for r in seg.rooms %}
          Room {{ r.room }}: {{ r.adults }} adult{{ 's' if r.adults != 1 else '' }}
          {%- if r.children %}, {{ r.children|length }} child{{ 'ren' if r.children|length > 1 else '' }}
          (age{{ 's' if r.children|length > 1 else '' }}: {{ r.children|join(', ') }}){%- endif %}
          {{ ' &middot; ' if not loop.last else '' }}
        {% endfor %}
      </div>

      {% for h in seg.hotels %}
      {% set prev = h.prev_price if h.prev_price is defined else h.price %}
      {% set diff = h.price - prev %}
      {% set pct = ((diff|abs / prev * 100)|round(1)) if prev else 0 %}
      <div class="hotel">
        <div class="hotel-top">
          <div>
            <div class="hname">{{ h.name }}</div>
            <div class="hmeta">
              <span class="badge bg">G {{ h.google_rating }}</span>
              {% if h.ta_rating %}
              <span class="badge ba" style="margin-left:4px">TA {{ h.ta_rating }}</span>
              {% endif %}
            </div>
          </div>
          <div class="price-block">
            <div class="price">${{ h.price }}<span class="pmeta">/room/night</span></div>
            <div class="pmeta">${{ h.price * seg.nights * seg.rooms|length }} total</div>
            <div style="margin-top:3px;">
              {% if diff < 0 and pct >= threshold %}
                <span class="badge drop">▼ {{ pct }}% ALERT</span>
              {% elif diff > 0 and pct >= threshold %}
                <span class="badge rise">▲ {{ pct }}% ALERT</span>
              {% elif diff < 0 %}
                <span style="color:#3B6D11;font-size:11px">▼ {{ pct }}%</span>
              {% elif diff > 0 %}
                <span style="color:#A32D2D;font-size:11px">▲ {{ pct }}%</span>
              {% else %}
                <span style="color:#aaa;font-size:11px">— unchanged</span>
              {% endif %}
            </div>
          </div>
        </div>
        <div class="extras">
          {% if h.area_notes %}<div>📍 {{ h.area_notes }}</div>{% endif %}
          {% if h.gaming %}<div style="color:#185FA5">🎮 {{ h.gaming|join(', ') }}</div>{% endif %}
          {% if h.restaurants %}
          <div style="color:#3B6D11">🌿 Vegetarian nearby:
            {% for meal, places in h.restaurants.items() %}
              {{ meal|title }}: {{ places|join(', ') }}{% if not loop.last %} &middot; {% endif %}
            {% endfor %}
          </div>
          {% endif %}
        </div>
      </div>
      {% endfor %}
    </div>
    {% endfor %}

  {% else %}
    <div class="empty-state">
      No report data yet — click <b>Refresh prices</b> above to run your first report.
    </div>
  {% endif %}

</div>

<script>
function triggerRefresh() {
  var btn = document.getElementById('refresh-btn');
  var status = document.getElementById('refresh-status');
  btn.textContent = 'Refreshing...';
  btn.classList.add('refreshing');
  status.textContent = 'Fetching prices — this takes about 30 seconds...';
  fetch('/refresh')
    .then(function(r){ return r.json(); })
    .then(function(){
      setTimeout(function(){ location.reload(); }, 35000);
    })
    .catch(function(){
      btn.textContent = 'Refresh prices';
      btn.classList.remove('refreshing');
      status.textContent = 'Error — please try again.';
    });
}
</script>

</body>
</html>
"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Hotel Tracker on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)
