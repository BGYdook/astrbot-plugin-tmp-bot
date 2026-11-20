"""HTML and JavaScript templates for AstrBot image rendering."""

RANK_IMAGE_TEMPLATE = """
<style>
  html, body {
    width: 760px;
    margin: 0;
    padding: 0;
    background: #070b12;
  }
  * { box-sizing: border-box; }
  .board {
    --accent: #55e0b0;
    --accent-soft: rgba(85, 224, 176, .16);
    --accent-line: rgba(85, 224, 176, .42);
    position: relative;
    width: 760px;
    overflow: hidden;
    padding: 28px 28px 24px;
    color: #f7f9fc;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    background:
      radial-gradient(circle at 90% 4%, rgba(65, 171, 255, .18), transparent 28%),
      radial-gradient(circle at 5% 48%, rgba(85, 224, 176, .12), transparent 30%),
      linear-gradient(150deg, #0d1523 0%, #09101b 48%, #070b12 100%);
  }
  .board.today {
    --accent: #ffbd63;
    --accent-soft: rgba(255, 189, 99, .16);
    --accent-line: rgba(255, 189, 99, .42);
  }
  .board::before {
    content: "";
    position: absolute;
    inset: 0;
    pointer-events: none;
    opacity: .34;
    background-image:
      linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
    background-size: 38px 38px;
    mask-image: linear-gradient(to bottom, black, transparent 78%);
  }
  .road-mark {
    position: absolute;
    right: -88px;
    top: 105px;
    width: 260px;
    height: 420px;
    border: 1px solid rgba(255,255,255,.07);
    border-radius: 50%;
    transform: rotate(24deg);
  }
  .road-mark::before,
  .road-mark::after {
    content: "";
    position: absolute;
    inset: 26px;
    border: 1px dashed rgba(255,255,255,.09);
    border-radius: 50%;
  }
  .road-mark::after { inset: 70px; }
  .hero {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: flex-start;
    justify-content: space-between;
    gap: 22px;
    padding-bottom: 22px;
    border-bottom: 1px solid rgba(255,255,255,.1);
  }
  .brand { display: flex; align-items: center; gap: 15px; min-width: 0; }
  .brand-mark {
    width: 54px;
    height: 54px;
    flex: 0 0 54px;
    display: grid;
    place-items: center;
    border-radius: 17px;
    color: #07121a;
    font-size: 16px;
    font-weight: 900;
    letter-spacing: .5px;
    background: linear-gradient(145deg, var(--accent), #e9fff8);
    box-shadow: 0 10px 30px var(--accent-soft);
  }
  .eyebrow {
    margin-bottom: 5px;
    color: var(--accent);
    font-size: 11px;
    font-weight: 800;
    letter-spacing: 2.6px;
    text-transform: uppercase;
  }
  h1 {
    margin: 0;
    font-size: 30px;
    line-height: 1.15;
    font-weight: 800;
    letter-spacing: -.8px;
  }
  .hero-meta {
    flex: 0 0 auto;
    text-align: right;
    padding-top: 3px;
  }
  .hero-meta strong {
    display: block;
    color: #fff;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 23px;
    line-height: 1;
    letter-spacing: -.5px;
  }
  .hero-meta span {
    display: block;
    margin-top: 6px;
    color: #8190a5;
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.8px;
  }
  .section-label {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    gap: 9px;
    margin: 18px 2px 10px;
    color: #8592a5;
    font-size: 10px;
    font-weight: 800;
    letter-spacing: 2.2px;
  }
  .section-label::after {
    content: "";
    height: 1px;
    flex: 1;
    background: linear-gradient(90deg, rgba(255,255,255,.13), transparent);
  }
  .champion,
  .runner-card,
  .row,
  .me-card {
    position: relative;
    z-index: 1;
    overflow: hidden;
    border: 1px solid rgba(255,255,255,.09);
    background: rgba(18, 28, 43, .88);
    box-shadow: 0 12px 34px rgba(0,0,0,.19);
  }
  .champion {
    display: grid;
    grid-template-columns: 76px minmax(0, 1fr) auto;
    align-items: center;
    gap: 17px;
    padding: 19px 21px;
    border-radius: 18px;
    border-color: rgba(246, 196, 83, .42);
    background:
      linear-gradient(110deg, rgba(246,196,83,.17), rgba(246,196,83,.035) 46%, rgba(18,28,43,.92)),
      rgba(18,28,43,.95);
  }
  .champion::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 4px;
    background: linear-gradient(#ffe49b, #f0a72f);
    box-shadow: 0 0 22px rgba(246,196,83,.7);
  }
  .champion::after {
    content: "01";
    position: absolute;
    right: 14px;
    bottom: -18px;
    color: rgba(255,255,255,.035);
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 92px;
    font-weight: 900;
    letter-spacing: -8px;
  }
  .medal {
    width: 60px;
    height: 60px;
    display: grid;
    place-items: center;
    border-radius: 18px;
    border: 1px solid rgba(255,255,255,.16);
    background: rgba(255,255,255,.08);
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 24px;
    font-weight: 900;
  }
  .champion .medal {
    color: #191204;
    border: 0;
    background: linear-gradient(145deg, #ffe7a2, #e7a531);
    box-shadow: 0 9px 24px rgba(240,167,47,.27);
  }
  .player { min-width: 0; }
  .player-name {
    overflow: hidden;
    color: #f8fafc;
    font-size: 18px;
    font-weight: 800;
    line-height: 1.25;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .player-id {
    margin-top: 4px;
    color: #8190a5;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 10px;
    letter-spacing: .7px;
  }
  .mileage {
    position: relative;
    z-index: 1;
    text-align: right;
    white-space: nowrap;
  }
  .mileage strong {
    display: block;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 22px;
    line-height: 1;
    font-variant-numeric: tabular-nums;
  }
  .mileage span {
    display: block;
    margin-top: 5px;
    color: #8290a3;
    font-size: 9px;
    font-weight: 800;
    letter-spacing: 1.6px;
  }
  .runner-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 10px;
    margin-top: 10px;
  }
  .runner-card {
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr);
    align-items: center;
    gap: 12px;
    padding: 14px;
    border-radius: 15px;
  }
  .runner-card.silver { border-color: rgba(194,207,222,.28); }
  .runner-card.bronze { border-color: rgba(226,153,91,.28); }
  .runner-card .medal { width: 44px; height: 44px; border-radius: 14px; font-size: 17px; }
  .runner-card.silver .medal { color: #17212d; background: linear-gradient(145deg, #edf3f9, #aab9ca); }
  .runner-card.bronze .medal { color: #24150a; background: linear-gradient(145deg, #f3bd8c, #c9783d); }
  .runner-card .player-name { font-size: 14px; }
  .runner-card .mileage { grid-column: 2; text-align: left; margin-top: -4px; }
  .runner-card .mileage strong { color: #dce5f0; font-size: 15px; }
  .runner-card .mileage span { display: none; }
  .rows { display: grid; gap: 7px; }
  .row {
    display: grid;
    grid-template-columns: 40px minmax(0, 1fr) auto;
    align-items: center;
    gap: 12px;
    padding: 11px 14px;
    border-radius: 12px;
    background: rgba(17, 27, 41, .74);
  }
  .row-rank {
    color: #8c9aae;
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 13px;
    font-weight: 800;
  }
  .row .player-name { font-size: 14px; font-weight: 700; }
  .row .player-id { margin-top: 2px; }
  .row .mileage strong { font-size: 14px; }
  .me-card {
    display: grid;
    grid-template-columns: minmax(0, 1fr) auto;
    gap: 16px;
    margin-top: 18px;
    padding: 15px 17px;
    border-radius: 16px;
    border-color: var(--accent-line);
    background:
      linear-gradient(105deg, var(--accent-soft), rgba(16,26,40,.88) 72%),
      rgba(16,26,40,.95);
    box-shadow: inset 0 0 0 1px var(--accent-soft);
  }
  .me-label {
    margin-bottom: 6px;
    color: var(--accent);
    font-size: 9px;
    font-weight: 900;
    letter-spacing: 2.2px;
  }
  .me-name { font-size: 15px; font-weight: 800; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .me-sub { margin-top: 5px; color: #8d9aad; font-size: 11px; }
  .me-values { text-align: right; white-space: nowrap; }
  .me-values strong {
    display: block;
    color: var(--accent);
    font-family: "Cascadia Mono", Consolas, monospace;
    font-size: 19px;
  }
  .me-values span {
    display: block;
    margin-top: 4px;
    color: #c3cedd;
    font-size: 11px;
    font-weight: 700;
  }
  .footer {
    position: relative;
    z-index: 1;
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-top: 15px;
    padding-top: 12px;
    border-top: 1px solid rgba(255,255,255,.08);
    color: #59677a;
    font-size: 9px;
    font-weight: 700;
    letter-spacing: 1.1px;
  }
  .footer b { color: var(--accent); font-weight: 800; }
</style>
<div class="board {{ 'today' if is_today else 'total' }}">
  <div class="road-mark"></div>
  <header class="hero">
    <div class="brand">
      <div class="brand-mark">TMP</div>
      <div>
        <div class="eyebrow">TRUCKERSMP · ETS2</div>
        <h1>{{ title|e }}</h1>
      </div>
    </div>
    <div class="hero-meta">
      <strong>TOP 10</strong>
      <span>{{ subtitle|e }}</span>
    </div>
  </header>

  {% if items|length > 0 %}
  <div class="section-label">CHAMPION</div>
  <div class="champion">
    <div class="medal">01</div>
    <div class="player">
      <div class="player-name">{{ items[0].name|e }}</div>
      <div class="player-id">TMP ID · {{ items[0].tmp_id|e }}</div>
    </div>
    <div class="mileage">
      <strong>{{ items[0].km_text|e }}</strong>
      <span>KILOMETERS</span>
    </div>
  </div>
  {% endif %}

  {% if items|length > 1 %}
  <div class="runner-grid">
    <div class="runner-card silver">
      <div class="medal">02</div>
      <div>
        <div class="player-name">{{ items[1].name|e }}</div>
        <div class="player-id">TMP ID · {{ items[1].tmp_id|e }}</div>
      </div>
      <div class="mileage"><strong>{{ items[1].km_text|e }}</strong><span>KM</span></div>
    </div>
    {% if items|length > 2 %}
    <div class="runner-card bronze">
      <div class="medal">03</div>
      <div>
        <div class="player-name">{{ items[2].name|e }}</div>
        <div class="player-id">TMP ID · {{ items[2].tmp_id|e }}</div>
      </div>
      <div class="mileage"><strong>{{ items[2].km_text|e }}</strong><span>KM</span></div>
    </div>
    {% endif %}
  </div>
  {% endif %}

  {% set remaining = items|length - 3 %}
  {% if remaining > 0 %}
  <div class="section-label">LEADERBOARD · 04–{{ items|length }}</div>
  <div class="rows">
    {% for it in items if it.rank > 3 %}
    <div class="row">
      <div class="row-rank">{{ ('%02d' % it.rank)|e }}</div>
      <div>
        <div class="player-name">{{ it.name|e }}</div>
        <div class="player-id">TMP ID · {{ it.tmp_id|e }}</div>
      </div>
      <div class="mileage"><strong>{{ it.km_text|e }}</strong><span>KM</span></div>
    </div>
    {% endfor %}
  </div>
  {% endif %}

  {% if me %}
  <div class="me-card">
    <div>
      <div class="me-label">MY POSITION</div>
      <div class="me-name">{{ me.name|e }}</div>
      <div class="me-sub">TMP ID · {{ me.tmp_id|e }}{% if me.vtc_role %} · {{ me.vtc_role|e }}{% endif %}</div>
    </div>
    <div class="me-values">
      <strong>{{ me.km_text|e }} KM</strong>
      <span>{% if me.rank is not none %}RANK #{{ me.rank|e }}{% else %}{{ scope|e }}{% endif %}</span>
    </div>
  </div>
  {% endif %}

  <footer class="footer">
    <span><b>LIVE DATA</b> · TRUCKERSMP MILEAGE</span>
    <span>{{ scope|e }} · TOP 10</span>
  </footer>
</div>
"""


