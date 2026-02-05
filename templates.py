"""
图片/地图渲染模板合集
"""

def dlc_list_template() -> str:
    return """
<style>
  html, body { margin:0; padding:0; background:#222d33; width:auto; }
  * { box-sizing: border-box; }
</style>
<div style="width:100vw;background:#222d33;color:#fff;font-family:system-ui,Segoe UI,Helvetica,Arial,sans-serif;">
  <div style="font-size:20px;font-weight:600;margin:0;padding:12px 0 8px 0;">DLC 列表</div>
  {% for it in items %}
  <div style="display:flex;flex-direction:row;background:#24313a;margin:0 0 12px 0;padding:12px;">
    <img src="{{ it.headerImageUrl }}" style="width:210px;height:auto;object-fit:cover;"/>
    <div style="flex:1;padding:0 12px;">
      <div style="font-size:18px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ it.name }}</div>
      <div style="font-size:14px;color:#e5e5e5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;text-overflow:ellipsis;">{{ it.desc }}</div>
      <div style="margin-top:8px;">
        <span style="display:inline-block;color:#BEEE11;font-size:16px;">{{ it.price_str }}</span>
        {% if it.discount and it.discount > 0 %}
        <span style="display:inline-block;color:#cbcbcb;font-size:16px;text-decoration:line-through;margin-left:6px;">{{ it.original_price_str }}</span>
        <span style="font-size:14px;color:#BEEE11;background:#4c6b22;padding:2px 6px;margin-left:4px;">-{{ it.discount }}%</span>
        {% endif %}
      </div>
    </div>
  </div>
  {% endfor %}
</div>
"""


