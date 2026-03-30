import os
import json
import threading
from datetime import datetime
from flask import (Flask, render_template_string, jsonify,
                   request, session, redirect, url_for)

try:
    from hotel_tracker import (run_report, load_profiles, save_profiles,
                               PRICE_THRESHOLD, REPORT_TIME, REPORT_FREQ, SECRET_KEY)
except Exception as e:
    import traceback
    traceback.print_exc()
    PRICE_THRESHOLD = 10
    REPORT_TIME = "08:00"
    REPORT_FREQ = "every2days"
    SECRET_KEY = os.environ.get("SECRET_KEY", "fallback-secret")
    def run_report(user=None): return []
    def load_profiles(): return {}
    def save_profiles(p): pass

app = Flask(__name__)
app.secret_key = SECRET_KEY
report_cache = {}
last_updated  = {}

def current_user():
    return session.get("user")

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
        user=user, profile=profile, report=report,
        last_updated=updated,
        threshold=PRICE_THRESHOLD, report_time=REPORT_TIME
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
def save_profile_route():
    user = current_user()
    if not user:
        return jsonify({"error": "not logged in"}), 401
    profiles = load_profiles()
    data = request.json or {}
    data["savedAt"] = datetime.now().isoformat()
    profiles[user]  = data
    save_profiles(profiles)
    return jsonify({"status": "saved"})

@app.route("/load_profile")
def load_profile_route():
    user = current_user()
    if not user:
        return jsonify({"error": "not logged in"}), 401
    profiles = load_profiles()
    return jsonify(profiles.get(user, {}))

@app.route("/refresh")
def refresh():
    user = current_user()
    if not user:
        return jsonify({"error": "not logged in"}), 401
    def do_refresh():
        result = run_report(user=user)
        report_cache[user] = result
        last_updated[user] = datetime.now().strftime("%b %d %Y %H:%M")
    threading.Thread(target=do_refresh, daemon=True).start()
    return jsonify({"status": "refreshing"})

@app.route("/health")
def health():
    return jsonify({"status": "running", "users": list(report_cache.keys())})