LOCATION_TEMPLATE = """
<link rel=\"stylesheet\" href=\"https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css\">
<script src=\"https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js\"></script>
<style>
  html, body { margin:0; padding:0; width:1280px; height:720px; overflow:hidden; background:#244b63; }
  * { box-sizing:border-box; }
  body { font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif; }
  .shell { position:relative; width:1280px; height:720px; overflow:hidden; color:#f5fbfa; background:#244b63; }
  #map { position:absolute; inset:0; background:radial-gradient(circle at 52% 42%,#365f76 0,#294f66 52%,#1b3b51 100%); }
  #map .leaflet-tile-pane { opacity:.82; filter:grayscale(1) brightness(1.75) contrast(1.12); mix-blend-mode:screen; }
  #map .leaflet-image-layer { opacity:.82; filter:grayscale(1) brightness(1.75) contrast(1.12); mix-blend-mode:screen; }
  .leaflet-control-container { display:none; }
  .map-shade {
    position:absolute; inset:0; z-index:450; pointer-events:none;
    background:
      linear-gradient(180deg,rgba(7,29,45,.15),transparent 24%,transparent 66%,rgba(7,29,45,.42)),
      radial-gradient(circle at 50% 45%,transparent 48%,rgba(8,30,45,.22));
  }
  .live-pill {
    position:absolute; z-index:700; top:24px; left:26px; height:40px; padding:0 14px;
    display:flex; align-items:center; gap:9px; border:1px solid rgba(255,255,255,.18);
    border-radius:11px; color:#edf7fb; background:rgba(8,31,48,.8);
    backdrop-filter:blur(10px); box-shadow:0 10px 24px rgba(0,0,0,.18);
    font-size:11px; font-weight:800; letter-spacing:1px;
  }
  .live-dot {
    width:8px; height:8px; border-radius:50%; background:#69d9ff;
    box-shadow:0 0 0 4px rgba(105,217,255,.15),0 0 14px rgba(105,217,255,.75);
  }
  .server-pill {
    position:absolute; z-index:700; top:24px; right:26px; height:40px; padding:0 14px;
    display:flex; align-items:center; gap:8px; border:1px solid rgba(255,255,255,.17);
    border-radius:11px; color:#dfecef; background:rgba(8,31,48,.8);
    backdrop-filter:blur(10px); box-shadow:0 10px 24px rgba(0,0,0,.18);
    font-size:11px; font-weight:700;
  }
  .server-pill::before { content:""; width:7px; height:7px; border-radius:50%; background:#59c98d; }
  .self-ring {
    width:48px; height:48px; display:grid; place-items:center; border-radius:50%;
    border:1px solid rgba(112,229,183,.45); background:rgba(80,199,154,.1);
    box-shadow:0 0 0 9px rgba(80,199,154,.08);
  }
  .self-ring::after {
    content:""; width:15px; height:15px; border-radius:50%;
    border:3px solid #f7fffc; background:#59c98d; box-shadow:0 4px 12px rgba(0,0,0,.35);
  }
  .panel {
    position:absolute; z-index:900; left:24px; right:24px; bottom:20px; height:112px;
    padding:0 25px; display:grid; grid-template-columns:minmax(0,1fr) 520px;
    gap:24px; align-items:center; border:1px solid rgba(255,255,255,.16); border-radius:19px;
    background:linear-gradient(105deg,rgba(7,28,45,.95),rgba(8,36,55,.9));
    box-shadow:0 18px 45px rgba(6,25,39,.35); backdrop-filter:blur(14px);
  }
  .panel::before {
    content:""; position:absolute; left:22px; right:22px; top:0; height:1px;
    background:linear-gradient(90deg,transparent,rgba(121,213,255,.7),transparent);
  }
  .profile { min-width:0; display:flex; align-items:center; gap:15px; }
  .avatar-wrap {
    width:70px; height:70px; flex:0 0 70px; padding:4px; border-radius:50%;
    background:linear-gradient(145deg,#6bcfff,#267cad); box-shadow:0 8px 22px rgba(2,16,27,.38);
  }
  .avatar { width:62px; height:62px; display:block; border:3px solid #102f45; border-radius:50%; object-fit:cover; background:#d8e0e3; }
  .avatar-fallback {
    width:62px; height:62px; display:flex; align-items:center; justify-content:center;
    border:3px solid #102f45; border-radius:50%; color:#f8fffd;
    background:linear-gradient(145deg,#237ca8,#123d59); font-size:24px; font-weight:800;
  }
  .profile-copy { min-width:0; }
  .profile-kicker { margin-bottom:5px; color:#8bb1c3; font-size:9px; font-weight:800; letter-spacing:1.4px; }
  .name {
    max-width:330px; overflow:hidden; color:#f7fbfc; font-size:23px; line-height:1.15;
    font-weight:800; letter-spacing:-.4px; text-overflow:ellipsis; white-space:nowrap;
  }
  .chips { display:flex; align-items:center; gap:6px; margin-top:8px; }
  .chip {
    display:inline-flex; align-items:center; height:21px; padding:0 8px; border-radius:6px;
    color:#c1d8e3; background:rgba(255,255,255,.08); font-size:9px; font-weight:700;
  }
  .chip.server { color:#7ce0b1; background:rgba(83,199,143,.13); }
  .location-card { min-width:0; text-align:right; }
  .location-label { color:#89a5b3; font-size:9px; font-weight:800; letter-spacing:1.4px; }
  .location-value {
    margin-top:6px; overflow:hidden; color:#f6fbfc; font-size:21px; line-height:1.2;
    font-weight:800; text-overflow:ellipsis; white-space:nowrap;
  }
  .direction {
    display:flex; justify-content:flex-end; align-items:center; gap:7px;
    margin-top:7px; color:#7dd9b0; font-size:11px; font-weight:700;
  }
  .direction::before { content:""; width:6px; height:6px; border-radius:50%; background:#59c98d; }
</style>
<div class=\"shell\">
  <div id=\"map\"></div>
  <div class=\"map-shade\"></div>
  <div class=\"live-pill\"><span class=\"live-dot\"></span>在线位置</div>
  <div class=\"server-pill\">{{ server_name|e }} · 游戏中</div>
  <div class=\"panel\">
    <div class=\"profile\">
      <div class=\"avatar-wrap\">
        {% if avatar %}<img class=\"avatar\" src=\"{{ avatar|e }}\" />{% else %}<div class=\"avatar-fallback\">{{ avatar_initial|e }}</div>{% endif %}
      </div>
      <div class=\"profile-copy\">
        <div class=\"profile-kicker\">DRIVER LOCATION</div>
        <div class=\"name\">{{ player_name|e }}</div>
        <div class=\"chips\">
          <span class=\"chip server\">{{ server_name|e }}</span>
          <span class=\"chip\">TMP #{{ me_id|e }}</span>
          <span class=\"chip\">附近 {{ nearby_count|e }} 人</span>
        </div>
      </div>
    </div>
    <div class=\"location-card\">
      <div class=\"location-label\">当前位置</div>
      <div class=\"location-value\">{{ location_line|e }}</div>
      {% if direction_text %}<div class=\"direction\">{{ direction_text|e }}</div>{% endif %}
    </div>
  </div>
</div>
<script>
  var promodsIds = [50, 51];
  var serverId = {{ server_id }};
  var mapType = promodsIds.indexOf(serverId) !== -1 ? 'promods' : 'ets';
  var cfg = {{ map_profiles|tojson }};
  function project(xx, yy, profile) {
    if (profile.trackerTiles) {
      if (profile.ukCorrection && xx < -30100 && yy < -0.14*xx-10040 && yy > -86000) {
        xx = 0.75*xx-8337;
        yy = 0.75*yy-1000;
      }
      return [xx*profile.pixelScale, yy*profile.pixelScale];
    }
    if (profile.extent) {
      var e = profile.extent;
      return [(xx-e[0])/(e[1]-e[0])*profile.bounds.x,
              (yy-e[2])/(e[3]-e[2])*profile.bounds.y];
    }
    return [xx/profile.scale+profile.origin[0], yy/profile.scale+profile.origin[1]];
  }

  var map = L.map('map', { attributionControl: false, crs: L.CRS.Simple, zoomControl: false, zoomSnap: 0.2, zoomDelta: 0.2 });
  var centerX = {{ center_x }};
  var centerY = {{ center_y }};
  var players = {{ players|tojson }};
  var markers = L.layerGroup().addTo(map);
  var tileLayer = null;
  function applyProfile(c) {
    if (tileLayer) map.removeLayer(tileLayer);
    markers.clearLayers();
    var b = c.trackerTiles ? L.latLngBounds(
      map.unproject([c.world[0]*c.pixelScale, c.world[3]*c.pixelScale], c.maxZoom),
      map.unproject([c.world[2]*c.pixelScale, c.world[1]*c.pixelScale], c.maxZoom)
    ) : L.latLngBounds(
      map.unproject([0, c.bounds.y], c.maxZoom),
      map.unproject([c.bounds.x, 0], c.maxZoom)
    );
    map.setMaxBounds(b);
    var switched = false;
    function useFallback() {
      if (switched || !c.fallback) return;
      switched = true;
      applyProfile(c.fallback);
    }
    if (c.trackerTiles) {
      tileLayer = L.layerGroup().addTo(map);
      c.images.forEach(function(tile) {
        var bounds = L.latLngBounds(
          map.unproject([tile.left*c.pixelScale, (tile.top+1000)*c.pixelScale], c.maxZoom),
          map.unproject([(tile.left+1000)*c.pixelScale, tile.top*c.pixelScale], c.maxZoom)
        );
        L.imageOverlay(tile.url, bounds, {interactive:false}).on('error', useFallback).addTo(tileLayer);
      });
    } else {
      tileLayer = L.tileLayer(c.tileUrl, { minZoom:c.minZoom, maxZoom:10, maxNativeZoom:c.maxZoom, tileSize:c.tileSize, bounds:b, reuseTiles:true }).on('tileerror', useFallback).addTo(map);
    }
    players.forEach(function(p) {
      if (p.tmpId === {{ me_id|tojson }}) return;
      var latlng = map.unproject(project(p.axisX, p.axisY, c), c.maxZoom);
      L.circleMarker(latlng, { color:'#c9f3ff', weight:1, opacity:.5, fillColor:'#69bce8', fillOpacity:.72, radius:4 }).addTo(markers);
    });
    var meLL = map.unproject(project(centerX, centerY, c), c.maxZoom);
    L.circleMarker(meLL, { color:'#8de4b0', weight:1, opacity:.25, fillColor:'#59c98d', fillOpacity:.08, radius:25 }).addTo(markers);
    L.marker(meLL, {
      interactive:false,
      icon:L.divIcon({className:'',html:'<div class=\"self-ring\"></div>',iconSize:[48,48],iconAnchor:[24,24]})
    }).addTo(markers);
    // 256px tiles use one more zoom level to retain the previous visual scale.
    map.setView(meLL, c.viewZoom !== undefined ? c.viewZoom : (c.tileSize === 256 ? 9 : 8));
  }
  applyProfile(cfg[mapType]);
  setTimeout(function(){ map.invalidateSize(); }, 80);
</script>
"""