def footprint_map_template() -> str:
    return """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin:0; padding:0; width:100vw; height:100vh; background:#111; overflow:hidden; }
  * { box-sizing: border-box; }
  .wrap { width: 100vw; color:#f2f4f8; font-family: system-ui, Segoe UI, Helvetica, Arial, sans-serif; }
  #map { width: 100vw; height: calc(100vh - 140px); background:#121417; }
  .panel { width:100vw; height:140px; background:rgba(10,10,10,.82); display:flex; align-items:center; padding:14px 20px; color:#eaeaea; backdrop-filter: blur(4px); }
  .avatar { width:64px; height:64px; border-radius:50%; background:#808080; object-fit:cover; margin-right:16px; }
  .col { flex:1; }
  .name { font-size:20px; font-weight:600; letter-spacing:.3px; color:#f0f3f5; }
  .sub { font-size:14px; color:#d8d8d8; margin-top:6px; line-height:1.5; }
  .right { width:260px; text-align:right; color:#f0f3f5; font-size:14px; }
</style>
<div class="wrap">
  <div id="map"></div>
  <div class="panel">
    <img class="avatar" src="{{ avatar }}" />
    <div class="col"> 
      <div class="name">{{ player_name }} · {{ server_label }}</div>
      <div class="sub">点位数: {{ points_count }}{% if distance_km is not none %} · 里程: {{ '%.2f' % distance_km }} km{% endif %}</div>
      <div class="sub">{% if start_time %}开始: {{ start_time }}{% endif %}{% if end_time %} · 结束: {{ end_time }}{% endif %}</div>
    </div>
    <div class="right">
      <div>上次在线: {{ last_online }}</div>
    </div>
  </div>
</div>
<script>
  var mapType = "{{ map_type }}";
  var distanceKm = {% if distance_km is not none %}{{ '%.2f' % distance_km }}{% else %}null{% endif %};
  var cfg = {
    ets: {
      tileUrl: '{{ tile_url_ets }}',
      fallbackUrl: 'https://ets2.online/map/ets2map_157/{z}/{x}/{y}.png',
      multipliers: { x: 70272, y: 76157 },
      breakpoints: { uk: { x: -31056.8, y: -5832.867 } },
      bounds: { x:131072, y:131072 },
      maxZoom: 8, minZoom: 2,
      calc: function(xx, yy) {
        return [ xx / 1.609055 + cfg.ets.multipliers.x, yy / 1.609055 + cfg.ets.multipliers.y ];
      }
    },
    promods: {
      tileUrl: '{{ tile_url_promods }}',
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
  var tileLayer = L.tileLayer(c.tileUrl, { minZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  var switched = false;
  tileLayer.on('tileerror', function(){
    if (switched || !c.fallbackUrl) return;
    switched = true;
    map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(c.fallbackUrl, { minZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  });
  map.setMaxBounds(b);
  function calculateDistance(p1, p2) {
    return Math.sqrt(Math.pow(p1.axisX - p2.axisX, 2) + Math.pow(p1.axisY - p2.axisY, 2));
  }
  var points = [ {% for p in points %}{ axisX: {{ p.axisX }}, axisY: {{ p.axisY }}, serverId: {{ p.serverId }}, heading: {{ p.heading }}, ts: {{ p.ts }} }{% if not loop.last %}, {% endif %}{% endfor %} ];
  points = points.filter(function(p){ return !(p.axisX === 0 && p.axisY === 0 && p.heading === 0); });
  var minX = null, maxX = null, minY = null, maxY = null;
  for (var pi=0; pi<points.length; pi++){
    var px = points[pi].axisX;
    var py = points[pi].axisY;
    if (minX === null || px < minX) minX = px;
    if (maxX === null || px > maxX) maxX = px;
    if (minY === null || py < minY) minY = py;
    if (maxY === null || py > maxY) maxY = py;
  }
  var lines = [];
  var currentLine = [];
  if (points.length > 0) {
    currentLine.push(points[0]);
    for (var i=1;i<points.length;i++){
      var prev = points[i-1];
      var curr = points[i];
      var dist = calculateDistance(prev, curr) * 19;
      var isDistJump = dist > 30000;
      var timeDiff = 0;
      if (curr.ts && prev.ts) {
        timeDiff = curr.ts - prev.ts;
      }
      var isTimeJump = timeDiff > 90;
      var isServerJump = prev.serverId !== curr.serverId;
      if (isDistJump || isTimeJump || isServerJump) {
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
    var line = L.polyline(latlngs, { color:'#3aa3ff', weight:4, opacity:0.9 }).addTo(map);
    if (latlngs.length > 0) {
      L.circleMarker(latlngs[0], { color:'#ffffff', weight:2, fillColor:'#21d07a', fillOpacity:1, radius:5 }).addTo(map);
      L.circleMarker(latlngs[latlngs.length-1], { color:'#ffffff', weight:2, fillColor:'#ff4d4f', fillOpacity:1, radius:5 }).addTo(map);
    }
  }
  var fitLatlngs = null;
  if (minX !== null && minY !== null && maxX !== null && maxY !== null) {
    if (distanceKm && !isNaN(distanceKm)) {
      var scaleFactor = (mapType === 'promods') ? (2.598541 / 1.609055) : 1;
      var baseRange = (distanceKm * 1000) / 19 * scaleFactor;
      var rangeX = maxX - minX;
      var rangeY = maxY - minY;
      var range = Math.max(rangeX, rangeY);
      var targetRange = baseRange;
      if (mapType === 'promods') {
        if (distanceKm >= 1200) {
          targetRange = baseRange * 2.2;
        } else if (distanceKm >= 600) {
          targetRange = baseRange * 1.6;
        } else {
          targetRange = baseRange * 1.2;
        }
      }
      if (targetRange > range) {
        var cx = (minX + maxX) / 2;
        var cy = (minY + maxY) / 2;
        var half = targetRange / 2;
        minX = cx - half;
        maxX = cx + half;
        minY = cy - half;
        maxY = cy + half;
      }
    }
    var ll1 = map.unproject(c.calc(minX, maxY), c.maxZoom);
    var ll2 = map.unproject(c.calc(maxX, minY), c.maxZoom);
    fitLatlngs = [ll1, ll2];
  }
  if (fitLatlngs && fitLatlngs.length > 0) {
    map.fitBounds(L.latLngBounds(fitLatlngs), { padding: [30, 30] });
  } else if (allLatlngs.length > 0) {
    map.fitBounds(L.latLngBounds(allLatlngs), { padding: [30, 30] });
  }
</script>
"""