LOGIN_TMPL = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Hotel Tracker</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
         background:#f5f5f3;display:flex;align-items:center;
         justify-content:center;min-height:100vh;}
    .box{background:#fff;border:1px solid #e8e8e8;border-radius:16px;
         padding:36px 40px;width:100%;max-width:400px;}
    h1{font-size:22px;font-weight:600;margin-bottom:6px;}
    p{font-size:13px;color:#888;margin-bottom:24px;line-height:1.6;}
    input{width:100%;padding:11px 14px;border:1px solid #ddd;border-radius:10px;
          font-size:14px;margin-bottom:14px;outline:none;font-family:inherit;}
    input:focus{border-color:#555;}
    button{width:100%;padding:11px;border:none;border-radius:10px;
           background:#1a1a1a;color:#fff;font-size:14px;font-weight:500;cursor:pointer;}
    button:hover{background:#333;}
    .note{font-size:11px;color:#bbb;text-align:center;margin-top:16px;line-height:1.6;}
  </style>
</head>
<body>
  <div class="box">
    <h1>Hotel Price Tracker</h1>
    <p>Enter your name to access your personal report. Each family member has their own saved configuration.</p>
    <form method="POST" action="/login">
      <input type="text" name="name" placeholder="Your name, e.g. Mum" autofocus required />
      <button type="submit">Continue</button>
    </form>
    <div class="note">No password needed &nbsp;·&nbsp; Your profile is saved on the server<br>
    Everyone shares the URL but sees their own settings</div>
  </div>
</body>
</html>"""

DASHBOARD_TMPL = """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Hotel Tracker</title>
  <style>
    *{box-sizing:border-box;margin:0;padding:0;}
    body{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
         background:#f5f5f3;color:#1a1a1a;font-size:14px;}
    .hdr{background:#fff;border-bottom:1px solid #e8e8e8;padding:13px 20px;
         display:flex;align-items:center;justify-content:space-between;
         flex-wrap:wrap;gap:10px;position:sticky;top:0;z-index:100;}
    .hdr-title{font-size:16px;font-weight:600;}
    .hdr-sub{font-size:12px;color:#888;margin-top:2px;}
    .hdr-btns{display:flex;gap:8px;flex-wrap:wrap;}
    .btn{padding:7px 16px;border:1px solid #ddd;border-radius:8px;background:#fff;
         cursor:pointer;font-size:13px;color:#1a1a1a;text-decoration:none;
         white-space:nowrap;font-family:inherit;}
    .btn:hover{background:#f5f5f3;}
    .btn-primary{background:#1a1a1a;color:#fff;border-color:#1a1a1a;}
    .btn-primary:hover{background:#333;}
    .btn-save{background:#1a6b3c;color:#fff;border-color:#1a6b3c;}
    .btn-save:hover{background:#155230;}
    .tab-bar{background:#fff;border-bottom:1px solid #e8e8e8;display:flex;overflow-x:auto;}
    .tab-btn{padding:12px 20px;border:none;background:none;cursor:pointer;font-size:13px;
             color:#888;border-bottom:2px solid transparent;white-space:nowrap;font-family:inherit;}
    .tab-btn.active{color:#1a1a1a;font-weight:500;border-bottom-color:#1a1a1a;}
    .tab-btn:hover{color:#1a1a1a;}
    .panel{display:none;max-width:800px;margin:0 auto;padding:20px 14px 100px;}
    .panel.active{display:block;}
    .card{background:#fff;border:1px solid #e8e8e8;border-radius:12px;
          padding:18px 20px;margin-bottom:14px;}
    .card-title{font-size:15px;font-weight:600;margin-bottom:14px;}
    .slbl{font-size:11px;font-weight:600;color:#888;text-transform:uppercase;
          letter-spacing:.06em;margin:14px 0 8px;}
    .slbl:first-of-type{margin-top:0;}
    label.lbl{display:block;font-size:11px;color:#888;margin-bottom:4px;}
    input[type=text],input[type=email],input[type=date],input[type=number],
    input[type=time],select{width:100%;padding:8px 11px;border:1px solid #ddd;
      border-radius:8px;font-size:13px;background:#fff;color:#1a1a1a;font-family:inherit;}
    input:focus,select:focus{outline:none;border-color:#888;}
    .g2{display:grid;grid-template-columns:1fr 1fr;gap:10px;}
    .g3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:10px;}
    .tgl-row{display:flex;align-items:center;justify-content:space-between;
             padding:9px 0;border-bottom:1px solid #f0f0f0;}
    .tgl-row:last-child{border-bottom:none;}
    .tgl-lbl{font-size:13px;}
    .tgl-sub{font-size:11px;color:#888;margin-top:1px;}
    .tog{position:relative;width:36px;height:20px;flex-shrink:0;display:inline-block;}
    .tog input{opacity:0;width:0;height:0;position:absolute;}
    .tog-sl{position:absolute;inset:0;background:#ddd;border-radius:20px;
            cursor:pointer;transition:background .15s;}
    .tog-sl:before{content:'';position:absolute;width:14px;height:14px;left:3px;top:3px;
                   background:#fff;border-radius:50%;transition:transform .15s;}
    .tog input:checked~.tog-sl{background:#1a6b3c;}
    .tog input:checked~.tog-sl:before{transform:translateX(16px);}
    .gc{display:flex;align-items:center;gap:8px;}
    .gc-btn{width:28px;height:28px;border:1px solid #ddd;border-radius:8px;
            background:#f5f5f3;cursor:pointer;font-size:16px;
            display:flex;align-items:center;justify-content:center;
            flex-shrink:0;font-family:inherit;}
    .gc-btn:hover{background:#e8e8e8;}
    .gc-val{font-size:14px;font-weight:600;min-width:22px;text-align:center;}
    .seg{background:#fff;border:1px solid #e8e8e8;border-radius:12px;
         padding:18px 20px;margin-bottom:12px;}
    .seg-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:14px;}
    .seg-name{font-size:15px;font-weight:600;}
    .nights-pill{background:#e8f0fe;color:#1a56db;font-size:11px;font-weight:500;
                 padding:2px 9px;border-radius:10px;margin-left:8px;}
    .x-btn{background:none;border:none;cursor:pointer;font-size:18px;
           color:#bbb;line-height:1;padding:2px 4px;}
    .x-btn:hover{color:#1a1a1a;}
    .room-card{background:#f9f9f7;border:1px solid #eee;border-radius:8px;
               padding:12px 14px;margin-bottom:8px;}
    .room-hdr{display:flex;align-items:center;justify-content:space-between;margin-bottom:10px;}
    .room-lbl{font-size:12px;font-weight:600;color:#888;}
    .add-room-btn{width:100%;padding:8px;border:1px dashed #ccc;border-radius:8px;
                  background:none;color:#888;font-size:12px;cursor:pointer;
                  margin-top:4px;font-family:inherit;}
    .add-room-btn:hover{background:#f5f5f3;color:#1a1a1a;}
    .sum-bar{background:#f0f0ee;border-radius:8px;padding:7px 11px;
             font-size:12px;color:#666;margin-top:10px;line-height:1.7;}
    .child-row{display:flex;flex-wrap:wrap;gap:8px;margin-top:8px;}
    .child-tag{display:inline-flex;align-items:center;gap:6px;background:#fff;
               border:1px solid #ddd;border-radius:8px;padding:4px 8px;font-size:12px;}
    .child-tag span{color:#888;font-size:11px;white-space:nowrap;}
    .child-tag input{width:44px;padding:2px 5px;font-size:12px;
                     border:1px solid #ddd;border-radius:5px;}
    .child-tag .rm{background:none;border:none;cursor:pointer;
                   color:#bbb;font-size:14px;padding:0;line-height:1;}
    .child-tag .rm:hover{color:#1a1a1a;}
    .freq-chips{display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px;}
    .freq-chip{padding:7px 16px;border:1px solid #ddd;border-radius:20px;font-size:13px;
               cursor:pointer;color:#888;background:#fff;font-family:inherit;}
    .freq-chip.sel{background:#1a1a1a;color:#fff;border-color:#1a1a1a;}
    .day-chips{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:12px;}
    .day-chip{padding:5px 11px;border:1px solid #ddd;border-radius:20px;font-size:12px;
              cursor:pointer;color:#888;background:#fff;font-family:inherit;}
    .day-chip.sel{background:#e8f0fe;color:#1a56db;border-color:#c0d0f8;}
    .thr-num{font-size:28px;font-weight:600;text-align:center;}
    .alert-dn{background:#f0fdf4;color:#166534;border-radius:8px;
              padding:8px 12px;text-align:center;font-size:13px;}
    .alert-up{background:#fef2f2;color:#991b1b;border-radius:8px;
              padding:8px 12px;text-align:center;font-size:13px;}
    .status-bar{background:#fff;border:1px solid #e8e8e8;border-radius:8px;
                padding:10px 16px;margin-bottom:16px;font-size:12px;
                display:flex;justify-content:space-between;align-items:center;
                flex-wrap:wrap;gap:8px;}
    .hotel-card{border:1px solid #eee;border-radius:10px;padding:14px;margin-bottom:10px;}
    .hotel-top{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;}
    .hotel-name{font-size:14px;font-weight:600;}
    .hotel-meta{font-size:11px;color:#888;margin-top:3px;}
    .price-num{font-size:16px;font-weight:600;text-align:right;}
    .price-sub{font-size:11px;color:#aaa;text-align:right;}
    .hotel-extras{margin-top:10px;font-size:12px;color:#555;line-height:1.8;}
    .badge{font-size:10px;padding:2px 7px;border-radius:8px;
           display:inline-block;font-weight:500;}
    .b-g{background:#e8f0fe;color:#1a56db;}
    .b-ta{background:#fef3c7;color:#92400e;}
    .b-drop{background:#f0fdf4;color:#166534;font-weight:600;}
    .b-rise{background:#fef2f2;color:#991b1b;font-weight:600;}
    .empty-state{text-align:center;padding:50px 20px;color:#888;}
    .empty-state h2{font-size:16px;margin-bottom:8px;color:#555;}
    .save-bar{position:fixed;bottom:0;left:0;right:0;background:#fff;
              border-top:1px solid #e8e8e8;padding:12px 20px;
              display:flex;align-items:center;justify-content:space-between;
              gap:12px;z-index:200;}
    .save-msg{font-size:13px;color:#888;}
    .save-msg.ok{color:#166534;}
    .save-msg.err{color:#991b1b;}
    input[type=range]{width:100%;}
    @media(max-width:520px){.g2,.g3{grid-template-columns:1fr;}}
  </style>
</head>
<body>

<div class="hdr">
  <div>
    <div class="hdr-title">Hotel Price Tracker</div>
    <div class="hdr-sub">Welcome, <b>{{ user }}</b></div>
  </div>
  <div class="hdr-btns">
    <button class="btn btn-save" id="hdr-save-btn">Save changes</button>
    <button class="btn btn-primary" id="refresh-btn" onclick="triggerRefresh()">Refresh prices</button>
    <a href="/logout" class="btn">Switch user</a>
  </div>
</div>

<div class="tab-bar">
  <button class="tab-btn active" data-tab="report">Report</button>
  <button class="tab-btn" data-tab="itinerary">Itinerary</button>
  <button class="tab-btn" data-tab="preferences">Preferences</button>
  <button class="tab-btn" data-tab="delivery">Delivery &amp; alerts</button>
</div>

<div class="panel active" id="tab-report">
  <div class="status-bar">
    <span>Last updated: <b id="last-updated">{{ last_updated }}</b></span>
    <span id="refresh-status" style="font-size:12px;color:#888;"></span>
  </div>
  {% if report %}
    {% for seg in report %}
    <div class="card">
      <div style="font-size:16px;font-weight:600;margin-bottom:3px;">{{ seg.city }}</div>
      <div style="font-size:12px;color:#888;margin-bottom:3px;">
        {{ seg.check_in }} → {{ seg.check_out }} &middot; {{ seg.nights }} nights
        &middot; {{ seg.tier }} &middot; {{ seg.rooms|length }} room(s)
      </div>
      <div style="font-size:12px;color:#aaa;margin-bottom:14px;">
        {% for r in seg.rooms %}Room {{ r.room }}: {{ r.adults }} adult{{ 's' if r.adults!=1 else '' }}
          {%- if r.children %}, {{ r.children|length }} child{{ 'ren' if r.children|length>1 else '' }}
          (ages: {{ r.children|join(', ') }}){%- endif %}
          {{ ' &middot; ' if not loop.last else '' }}
        {% endfor %}
      </div>
      {% for h in seg.hotels %}
      {% set prev=h.prev_price if h.prev_price is defined else h.price %}
      {% set diff=h.price-prev %}
      {% set pct=((diff|abs/prev*100)|round(1)) if prev else 0 %}
      <div class="hotel-card">
        <div class="hotel-top">
          <div style="flex:1;">
            <div class="hotel-name">{{ h.name }}</div>
            <div class="hotel-meta">
              <span class="badge b-g">G {{ h.google_rating }}</span>
              {% if h.ta_rating %}
              <span class="badge b-ta" style="margin-left:4px;">TA {{ h.ta_rating }}</span>
              {% endif %}
            </div>
          </div>
          <div>
            <div class="price-num">${{ h.price }}
              <span style="font-size:11px;font-weight:400;color:#aaa;">/room/night</span>
            </div>
            <div class="price-sub">${{ h.price * seg.nights * seg.rooms|length }} total</div>
            <div style="margin-top:4px;text-align:right;">
              {% if diff<0 and pct>=threshold %}<span class="badge b-drop">▼ {{ pct }}% ALERT</span>
              {% elif diff>0 and pct>=threshold %}<span class="badge b-rise">▲ {{ pct }}% ALERT</span>
              {% elif diff<0 %}<span style="color:#166534;font-size:12px;">▼ {{ pct }}%</span>
              {% elif diff>0 %}<span style="color:#991b1b;font-size:12px;">▲ {{ pct }}%</span>
              {% else %}<span style="color:#aaa;font-size:12px;">— unchanged</span>{% endif %}
            </div>
          </div>
        </div>
        <div class="hotel-extras">
          {% if h.area_notes %}<div>📍 {{ h.area_notes }}</div>{% endif %}
          {% if h.gaming %}<div style="color:#1a56db;">🎮 {{ h.gaming|join(', ') }}</div>{% endif %}
          {% if h.restaurants %}
          <div style="color:#166534;">🌿
            {% for meal,places in h.restaurants.items() %}
              <b>{{ meal|title }}:</b> {{ places|join(', ') }}
              {% if not loop.last %} &middot; {% endif %}
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
      <h2>No report data yet</h2>
      <p>First set up your itinerary in the <b>Itinerary</b> tab, save it,<br>
      then click <b>Refresh prices</b> to run your first report.</p>
    </div>
  {% endif %}
</div>

<div class="panel" id="tab-itinerary">
  <div id="seg-list"></div>
  <button class="btn" id="add-city-btn" style="width:100%;padding:11px;">+ Add city</button>
</div>

<div class="panel" id="tab-preferences">
  <div class="card">
    <div class="card-title">Hotel tier defaults</div>
    <div style="display:flex;gap:16px;flex-wrap:wrap;">
      <label style="display:flex;align-items:center;gap:7px;font-size:13px;cursor:pointer;">
        <input type="checkbox" id="p-mid" checked> Mid-range</label>
      <label style="display:flex;align-items:center;gap:7px;font-size:13px;cursor:pointer;">
        <input type="checkbox" id="p-lux" checked> Luxury</label>
      <label style="display:flex;align-items:center;gap:7px;font-size:13px;cursor:pointer;">
        <input type="checkbox" id="p-bud"> Budget</label>
    </div>
  </div>
  <div class="card">
    <div class="card-title">Room requirements</div>
    <div class="tgl-row"><div><div class="tgl-lbl">Rooms &gt;175 sqft / 16 sqm</div>
      <div class="tgl-sub">Filter for larger rooms only</div></div>
      <label class="tog"><input type="checkbox" id="p-large" checked><span class="tog-sl"></span></label></div>
    <div class="tgl-row"><div><div class="tgl-lbl">Natural light / high floor</div>
      <div class="tgl-sub">South/east facing, no interior rooms</div></div>
      <label class="tog"><input type="checkbox" id="p-light" checked><span class="tog-sl"></span></label></div>
    <div class="tgl-row"><div><div class="tgl-lbl">Step-free entrance</div>
      <div class="tgl-sub">Required for seniors and mobility needs</div></div>
      <label class="tog"><input type="checkbox" id="p-step" checked><span class="tog-sl"></span></label></div>
    <div class="tgl-row"><div><div class="tgl-lbl">Lift / elevator access</div>
      <div class="tgl-sub">No stairs required to reach the room</div></div>
      <label class="tog"><input type="checkbox" id="p-lift" checked><span class="tog-sl"></span></label></div>
    <div class="tgl-row"><div><div class="tgl-lbl">Family / interconnecting rooms</div></div>
      <label class="tog"><input type="checkbox" id="p-fam"><span class="tog-sl"></span></label></div>
  </div>
  <div class="card">
    <div class="card-title">Reviews &amp; extras</div>
    <div class="tgl-row"><div><div class="tgl-lbl">Google reviews &gt; 4.0 only</div></div>
      <label class="tog"><input type="checkbox" id="r-google" checked><span class="tog-sl"></span></label></div>
    <div class="tgl-row"><div><div class="tgl-lbl">TripAdvisor reviews &gt; 4.0</div></div>
      <label class="tog"><input type="checkbox" id="r-ta" checked><span class="tog-sl"></span></label></div>
    <div class="tgl-row"><div><div class="tgl-lbl">Vegetarian restaurants only</div>
      <div class="tgl-sub">Breakfast, lunch &amp; dinner near each hotel</div></div>
      <label class="tog"><input type="checkbox" id="r-veg" checked><span class="tog-sl"></span></label></div>
    <div class="tgl-row"><div><div class="tgl-lbl">Flag Nintendo / gaming spots nearby</div>
      <div class="tgl-sub">For children who enjoy Nintendo games</div></div>
      <label class="tog"><input type="checkbox" id="r-nin" checked><span class="tog-sl"></span></label></div>
    <div class="tgl-row"><div><div class="tgl-lbl">Area highlights &amp; transit info</div>
      <div class="tgl-sub">Subway distance, walkability, tourist spots</div></div>
      <label class="tog"><input type="checkbox" id="r-area" checked><span class="tog-sl"></span></label></div>
    <div class="tgl-row"><div><div class="tgl-lbl">Seniors travelling</div>
      <div class="tgl-sub">Step-free, lift access, tourist-area hotels</div></div>
      <label class="tog"><input type="checkbox" id="r-senior" checked><span class="tog-sl"></span></label></div>
  </div>
</div>

<div class="panel" id="tab-delivery">
  <div class="card">
    <div class="card-title">Report frequency</div>
    <div class="freq-chips" id="freq-chips">
      <button class="freq-chip" data-freq="daily">Daily</button>
      <button class="freq-chip sel" data-freq="every2days">Every 2 days</button>
      <button class="freq-chip" data-freq="weekdays">Weekdays only</button>
      <button class="freq-chip" data-freq="weekly">Weekly</button>
      <button class="freq-chip" data-freq="custom">Custom days</button>
    </div>
    <div id="custom-days-wrap" style="display:none;margin-bottom:14px;">
      <label class="lbl" style="margin-bottom:8px;">Select days</label>
      <div class="day-chips" id="day-chips">
        <button class="day-chip sel" data-day="mon">Mon</button>
        <button class="day-chip" data-day="tue">Tue</button>
        <button class="day-chip sel" data-day="wed">Wed</button>
        <button class="day-chip" data-day="thu">Thu</button>
        <button class="day-chip sel" data-day="fri">Fri</button>
        <button class="day-chip" data-day="sat">Sat</button>
        <button class="day-chip" data-day="sun">Sun</button>
      </div>
    </div>
    <div class="g2" style="margin-bottom:12px;">
      <div><label class="lbl">Send time</label>
        <input type="time" id="send-time" value="08:00"></div>
      <div><label class="lbl">Time zone</label>
        <select id="send-tz">
          <option value="America/Los_Angeles">Pacific Time</option>
          <option value="America/New_York">Eastern Time</option>
          <option value="Europe/London">London</option>
          <option value="Asia/Tokyo" selected>Tokyo</option>
        </select>
      </div>
    </div>
    <div id="freq-preview" style="background:#f5f5f3;border-radius:8px;
         padding:8px 12px;font-size:12px;color:#666;"></div>
  </div>
  <div class="card">
    <div class="card-title">Price change alerts</div>
    <div style="display:flex;align-items:center;gap:16px;margin-bottom:14px;">
      <div style="flex:1;">
        <label class="lbl" style="margin-bottom:6px;">Alert when price changes by more than</label>
        <input type="range" id="thr-range" min="1" max="30" step="1" value="10">
      </div>
      <div style="text-align:center;min-width:56px;">
        <div class="thr-num" id="thr-val">10%</div>
        <div style="font-size:11px;color:#888;">threshold</div>
      </div>
    </div>
    <div class="g2" style="margin-bottom:12px;">
      <div class="alert-dn">
        <div style="font-size:11px;margin-bottom:3px;">Drop alert</div>
        <div id="drop-lbl">▼ &gt;10% — email sent</div>
      </div>
      <div class="alert-up">
        <div style="font-size:11px;margin-bottom:3px;">Rise alert</div>
        <div id="rise-lbl">▲ &gt;10% — email sent</div>
      </div>
    </div>
    <div style="font-size:12px;color:#888;background:#f5f5f3;
         border-radius:8px;padding:8px 12px;">
      A separate alert email fires immediately when the threshold is crossed.
      The scheduled digest still goes out on your chosen frequency.
    </div>
  </div>
  <div class="card">
    <div class="card-title">Gmail delivery</div>
    <div style="margin-bottom:10px;">
      <label class="lbl">Primary Gmail address</label>
      <input type="email" id="main-email" placeholder="you@gmail.com">
    </div>
    <div>
      <label class="lbl">Additional recipients (comma-separated)</label>
      <input type="text" id="extra-rcpt" placeholder="spouse@gmail.com, parent@gmail.com">
    </div>
  </div>
</div>

<div class="save-bar">
  <span class="save-msg" id="save-msg">Your changes are saved when you click Save.</span>
  <button class="btn btn-save" onclick="saveProfile()">Save all changes</button>
</div>

<script>
var segs=[],segIdCtr=0,roomIdCtr=0,selFreq='every2days',selDays=['mon','wed','fri'],dirty=false;

document.querySelectorAll('.tab-btn').forEach(function(btn){
  btn.addEventListener('click',function(){
    document.querySelectorAll('.tab-btn').forEach(function(b){b.classList.remove('active');});
    document.querySelectorAll('.panel').forEach(function(p){p.classList.remove('active');});
    btn.classList.add('active');
    document.getElementById('tab-'+btn.getAttribute('data-tab')).classList.add('active');
  });
});

function markDirty(){
  dirty=true;
  var m=document.getElementById('save-msg');
  m.textContent='Unsaved changes — click Save to keep them.';
  m.className='save-msg';
}

document.getElementById('freq-chips').addEventListener('click',function(e){
  var btn=e.target.closest('.freq-chip');if(!btn)return;
  selFreq=btn.getAttribute('data-freq');
  document.querySelectorAll('.freq-chip').forEach(function(c){c.classList.toggle('sel',c===btn);});
  document.getElementById('custom-days-wrap').style.display=selFreq==='custom'?'block':'none';
  updateFreqPreview();markDirty();
});
document.getElementById('day-chips').addEventListener('click',function(e){
  var btn=e.target.closest('.day-chip');if(!btn)return;
  var day=btn.getAttribute('data-day'),idx=selDays.indexOf(day);
  if(idx>-1){selDays.splice(idx,1);btn.classList.remove('sel');}
  else{selDays.push(day);btn.classList.add('sel');}
  updateFreqPreview();markDirty();
});
document.getElementById('send-time').addEventListener('change',function(){updateFreqPreview();markDirty();});
document.getElementById('send-tz').addEventListener('change',function(){updateFreqPreview();markDirty();});

function updateFreqPreview(){
  var t=document.getElementById('send-time').value||'08:00';
  var tzMap={'America/Los_Angeles':'Pacific Time','America/New_York':'Eastern Time',
             'Europe/London':'London','Asia/Tokyo':'Tokyo'};
  var tz=tzMap[document.getElementById('send-tz').value]||'';
  var msgs={daily:'Every day',every2days:'Every 2 days',weekdays:'Monday-Friday',
            weekly:'Once a week (Monday)',
            custom:selDays.length?selDays.map(function(d){
              return d.charAt(0).toUpperCase()+d.slice(1);}).join(', '):'Select days below'};
  document.getElementById('freq-preview').textContent=(msgs[selFreq]||'')+' at '+t+' '+tz;
}
updateFreqPreview();

document.getElementById('thr-range').addEventListener('input',function(){
  var v=this.value;
  document.getElementById('thr-val').textContent=v+'%';
  document.getElementById('drop-lbl').textContent='> '+v+'% - email sent';
  document.getElementById('rise-lbl').textContent='> '+v+'% - email sent';
  markDirty();
});

['p-mid','p-lux','p-bud','p-large','p-light','p-step','p-lift','p-fam',
 'r-google','r-ta','r-veg','r-nin','r-area','r-senior'].forEach(function(id){
  var el=document.getElementById(id);if(el)el.addEventListener('change',markDirty);
});
document.getElementById('main-email').addEventListener('input',markDirty);
document.getElementById('extra-rcpt').addEventListener('input',markDirty);

function fmtDate(d){return d.toISOString().split('T')[0];}
function calcNights(ci,co){var d=Math.round((new Date(co)-new Date(ci))/86400000);return d>0?d:0;}
function getSeg(id){for(var i=0;i<segs.length;i++){if(segs[i].id===id)return segs[i];}return null;}
function getRoom(seg,rid){if(!seg)return null;for(var i=0;i<seg.rooms.length;i++){if(seg.rooms[i].id===rid)return seg.rooms[i];}return null;}

document.getElementById('add-city-btn').addEventListener('click',function(){addSeg(null);});

function addSeg(preset){
  var id=++segIdCtr;
  var today=new Date();
  var lastSeg=segs.length>0?segs[segs.length-1]:null;
  var defCi=lastSeg?lastSeg.co:fmtDate(today);
  var defCoD=new Date(defCi);defCoD.setDate(defCoD.getDate()+3);
  var rooms=preset&&preset.rooms?preset.rooms.map(function(r){
    return{id:++roomIdCtr,adults:r.adults||1,children:(r.children||[]).slice(),notes:r.notes||''};
  }):[{id:++roomIdCtr,adults:1,children:[],notes:''}];
  segs.push({id:id,city:preset?(preset.city||''):'',hotel:preset?(preset.hotel||''):'',
    ci:preset?(preset.ci||preset.check_in||fmtDate(today)):fmtDate(today),
    co:preset?(preset.co||preset.check_out||fmtDate(defCoD)):fmtDate(defCoD),
    tier:preset?(preset.tier||'midrange'):'midrange',rooms:rooms});
  var el=document.createElement('div');
  el.id='seg-'+id;
  document.getElementById('seg-list').appendChild(el);
  renderSeg(id);
  if(preset===null)markDirty();
}

function renderSeg(id){
  var seg=getSeg(id);if(!seg)return;
  var el=document.getElementById('seg-'+id);if(!el)return;
  var n=calcNights(seg.ci,seg.co);
  var canRm=segs.length>1;
  var roomsHTML='';
  for(var ri=0;ri<seg.rooms.length;ri++){
    var r=seg.rooms[ri];
    var childHTML='';
    for(var ci=0;ci<r.children.length;ci++){
      childHTML+='<div class="child-tag"><span>Child '+(ci+1)+' age</span>'
        +'<input type="number" min="0" max="17" value="'+r.children[ci]+'"'
        +' data-seg="'+id+'" data-room="'+r.id+'" data-cidx="'+ci+'" class="cage-inp">'
        +'<button class="rm cage-rm" data-seg="'+id+'" data-room="'+r.id+'" data-cidx="'+ci+'">x</button>'
        +'</div>';
    }
    roomsHTML+='<div class="room-card" id="room-'+id+'-'+r.id+'">'
      +'<div class="room-hdr"><span class="room-lbl">Room '+(ri+1)+'</span>'
      +(seg.rooms.length>1?'<button class="x-btn room-rm" data-seg="'+id+'" data-room="'+r.id+'">x</button>':'')
      +'</div>'
      +'<div class="g2" style="margin-bottom:8px;">'
      +'<div><label class="lbl">Adults</label><div class="gc" style="margin-top:4px;">'
      +'<button class="gc-btn adult-dec" data-seg="'+id+'" data-room="'+r.id+'">-</button>'
      +'<span class="gc-val" id="av-'+id+'-'+r.id+'">'+r.adults+'</span>'
      +'<button class="gc-btn adult-inc" data-seg="'+id+'" data-room="'+r.id+'">+</button>'
      +'</div></div>'
      +'<div><label class="lbl">Children</label><div class="gc" style="margin-top:4px;">'
      +'<button class="gc-btn child-dec" data-seg="'+id+'" data-room="'+r.id+'">-</button>'
      +'<span class="gc-val" id="cv-'+id+'-'+r.id+'">'+r.children.length+'</span>'
      +'<button class="gc-btn child-inc" data-seg="'+id+'" data-room="'+r.id+'">+</button>'
      +'</div></div></div>'
      +(r.children.length>0?'<div class="child-row">'+childHTML+'</div>':'')
      +'<div style="margin-top:8px;"><input type="text" class="rnotes-inp"'
      +' data-seg="'+id+'" data-room="'+r.id+'"'
      +' placeholder="Room notes e.g. twin beds, ground floor" value="'+(r.notes||'')+'"></div>'
      +'</div>';
  }
  el.className='seg';
  el.innerHTML=''
    +'<div class="seg-hdr"><div>'
    +'<span class="seg-name">'+(seg.city||'New city')+'</span>'
    +'<span class="nights-pill">'+n+' night'+(n!==1?'s':'')+'</span>'
    +'</div>'
    +(canRm?'<button class="x-btn seg-rm" data-seg="'+id+'">x</button>':'')
    +'</div>'
    +'<div class="slbl">City and hotel</div>'
    +'<div class="g2" style="margin-bottom:12px;">'
    +'<div><label class="lbl">City</label>'
    +'<input type="text" class="city-inp" data-seg="'+id+'" value="'+seg.city+'" placeholder="e.g. Tokyo"></div>'
    +'<div><label class="lbl">Hotel name (optional)</label>'
    +'<input type="text" class="hotel-inp" data-seg="'+id+'" value="'+(seg.hotel||'')+'" placeholder="Leave blank to search"></div>'
    +'</div>'
    +'<div class="slbl">Stay dates</div>'
    +'<div class="g3" style="margin-bottom:12px;">'
    +'<div><label class="lbl">Check-in</label>'
    +'<input type="date" class="ci-inp" data-seg="'+id+'" value="'+seg.ci+'"></div>'
    +'<div><label class="lbl">Check-out</label>'
    +'<input type="date" class="co-inp" data-seg="'+id+'" value="'+seg.co+'"></div>'
    +'<div><label class="lbl">Nights</label>'
    +'<input type="number" min="1" max="60" class="nights-inp" data-seg="'+id+'" value="'+n+'"></div>'
    +'</div>'
    +'<div class="slbl">Hotel tier</div>'
    +'<select class="tier-sel" data-seg="'+id+'" style="margin-bottom:14px;">'
    +'<option value="midrange"'+(seg.tier==='midrange'?' selected':'')+'>Mid-range</option>'
    +'<option value="luxury"'+(seg.tier==='luxury'?' selected':'')+'>Luxury</option>'
    +'<option value="budget"'+(seg.tier==='budget'?' selected':'')+'>Budget</option>'
    +'<option value="mixed"'+(seg.tier==='mixed'?' selected':'')+'>Mixed (mid-range + luxury)</option>'
    +'</select>'
    +'<div class="slbl">Rooms and guests</div>'
    +'<div id="rooms-'+id+'">'+roomsHTML+'</div>'
    +'<button class="add-room-btn" data-seg="'+id+'">+ Add another room</button>'
    +'<div class="sum-bar" id="sum-'+id+'"></div>';
  bindSeg(id);
  refreshSum(id);
}

function bindSeg(id){
  var el=document.getElementById('seg-'+id);if(!el)return;
  el.querySelector('.city-inp').addEventListener('input',function(){
    getSeg(id).city=this.value;
    var t=el.querySelector('.seg-name');if(t)t.textContent=this.value||'New city';
    markDirty();
  });
  el.querySelector('.hotel-inp').addEventListener('input',function(){getSeg(id).hotel=this.value;markDirty();});
  el.querySelector('.ci-inp').addEventListener('change',function(){getSeg(id).ci=this.value;updatePill(id);markDirty();});
  el.querySelector('.co-inp').addEventListener('change',function(){getSeg(id).co=this.value;updatePill(id);markDirty();});
  el.querySelector('.nights-inp').addEventListener('input',function(){
    var n=parseInt(this.value);if(!n||n<1)return;
    var seg=getSeg(id),co=new Date(seg.ci);
    co.setDate(co.getDate()+n);seg.co=fmtDate(co);
    var coI=el.querySelector('.co-inp');if(coI)coI.value=seg.co;
    var pill=el.querySelector('.nights-pill');if(pill)pill.textContent=n+' night'+(n!==1?'s':'');
    markDirty();
  });
  el.querySelector('.tier-sel').addEventListener('change',function(){getSeg(id).tier=this.value;markDirty();});
  var sr=el.querySelector('.seg-rm');
  if(sr)sr.addEventListener('click',function(){
    segs=segs.filter(function(s){return s.id!==id;});el.remove();markDirty();
  });
  el.querySelector('.add-room-btn').addEventListener('click',function(){
    getSeg(id).rooms.push({id:++roomIdCtr,adults:1,children:[],notes:''});
    renderSeg(id);markDirty();
  });
  el.querySelectorAll('.room-rm').forEach(function(btn){
    btn.addEventListener('click',function(){
      var rid=parseInt(this.getAttribute('data-room')),seg=getSeg(id);
      if(seg.rooms.length<=1)return;
      seg.rooms=seg.rooms.filter(function(r){return r.id!==rid;});
      renderSeg(id);markDirty();
    });
  });
  el.querySelectorAll('.adult-dec').forEach(function(btn){
    btn.addEventListener('click',function(){adjA(id,parseInt(this.getAttribute('data-room')),-1);});
  });
  el.querySelectorAll('.adult-inc').forEach(function(btn){
    btn.addEventListener('click',function(){adjA(id,parseInt(this.getAttribute('data-room')),1);});
  });
  el.querySelectorAll('.child-dec').forEach(function(btn){
    btn.addEventListener('click',function(){
      var seg=getSeg(id),r=getRoom(seg,parseInt(this.getAttribute('data-room')));
      if(r&&r.children.length>0){r.children.pop();renderSeg(id);markDirty();}
    });
  });
  el.querySelectorAll('.child-inc').forEach(function(btn){
    btn.addEventListener('click',function(){
      var seg=getSeg(id),r=getRoom(seg,parseInt(this.getAttribute('data-room')));
      if(r){r.children.push(0);renderSeg(id);markDirty();}
    });
  });
  el.querySelectorAll('.cage-rm').forEach(function(btn){
    btn.addEventListener('click',function(){
      var seg=getSeg(id),r=getRoom(seg,parseInt(this.getAttribute('data-room')));
      if(r){r.children.splice(parseInt(this.getAttribute('data-cidx')),1);renderSeg(id);markDirty();}
    });
  });
  el.querySelectorAll('.cage-inp').forEach(function(inp){
    inp.addEventListener('input',function(){
      var seg=getSeg(id),r=getRoom(seg,parseInt(this.getAttribute('data-room')));
      if(r){r.children[parseInt(this.getAttribute('data-cidx'))]=parseInt(this.value)||0;refreshSum(id);markDirty();}
    });
  });
  el.querySelectorAll('.rnotes-inp').forEach(function(inp){
    inp.addEventListener('input',function(){
      var seg=getSeg(id),r=getRoom(seg,parseInt(this.getAttribute('data-room')));
      if(r){r.notes=this.value;markDirty();}
    });
  });
}

function adjA(segId,rid,d){
  var seg=getSeg(segId),r=getRoom(seg,rid);if(!r)return;
  r.adults=Math.max(1,r.adults+d);
  var el=document.getElementById('av-'+segId+'-'+rid);if(el)el.textContent=r.adults;
  refreshSum(segId);markDirty();
}
function updatePill(id){
  var seg=getSeg(id);if(!seg)return;
  var el=document.getElementById('seg-'+id);if(!el)return;
  var n=calcNights(seg.ci,seg.co);
  var pill=el.querySelector('.nights-pill');if(pill)pill.textContent=n+' night'+(n!==1?'s':'');
  var ni=el.querySelector('.nights-inp');if(ni)ni.value=n;
}
function refreshSum(id){
  var seg=getSeg(id);if(!seg)return;
  var el=document.getElementById('sum-'+id);if(!el)return;
  var totA=0,allKids=[],lines=[];
  for(var i=0;i<seg.rooms.length;i++){
    var r=seg.rooms[i];totA+=r.adults;
    for(var j=0;j<r.children.length;j++)allKids.push(r.children[j]);
    var line='Room '+(i+1)+': '+r.adults+' adult'+(r.adults!==1?'s':'');
    if(r.children.length>0)line+=', '+r.children.length+' child'+(r.children.length>1?'ren':'')
      +' (ages: '+r.children.join(', ')+')';
    lines.push(line);
  }
  var top='<b>'+seg.rooms.length+'</b> room'+(seg.rooms.length>1?'s':'')+', <b>'+totA+'</b> adult'+(totA!==1?'s':'');
  if(allKids.length>0)top+=', <b>'+allKids.length+'</b> child'+(allKids.length>1?'ren':'')+' (ages: '+allKids.join(', ')+')';
  el.innerHTML=top+'<br><span style="font-size:11px;">'+lines.join(' | ')+'</span>';
}

function collectProfile(){
  return{
    segs:segs.map(function(seg){
      return{city:seg.city,hotel:seg.hotel,ci:seg.ci,co:seg.co,
        check_in:seg.ci,check_out:seg.co,nights:calcNights(seg.ci,seg.co),tier:seg.tier,
        rooms:seg.rooms.map(function(r,i){
          return{room:i+1,adults:r.adults,children:r.children.slice(),notes:r.notes||''};
        })};
    }),
    prefs:{
      midrange:document.getElementById('p-mid').checked,
      luxury:document.getElementById('p-lux').checked,
      budget:document.getElementById('p-bud').checked,
      largeRooms:document.getElementById('p-large').checked,
      naturalLight:document.getElementById('p-light').checked,
      stepFree:document.getElementById('p-step').checked,
      elevator:document.getElementById('p-lift').checked,
      familyRooms:document.getElementById('p-fam').checked,
      googleMin:document.getElementById('r-google').checked,
      taMin:document.getElementById('r-ta').checked,
      vegetarian:document.getElementById('r-veg').checked,
      nintendo:document.getElementById('r-nin').checked,
      areaInfo:document.getElementById('r-area').checked,
      seniors:document.getElementById('r-senior').checked,
    },
    freq:selFreq,customDays:selDays.slice(),
    sendTime:document.getElementById('send-time').value,
    timezone:document.getElementById('send-tz').value,
    threshold:parseInt(document.getElementById('thr-range').value),
    email:document.getElementById('main-email').value,
    extraRecipients:document.getElementById('extra-rcpt').value,
  };
}

function applyProfile(profile){
  if(!profile||Object.keys(profile).length===0)return;
  segs=[];document.getElementById('seg-list').innerHTML='';
  var saved=profile.segs||[];
  if(saved.length>0){saved.forEach(function(s){addSeg(s);});}
  else{addSeg(null);}
  var pr=profile.prefs||{};
  function setChk(id,val){var el=document.getElementById(id);if(el&&val!==undefined)el.checked=val;}
  setChk('p-mid',pr.midrange);setChk('p-lux',pr.luxury);setChk('p-bud',pr.budget);
  setChk('p-large',pr.largeRooms);setChk('p-light',pr.naturalLight);
  setChk('p-step',pr.stepFree);setChk('p-lift',pr.elevator);setChk('p-fam',pr.familyRooms);
  setChk('r-google',pr.googleMin);setChk('r-ta',pr.taMin);setChk('r-veg',pr.vegetarian);
  setChk('r-nin',pr.nintendo);setChk('r-area',pr.areaInfo);setChk('r-senior',pr.seniors);
  if(profile.freq){
    selFreq=profile.freq;
    document.querySelectorAll('.freq-chip').forEach(function(c){
      c.classList.toggle('sel',c.getAttribute('data-freq')===selFreq);
    });
    document.getElementById('custom-days-wrap').style.display=selFreq==='custom'?'block':'none';
  }
  if(profile.customDays){
    selDays=profile.customDays.slice();
    document.querySelectorAll('.day-chip').forEach(function(c){
      c.classList.toggle('sel',selDays.indexOf(c.getAttribute('data-day'))>-1);
    });
  }
  if(profile.sendTime)document.getElementById('send-time').value=profile.sendTime;
  if(profile.timezone)document.getElementById('send-tz').value=profile.timezone;
  if(profile.threshold){
    document.getElementById('thr-range').value=profile.threshold;
    document.getElementById('thr-val').textContent=profile.threshold+'%';
    document.getElementById('drop-lbl').textContent='> '+profile.threshold+'% - email sent';
    document.getElementById('rise-lbl').textContent='> '+profile.threshold+'% - email sent';
  }
  if(profile.email)document.getElementById('main-email').value=profile.email;
  if(profile.extraRecipients)document.getElementById('extra-rcpt').value=profile.extraRecipients;
  updateFreqPreview();
}

function saveProfile(){
  fetch('/save_profile',{
    method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify(collectProfile())
  })
  .then(function(r){return r.json();})
  .then(function(d){
    if(d.status==='saved'){
      dirty=false;
      var m=document.getElementById('save-msg');
      m.textContent='All changes saved at '+new Date().toLocaleTimeString();
      m.className='save-msg ok';
    }
  })
  .catch(function(){
    var m=document.getElementById('save-msg');
    m.textContent='Save failed - please try again.';
    m.className='save-msg err';
  });
}
document.getElementById('hdr-save-btn').addEventListener('click',saveProfile);

function triggerRefresh(){
  saveProfile();
  var btn=document.getElementById('refresh-btn');
  var status=document.getElementById('refresh-status');
  btn.textContent='Refreshing...';btn.disabled=true;
  status.textContent='Fetching prices - this takes about 30 seconds...';
  fetch('/refresh')
    .then(function(r){return r.json();})
    .then(function(){setTimeout(function(){location.reload();},35000);})
    .catch(function(){
      btn.textContent='Refresh prices';btn.disabled=false;
      status.textContent='Error - check API keys in Railway Variables.';
    });
}

window.addEventListener('beforeunload',function(e){if(dirty){e.preventDefault();e.returnValue='';}});

fetch('/load_profile')
  .then(function(r){return r.json();})
  .then(function(profile){
    applyProfile(profile);
    dirty=false;
    var m=document.getElementById('save-msg');
    if(profile&&Object.keys(profile).length>0){
      m.textContent='Profile loaded.';m.className='save-msg ok';
    }
  })
  .catch(function(){addSeg(null);});
</script>
</body>
</html>"""

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"Starting Hotel Tracker on port {port}")
    app.run(host="0.0.0.0", port=port, debug=False)