FOOTPRINT_TEMPLATE = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin:0; padding:0; width:1280px; height:720px; background:#244b63; overflow:hidden; }
  * { box-sizing:border-box; }
  body { font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif; }
  .shell { position:relative; width:1280px; height:720px; overflow:hidden; color:#f5fbfa; background:#244b63; }
  .map-stage { position:relative; width:100%; height:100%; overflow:hidden; background:radial-gradient(circle at 52% 40%,#365f76 0,#294f66 52%,#1b3b51 100%); }
  #map { position:absolute; inset:0; background:transparent; }
  #map .leaflet-tile-pane {
    opacity:.82; filter:grayscale(1) brightness(1.75) contrast(1.12);
    mix-blend-mode:screen;
  }
  .leaflet-control-container { display:none; }
  .map-stage::after {
    content:""; position:absolute; inset:0; z-index:450; pointer-events:none;
    background:
      linear-gradient(180deg,rgba(7,29,45,.18) 0,rgba(7,29,45,0) 22%,rgba(7,29,45,0) 66%,rgba(7,29,45,.38) 100%),
      radial-gradient(circle at 52% 45%,transparent 50%,rgba(8,30,45,.24) 100%);
  }
  .route-tooltip {
    border:none!important; border-radius:9px!important; background:#f8f6ef!important; color:#172625!important;
    box-shadow:0 8px 22px rgba(0,0,0,.2)!important; font-size:11px!important; font-weight:700!important;
  }
  .route-tooltip::before { border-top-color:#f8f6ef!important; }
  .panel {
    position:absolute; z-index:900; left:28px; right:28px; bottom:24px; height:112px;
    padding:0 28px; display:grid; grid-template-columns:minmax(0,1fr) 280px;
    gap:18px; align-items:center; border:1px solid rgba(255,255,255,.16); border-radius:20px;
    background:linear-gradient(105deg,rgba(7,28,45,.94),rgba(8,36,55,.88));
    box-shadow:0 18px 45px rgba(6,25,39,.34); backdrop-filter:blur(14px);
  }
  .panel::before {
    content:""; position:absolute; left:22px; right:22px; top:0; height:1px;
    background:linear-gradient(90deg,transparent,rgba(121,213,255,.7),transparent);
  }
  .profile { min-width:0; display:flex; align-items:center; gap:15px; }
  .avatar-wrap {
    width:72px; height:72px; flex:0 0 72px; padding:4px; border-radius:50%;
    background:linear-gradient(145deg,#6bcfff,#267cad); box-shadow:0 8px 22px rgba(2,16,27,.38);
  }
  .avatar {
    width:64px; height:64px; display:block; border:3px solid #102f45; border-radius:50%;
    object-fit:cover; background:#d9e0dc;
  }
  .avatar-fallback {
    width:64px; height:64px; display:flex; align-items:center; justify-content:center;
    border:3px solid #102f45; border-radius:50%; color:#f8fffd;
    background:linear-gradient(145deg,#237ca8,#123d59); font-size:26px; font-weight:800;
  }
  .profile-copy { min-width:0; flex:1; }
  .profile-kicker { margin-bottom:5px; color:#8bb1c3; font-size:10px; font-weight:800; letter-spacing:1.35px; }
  .name-line { display:flex; align-items:baseline; min-width:0; max-width:100%; }
  .name {
    min-width:0; max-width:380px; overflow:hidden; color:#f7fbfc; font-size:24px; line-height:1.18;
    font-weight:800; letter-spacing:-.4px; text-overflow:ellipsis; white-space:nowrap;
  }
  .name-suffix { flex:0 0 auto; color:#afc8d4; font-size:17px; font-weight:600; letter-spacing:0; white-space:nowrap; }
  .chips { display:flex; align-items:center; gap:7px; margin-top:8px; }
  .chip {
    display:inline-flex; align-items:center; height:22px; padding:0 9px; border-radius:7px;
    color:#c1d8e3; background:rgba(255,255,255,.08); font-size:10px; font-weight:700; letter-spacing:.35px;
  }
  .chip.server { color:#78ddae; background:rgba(83,199,143,.13); }
  .mileage { display:flex; align-items:baseline; justify-content:flex-end; gap:16px; white-space:nowrap; }
  .mileage span { color:#9bb6c4; font-size:14px; font-weight:600; }
  .mileage strong { color:#8de4b0; font-size:29px; line-height:1; font-weight:800; letter-spacing:-.6px; }
  .mileage small { margin-left:5px; color:#a7c6b7; font-size:13px; font-weight:600; letter-spacing:0; }
</style>
<div class="shell">
  <div class="map-stage">
    <div id="map"></div>
  </div>
  <div class="panel">
    <div class="profile">
      <div class="avatar-wrap">
        {% if avatar %}
        <img class="avatar" src="{{ avatar|e }}" />
        {% else %}
        <div class="avatar-fallback">{{ avatar_initial|e }}</div>
        {% endif %}
      </div>
      <div class="profile-copy">
        <div class="profile-kicker">DRIVER JOURNEY</div>
        <div class="name-line">
          <div class="name">{{ player_name|e }}</div>
          <span class="name-suffix"> 的今日行驶足迹</span>
        </div>
        <div class="chips">
          <span class="chip server">{{ server_label|e }}</span>
          <span class="chip">TMP #{{ tmp_id|e }}</span>
        </div>
      </div>
    </div>
    <div class="mileage">
      <span>今日里程</span>
      <strong>
        {% if distance_km is not none %}{{ '%.1f' % distance_km }}<small>km</small>{% else %}暂无记录{% endif %}
      </strong>
    </div>
  </div>
</div>
<script>
  var mapType = {{ map_type|tojson }};
  var cfg = {
    ets: {
      tileUrl: {{ tile_url_ets|tojson }},
      fallbackUrl: 'https://ets_tiles.cnly.top/20260903/tmp-ets-yellow/Tiles/{z}/{x}/{y}.png',
      breakpoints: { uk: { x: -31056.8, y: -5832.867 } },
      bounds: { x:131072, y:131072 },
      maxZoom: 8, minZoom: 2,
      calc: function(xx, yy) {
        var x1 = -113177.305, x2 = 97925.63, y1 = -122648.086, y2 = 88454.85;
        return [ (xx - x1) / (x2 - x1) * 131072, (yy - y1) / (y2 - y1) * 131072 ];
      }
    },
    promods: {
      tileUrl: {{ tile_url_promods|tojson }},
      fallbackUrl: 'https://ets2.online/map/ets2mappromods_156/{z}/{x}/{y}.png',
      multipliers: { x: 51953, y: 76024 },
      breakpoints: { uk: { x: -31056.8, y: -5832.867 } },
      bounds: { x:131072, y:131072 },
      maxZoom: 8, minZoom: 2,
      calc: function(xx, yy) {
        return [ xx / 2.598541 + cfg.promods.multipliers.x, yy / 2.598541 + cfg.promods.multipliers.y ];
      }
    }
  };

  var map = L.map('map', { attributionControl: false, crs: L.CRS.Simple, zoomControl: false, zoomSnap: 0.2, zoomDelta: 0.2 });
  var c = cfg[mapType];
  var b = L.latLngBounds(
    map.unproject([0, c.bounds.y], c.maxZoom),
    map.unproject([c.bounds.x, 0], c.maxZoom)
  );
  var tileLayer = L.tileLayer(c.tileUrl, { minZoom: 0, minNativeZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  var switched = false;
  tileLayer.on('tileerror', function(){
    if (switched || !c.fallbackUrl) return;
    switched = true;
    map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(c.fallbackUrl, { minZoom: 0, minNativeZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  });
  map.setMaxBounds(b);
  var points = {{ points|tojson }};
  points = points.filter(function(p){ return !(p.axisX === 0 && p.axisY === 0 && p.heading === 0); });
  var lines = [];
  var currentLine = [];
  if (points.length > 0) {
    currentLine.push(points[0]);
    for (var i=1;i<points.length;i++){
      var prev = points[i-1];
      var curr = points[i];
      var dist = Math.hypot(curr.axisX - prev.axisX, curr.axisY - prev.axisY) * 19;
      var isDistJump = dist > 30000;
      var timeDiff = 0;
      if (curr.ts && prev.ts) {
        timeDiff = curr.ts - prev.ts;
      }
      var isTimeJump = timeDiff > 90;
      if (isDistJump || isTimeJump) {
        if (currentLine.length > 0) lines.push(currentLine);
        currentLine = [];
      }
      currentLine.push(curr);
    }
    if (currentLine.length > 0) lines.push(currentLine);
  }
  var allLatlngs = [];
  for (var li=0; li<lines.length; li++){
    var linePts = lines[li];
    if (!linePts || linePts.length === 0) continue;
    var latlngs = [];
    for (var j=0;j<linePts.length;j++){
      var xy = c.calc(linePts[j].axisX, linePts[j].axisY);
      var ll = map.unproject(xy, c.maxZoom);
      latlngs.push(ll);
      allLatlngs.push(ll);
    }
    L.polyline(latlngs, {
      color:'#0c3653', weight:11, opacity:0.96, lineCap:'round', lineJoin:'round'
    }).addTo(map);
    L.polyline(latlngs, {
      color:'#50afe8', weight:6, opacity:1, lineCap:'round', lineJoin:'round'
    }).addTo(map);
    L.polyline(latlngs, {
      color:'#8bd8ff', weight:1.8, opacity:0.48, lineCap:'round', lineJoin:'round'
    }).addTo(map);
  }

  function addEndpoint(latlng, type) {
    var color = type === 'end' ? '#ef655e' : '#59c98d';
    L.circleMarker(latlng, {
      radius:11, color:color, weight:1.5, opacity:0.32, fillOpacity:0
    }).addTo(map);
    L.circleMarker(latlng, {
      radius:6.5, color:'#f8fffd', weight:2, opacity:1, fillColor:color, fillOpacity:1
    }).addTo(map);
  }

  if (allLatlngs.length > 0) {
    addEndpoint(allLatlngs[0], 'start');
    addEndpoint(allLatlngs[allLatlngs.length - 1], 'end');
  }

  if (allLatlngs.length === 1) {
    map.setView(allLatlngs[0], 7);
  } else if (allLatlngs.length > 1) {
    map.fitBounds(L.latLngBounds(allLatlngs), {
      paddingTopLeft: [48, 55],
      paddingBottomRight: [48, 165],
      maxZoom: 8
    });
  }
  setTimeout(function(){ map.invalidateSize(); }, 80);
</script>
"""


COMBINED_FOOTPRINT_TEMPLATE = """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin:0; padding:0; width:1280px; height:720px; overflow:hidden; background:#244b63; }
  * { box-sizing:border-box; }
  body { font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC",system-ui,sans-serif; }
  .shell { position:relative; width:1280px; height:720px; overflow:hidden; color:#f5fbfa; background:#244b63; }
  .map-grid { display:grid; width:100%; height:100%; gap:5px; background:#122f43; }
  .map-grid.single { grid-template-columns:1fr; }
  .map-grid.dual { grid-template-columns:1fr 1fr; }
  .map-pane { position:relative; overflow:hidden; background:radial-gradient(circle at 52% 40%,#365f76 0,#294f66 52%,#1b3b51 100%); }
  .map-canvas { position:absolute; inset:0; background:transparent; }
  .map-canvas .leaflet-tile-pane { opacity:.82; filter:grayscale(1) brightness(1.75) contrast(1.12); mix-blend-mode:screen; }
  .leaflet-control-container { display:none; }
  .map-pane::after {
    content:""; position:absolute; inset:0; z-index:450; pointer-events:none;
    background:linear-gradient(180deg,rgba(7,29,45,.15),transparent 25%,transparent 66%,rgba(7,29,45,.42));
  }
  .route-legend { position:absolute; z-index:700; top:18px; left:18px; display:flex; flex-wrap:wrap; gap:7px; }
  .legend-pill {
    display:flex; align-items:center; gap:7px; height:27px; padding:0 10px;
    border:1px solid rgba(255,255,255,.18); border-radius:8px; color:#eaf6fa;
    background:rgba(8,31,48,.78); backdrop-filter:blur(9px); font-size:10px; font-weight:800;
  }
  .legend-pill i { width:8px; height:8px; border-radius:50%; }
  .panel {
    position:absolute; z-index:900; left:24px; right:24px; bottom:20px; height:104px;
    padding:0 25px; display:grid; grid-template-columns:minmax(0,1fr) 280px; gap:18px; align-items:center;
    border:1px solid rgba(255,255,255,.16); border-radius:19px;
    background:linear-gradient(105deg,rgba(7,28,45,.95),rgba(8,36,55,.9));
    box-shadow:0 18px 45px rgba(6,25,39,.35); backdrop-filter:blur(14px);
  }
  .panel::before {
    content:""; position:absolute; left:22px; right:22px; top:0; height:1px;
    background:linear-gradient(90deg,transparent,rgba(121,213,255,.7),transparent);
  }
  .profile { min-width:0; display:flex; align-items:center; gap:15px; }
  .avatar-wrap {
    width:68px; height:68px; flex:0 0 68px; padding:4px; border-radius:50%;
    background:linear-gradient(145deg,#6bcfff,#267cad); box-shadow:0 8px 22px rgba(2,16,27,.38);
  }
  .avatar { width:60px; height:60px; display:block; border:3px solid #102f45; border-radius:50%; object-fit:cover; }
  .avatar-fallback {
    width:60px; height:60px; display:flex; align-items:center; justify-content:center;
    border:3px solid #102f45; border-radius:50%; color:#f8fffd;
    background:linear-gradient(145deg,#237ca8,#123d59); font-size:24px; font-weight:800;
  }
  .profile-copy { min-width:0; flex:1; }
  .profile-kicker { margin-bottom:5px; color:#8bb1c3; font-size:9px; font-weight:800; letter-spacing:1.35px; }
  .name-line { display:flex; align-items:baseline; min-width:0; }
  .name {
    min-width:0; max-width:340px; overflow:hidden; color:#f7fbfc; font-size:23px; line-height:1.15;
    font-weight:800; letter-spacing:-.4px; text-overflow:ellipsis; white-space:nowrap;
  }
  .name-suffix { flex:0 0 auto; color:#afc8d4; font-size:16px; font-weight:600; white-space:nowrap; }
  .chips { display:flex; align-items:center; gap:6px; margin-top:8px; flex-wrap:wrap; }
  .chip {
    display:inline-flex; align-items:center; gap:5px; height:21px; padding:0 8px; border-radius:6px;
    color:#c1d8e3; background:rgba(255,255,255,.08); font-size:9px; font-weight:700;
  }
  .chip i { width:6px; height:6px; border-radius:50%; }
  .mileage { display:flex; align-items:baseline; justify-content:flex-end; gap:15px; white-space:nowrap; }
  .mileage span { color:#9bb6c4; font-size:14px; font-weight:600; }
  .mileage strong { color:#8de4b0; font-size:28px; line-height:1; font-weight:800; letter-spacing:-.6px; }
  .mileage small { margin-left:5px; color:#a7c6b7; font-size:12px; font-weight:600; }
</style>
<div class="shell">
  <div class="map-grid {% if map_groups|length == 1 %}single{% else %}dual{% endif %}">
    {% for group in map_groups %}
    <div class="map-pane">
      <div id="map-{{ loop.index }}" class="map-canvas"></div>
      <div class="route-legend">
        {% for route in group.routes %}
        <span class="legend-pill"><i style="background:{{ route.color|e }}"></i>{% if group.title == route.label %}{{ route.label|e }}{% else %}{{ group.title|e }} · {{ route.label|e }}{% endif %}</span>
        {% endfor %}
      </div>
    </div>
    {% endfor %}
  </div>
  <div class="panel">
    <div class="profile">
      <div class="avatar-wrap">
        {% if avatar %}<img class="avatar" src="{{ avatar|e }}" />{% else %}<div class="avatar-fallback">{{ avatar_initial|e }}</div>{% endif %}
      </div>
      <div class="profile-copy">
        <div class="profile-kicker">COMBINED DAILY TRACE</div>
        <div class="name-line">
          <div class="name">{{ player_name|e }}</div>
          <span class="name-suffix"> 的今日行驶足迹</span>
        </div>
        <div class="chips">
          {% for route in server_chips %}
          <span class="chip"><i style="background:{{ route.color|e }}"></i>{{ route.label|e }}</span>
          {% endfor %}
          <span class="chip">TMP #{{ tmp_id|e }}</span>
        </div>
      </div>
    </div>
    <div class="mileage">
      <span>今日里程</span>
      <strong>{% if total_distance is not none %}{{ '%.1f' % total_distance }}<small>km</small>{% else %}暂无记录{% endif %}</strong>
    </div>
  </div>
</div>
<script>
  var cfg = {
    ets: {
      fallbackUrl:'https://ets_tiles.cnly.top/20260903/tmp-ets-yellow/Tiles/{z}/{x}/{y}.png',
      bounds:{x:131072,y:131072}, maxZoom:8, minZoom:2,
      calc:function(xx,yy){var x1=-113177.305,x2=97925.63,y1=-122648.086,y2=88454.85;return [(xx-x1)/(x2-x1)*131072,(yy-y1)/(y2-y1)*131072];}
    },
    promods: {
      fallbackUrl:'https://ets2.online/map/ets2mappromods_156/{z}/{x}/{y}.png',
      multipliers:{x:51953,y:76024}, bounds:{x:131072,y:131072}, maxZoom:8, minZoom:2,
      calc:function(xx,yy){return [xx/2.598541+cfg.promods.multipliers.x,yy/2.598541+cfg.promods.multipliers.y];}
    }
  };
  var groups = {{ map_groups|tojson }};
  groups.forEach(function(group, index) {
    var map = L.map('map-' + (index + 1), {attributionControl:false,crs:L.CRS.Simple,zoomControl:false,zoomSnap:0.2,zoomDelta:0.2});
    var c = cfg[group.map_type];
    var world = L.latLngBounds(map.unproject([0,c.bounds.y],c.maxZoom),map.unproject([c.bounds.x,0],c.maxZoom));
    var tile = L.tileLayer(group.tile_url || c.fallbackUrl,{minZoom:0,minNativeZoom:c.minZoom,maxZoom:10,maxNativeZoom:c.maxZoom,tileSize:512,bounds:world,reuseTiles:true}).addTo(map);
    var switched = false;
    tile.on('tileerror',function(){if(switched||!c.fallbackUrl)return;switched=true;map.removeLayer(tile);tile=L.tileLayer(c.fallbackUrl,{minZoom:0,minNativeZoom:c.minZoom,maxZoom:10,maxNativeZoom:c.maxZoom,tileSize:512,bounds:world,reuseTiles:true}).addTo(map);});
    map.setMaxBounds(world);
    var panelFocus = [];
    group.routes.forEach(function(route){
      var points = route.points.filter(function(p){return !(p.axisX===0&&p.axisY===0&&p.heading===0);});
      var lines=[], current=[];
      if(points.length){current.push(points[0]);for(var i=1;i<points.length;i++){var prev=points[i-1],curr=points[i];var dist=Math.hypot(curr.axisX-prev.axisX,curr.axisY-prev.axisY)*19;var timeDiff=(curr.ts&&prev.ts)?curr.ts-prev.ts:0;if(dist>30000||timeDiff>90){if(current.length)lines.push(current);current=[];}current.push(curr);}if(current.length)lines.push(current);}
      var routeLatlngs=[];
      lines.forEach(function(linePts){
        var latlngs=linePts.map(function(p){var xy=c.calc(p.axisX,p.axisY);return map.unproject(xy,c.maxZoom);});
        routeLatlngs=routeLatlngs.concat(latlngs);
        L.polyline(latlngs,{color:'#0a2638',weight:10,opacity:.72,lineCap:'round',lineJoin:'round'}).addTo(map);
        L.polyline(latlngs,{color:route.color,weight:5,opacity:1,lineCap:'round',lineJoin:'round'}).addTo(map);
      });
      if(routeLatlngs.length){L.circleMarker(routeLatlngs[0],{radius:6,color:'#fff',weight:2,fillColor:'#59c98d',fillOpacity:1}).addTo(map);L.circleMarker(routeLatlngs[routeLatlngs.length-1],{radius:6,color:'#fff',weight:2,fillColor:'#ef655e',fillOpacity:1}).addTo(map);panelFocus=panelFocus.concat(routeLatlngs);}
    });
    if(panelFocus.length===1){map.setView(panelFocus[0],7);}else if(panelFocus.length>1){map.fitBounds(L.latLngBounds(panelFocus),{paddingTopLeft:[45,60],paddingBottomRight:[45,145],maxZoom:8});}
    setTimeout(function(){map.invalidateSize();},80);
  });
</script>
"""