def locate_map_template() -> str:
    return """
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.css">
<script src="https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin:0; padding:0; width:100vw; height:100vh; background:#1f2328; overflow:hidden; }
  * { box-sizing: border-box; }
  .wrap { width: 100vw; color:#f2f4f8; font-family: system-ui, Segoe UI, Helvetica, Arial, sans-serif; }
  #map { width: 100vw; height: calc(100vh - 150px); background:#2a2f36; filter: contrast(1.08) saturate(1.15) brightness(1.18); }
  .panel { width:100vw; height:150px; background:rgba(28,28,28,.75); display:flex; align-items:center; padding:16px 20px; color:#eaeaea; backdrop-filter: blur(4px); }
  .avatar { width:64px; height:64px; border-radius:50%; background:#808080; object-fit:cover; margin-right:16px; }
  .col { flex:1; }
  .name { font-size:22px; font-weight:600; letter-spacing:.3px; color:#f0f3f5; }
  .sub { font-size:16px; color:#d8d8d8; margin-top:6px; }
  .right { width:240px; text-align:right; color:#f0f3f5; font-size:16px; }
</style>
<div class="wrap">
  <div id="map"></div>
  <div class="panel">
    <img class="avatar" src="{{ avatar }}" />
    <div class="col"> 
      <div class="name">{{ player_name }}</div>
      <div class="sub">{{ server_name }} 游戏中</div>
    </div>
    <div class="right">
      <div>{{ location_line }}</div>
    </div>
  </div>
</div>
<script>
  var promodsIds = [50, 51];
  var serverId = {{ server_id }};
  var mapType = promodsIds.indexOf(serverId) !== -1 ? 'promods' : 'ets';
  var cfg = {
    ets: {
      tileUrl: 'https://ets-map.oss-cn-beijing.aliyuncs.com/ets2/05102019/{z}/{x}/{y}.png',
      fallbackUrl: 'https://ets2.online/map/ets2map_157/{z}/{x}/{y}.png',
      multipliers: { x: 70272, y: 76157 },
      breakpoints: { uk: { x: -31056.8, y: -5832.867 } },
      bounds: { x:131072, y:131072 },
      maxZoom: 8, minZoom: 2,
      calc: function(xx, yy) {
        return [ xx / 1.609055 + cfg.ets.multipliers.x, yy / 1.609055 + cfg.ets.multipliers.y ];
      }
    },
    promods: {
      tileUrl: 'https://ets-map.oss-cn-beijing.aliyuncs.com/promods/05102019/{z}/{x}/{y}.png',
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
  var tileLayer = L.tileLayer(c.tileUrl, { minZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  var switched = false;
  tileLayer.on('tileerror', function(){
    if (switched || !c.fallbackUrl) return;
    switched = true;
    map.removeLayer(tileLayer);
    tileLayer = L.tileLayer(c.fallbackUrl, { minZoom: c.minZoom, maxZoom: 10, maxNativeZoom: c.maxZoom, tileSize: 512, bounds: b, reuseTiles: true }).addTo(map);
  });
  map.setMaxBounds(b);
  var centerX = {{ center_x }};
  var centerY = {{ center_y }};
  var players = [ {% for p in players %}{ axisX: {{ p.axisX }}, axisY: {{ p.axisY }}, tmpId: "{{ p.tmpId }}" }{% if not loop.last %}, {% endif %}{% endfor %} ];
  for (var i=0;i<players.length;i++){
    var p = players[i];
    var xy = c.calc(p.axisX, p.axisY);
    var latlng = map.unproject(xy, c.maxZoom);
    L.circleMarker(latlng, { color:'#2f2f2f', weight:2, fillColor:(p.tmpId === '{{ me_id }}' ? '#57bd00' : '#3ca7ff'), fillOpacity:1, radius:(p.tmpId === '{{ me_id }}' ? 6 : 5) }).addTo(map);
  }
  var centerLL = map.unproject(c.calc(centerX, centerY+80), c.maxZoom);
  map.setView(centerLL, 7);
  setTimeout(function(){}, 800);
</script>
"""


def rank_template() -> str:
    return """
<style>
  html, body { margin:0; padding:0; background:#222d33; width:auto; }
  * { box-sizing: border-box; }
  .wrap { width:600px; margin:0 auto; padding:14px; background:#222d33; color:#fff; font-family:system-ui,Segoe UI,Helvetica,Arial,sans-serif; }
  .header { font-size:20px; font-weight:600; margin:0 0 8px 0; text-align:center; }
  .me { background:#1f2a31; border:1px solid rgba(255,255,255,0.10); border-radius:8px; padding:10px 12px; margin:0 0 10px 0; }
  .me .t1 { font-size:14px; font-weight:700; margin:0 0 4px 0; }
  .me .t2 { font-size:13px; opacity:0.92; }
  .list { margin:0; padding:0; }
  .item { display:flex; align-items:center; background:#24313a; margin:0 0 8px 0; padding:8px 12px; border-radius:6px; border:1px solid rgba(255,255,255,0.08); }
  .item.top3 { background:linear-gradient(135deg,rgba(255,215,0,0.18),rgba(255,215,0,0.06)); border-color:rgba(255,215,0,0.35); }
  .rank { width:40px; font-size:15px; font-weight:bold; text-align:center; }
  .name { flex:1; padding:0 10px; min-width:0; font-size:14px; font-weight:600; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; }
  .km { min-width:90px; font-size:14px; font-weight:700; text-align:right; white-space:nowrap; }
</style>
<div class="wrap">
  <div class="header">{{ title }}</div>
  {% if me %}
  <div class="me">
    <div class="t1">🙋 个人信息：{{ me.name }} (ID:{{ me.tmp_id }})</div>
    <div class="t2">里程：{{ '%.2f' % me.km }} km{% if me.rank is not none %} | 排名：No.{{ me.rank }}{% endif %}{% if me.vtc_role %} | 车队职位：{{ me.vtc_role }}{% endif %}</div>
  </div>
  {% endif %}
  <div class="list">
    {% for it in items %}
    <div class="item{% if it.rank <= 3 %} top3{% endif %}">
      <div class="rank">#{{ it.rank }}</div>
      <div class="name">{{ it.name }} (ID:{{ it.tmp_id }})</div>
      <div class="km">{{ it.km }} km</div>
    </div>
    {% endfor %}
  </div>
</div>
"""
