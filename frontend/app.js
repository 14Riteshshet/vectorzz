/**
 * SookshmaJal – Frontend Application
 * Team VECTORZZ · Hackwarts 2026 AgriTech Track
 *
 * Fix: wrapped in window.onload so Leaflet, Leaflet.Draw and Chart.js
 * are guaranteed to be parsed before any L.* call runs.
 * Loaded as a plain <script> (not type="module") for global scope access.
 */

// ── Config ───────────────────────────────────────────────────────────────────
var API_BASE = window.location.origin;

// Tumakuru preset coordinates (approximate plot polygons ~1 acre each)
var TALUK_PRESETS = {
  Madhugiri: {
    center: [13.6621, 77.2017],
    polygon: function() { return makeSquarePolygon(13.6621, 77.2017, 0.005); }
  },
  Koratagere: {
    center: [13.5225, 77.2365],
    polygon: function() { return makeSquarePolygon(13.5225, 77.2365, 0.005); }
  },
  Chikkanayakanahalli: {
    center: [13.4318, 76.9336],
    polygon: function() { return makeSquarePolygon(13.4318, 76.9336, 0.005); }
  }
};

/** Build a closed square GeoJSON ring [lon,lat] around a point. */
function makeSquarePolygon(lat, lon, half) {
  return [
    [lon - half, lat - half],
    [lon + half, lat - half],
    [lon + half, lat + half],
    [lon - half, lat + half],
    [lon - half, lat - half]  // close ring
  ];
}

// ── State ────────────────────────────────────────────────────────────────────
var drawnPolygon = null;
var currentResult = null;
var indicesChart = null;
var map = null;
var drawnItems = null;

// ── Bootstrap — wait for ALL scripts (Leaflet, Draw, Chart) to load ──────────
window.addEventListener('load', function() {

  // Safety check: if Leaflet didn't load, show a friendly error
  if (typeof L === 'undefined') {
    document.getElementById('map').innerHTML =
      '<div style="display:flex;align-items:center;justify-content:center;height:100%;flex-direction:column;gap:16px;">' +
      '<span style="font-size:40px;">⚠️</span>' +
      '<p style="color:#B64400;font-size:17px;">Map library failed to load. Please check your internet connection and refresh.</p>' +
      '</div>';
    return;
  }

  initMap();
  initUI();
});

// ── Map initialisation ────────────────────────────────────────────────────────
function initMap() {
  // Fix Leaflet default icon path broken by bundlers
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl:       'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl:     'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-shadow.png',
  });

  map = L.map('map', {
    center: [13.5, 77.1],
    zoom: 11,
    zoomControl: true,
    preferCanvas: false
  });

  // OpenStreetMap tiles
  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
    crossOrigin: true
  }).addTo(map);

  // Drawn items layer
  drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);

  // Draw controls — only if Leaflet.Draw loaded
  if (typeof L.Control !== 'undefined' && typeof L.Control.Draw !== 'undefined') {
    var drawControl = new L.Control.Draw({
      edit: { featureGroup: drawnItems, remove: true },
      draw: {
        polygon: {
          allowIntersection: false,
          showArea: true,
          shapeOptions: { color: '#0066CC', weight: 2, fillOpacity: 0.15 }
        },
        polyline:     false,
        rectangle:    false,
        circle:       false,
        marker:       false,
        circlemarker: false
      }
    });
    map.addControl(drawControl);

    map.on(L.Draw.Event.CREATED, function(e) {
      drawnItems.clearLayers();
      drawnItems.addLayer(e.layer);
      var geojson = e.layer.toGeoJSON();
      drawnPolygon = geojson.geometry.coordinates[0]; // [[lon,lat],…]
      updatePolygonStatus(drawnPolygon.length - 1);
    });

    map.on(L.Draw.Event.DELETED, function() {
      drawnPolygon = null;
      updatePolygonStatus(0);
    });
  } else {
    console.warn('Leaflet.Draw not loaded — polygon drawing disabled.');
    document.getElementById('polygon-status').textContent =
      '⚠ Draw plugin unavailable. Use a taluk preset instead.';
  }

  // Force map to recalculate size after CSS has rendered
  setTimeout(function() { map.invalidateSize(); }, 300);
}

// ── UI wiring ─────────────────────────────────────────────────────────────────
function initUI() {

  var $form       = document.getElementById('analyze-form');
  var $btnAnalyze = document.getElementById('btn-analyze');
  var $results    = document.getElementById('results-section');
  var $polyStatus = document.getElementById('polygon-status');
  var $errSummary = document.getElementById('form-error-summary');

  // ── Taluk preset buttons ───────────────────────────────────────────────────
  document.querySelectorAll('.btn-preset').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var taluk  = btn.dataset.taluk;
      var preset = TALUK_PRESETS[taluk];
      if (!preset || !map) return;

      drawnItems.clearLayers();

      var coords = preset.polygon();
      drawnPolygon = coords;

      var latlngs = coords.slice(0, -1).map(function(c) { return [c[1], c[0]]; });
      var poly = L.polygon(latlngs, { color: '#0066CC', weight: 2, fillOpacity: 0.15 });
      drawnItems.addLayer(poly);
      map.fitBounds(poly.getBounds(), { padding: [20, 20] });
      map.invalidateSize();

      document.getElementById('taluk').value = taluk;
      updatePolygonStatus(coords.length - 1);

      document.querySelectorAll('.btn-preset').forEach(function(b) {
        b.classList.remove('selected');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('selected');
      btn.setAttribute('aria-pressed', 'true');

      showToast('📍 ' + taluk + ' preset loaded', 'success');
    });
  });

  // ── Form submission ────────────────────────────────────────────────────────
  $form.addEventListener('submit', async function(e) {
    e.preventDefault();
    hideErrors($errSummary);

    if (!drawnPolygon || drawnPolygon.length < 4) {
      showError($errSummary, 'Please draw a polygon on the map or select a taluk preset before analysing.');
      return;
    }

    var farmerName = document.getElementById('farmer-name').value.trim();
    var cropType   = document.getElementById('crop-type').value;
    var taluk      = document.getElementById('taluk').value;
    var areaAcres  = parseFloat(document.getElementById('area-acres').value);

    var errors = [];
    if (!farmerName)   errors.push('Farmer Name is required.');
    if (!cropType)     errors.push('Crop Type is required.');
    if (!taluk)        errors.push('Taluk is required.');
    if (isNaN(areaAcres) || areaAcres < 0.1 || areaAcres > 50)
      errors.push('Plot area must be between 0.1 and 50 acres.');

    if (errors.length) { showError($errSummary, errors.join(' ')); return; }

    setButtonLoading($btnAnalyze, true);
    $results.classList.remove('visible');

    var payload = {
      farmer_name:          farmerName,
      crop_type:            cropType,
      taluk:                taluk,
      area_acres:           areaAcres,
      polygon_coordinates:  drawnPolygon,
      use_fallback:         false
    };

    try {
      var res = await fetchJSON('/api/analyze-plot', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload)
      });

      currentResult = res;
      renderResults(res);
      setButtonLoading($btnAnalyze, false);
      $results.classList.add('visible');
      requestAnimationFrame(function() {
        $results.scrollIntoView({ behavior: 'smooth', block: 'start' });
      });
      showToast('✅ Analysis complete!', 'success');

    } catch (err) {
      setButtonLoading($btnAnalyze, false, true);
      showError($errSummary, 'Analysis failed: ' + err.message);
      showToast('❌ ' + err.message, 'error');
      console.error('Analyze error:', err);
    }
  });

  // ── Plots history ──────────────────────────────────────────────────────────
  document.getElementById('btn-view-plots').addEventListener('click', async function() {
    var $section = document.getElementById('plots-section');
    var $btn = document.getElementById('btn-view-plots');
    var isExpanded = $btn.getAttribute('aria-expanded') === 'true';
    if (isExpanded) {
      $section.style.display = 'none';
      $btn.setAttribute('aria-expanded', 'false');
      return;
    }
    $btn.setAttribute('aria-expanded', 'true');
    $section.style.display = 'block';
    try {
      var data = await fetchJSON('/api/plots');
      renderPlots(data);
    } catch (err) {
      document.getElementById('plots-list-container').innerHTML =
        '<p style="color:var(--color-3);">Failed to load plots: ' + escHtml(err.message) + '</p>';
    }
  });

  // ── Verification modal ─────────────────────────────────────────────────────
  var $modal = document.getElementById('modal-verify');

  document.getElementById('btn-open-verify').addEventListener('click', function() { openModal($modal); });
  document.getElementById('modal-close-btn').addEventListener('click', function() { closeModal($modal); });
  $modal.addEventListener('click', function(e) { if (e.target === $modal) closeModal($modal); });
  document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape' && $modal.classList.contains('open')) closeModal($modal);
  });

  document.getElementById('btn-verify-hash').addEventListener('click', async function() {
    var hash = document.getElementById('verify-hash-input').value.trim().toLowerCase();
    var $result = document.getElementById('verify-result');
    $result.className = 'verify-result';
    $result.textContent = '';

    if (!/^[0-9a-f]{64}$/.test(hash)) {
      $result.className = 'verify-result invalid';
      $result.textContent = '❌ Invalid SHA-256 hash. Must be exactly 64 hex characters.';
      return;
    }
    $result.textContent = 'Verifying…';
    $result.style.display = 'block';
    try {
      var data = await fetchJSON('/api/verify/' + hash);
      if (data.is_valid) {
        $result.className = 'verify-result valid';
        $result.innerHTML = '✅ ' + escHtml(data.message) + '<br/>' +
          '<strong>Farmer:</strong> ' + escHtml(data.farmer_name || '') + '<br/>' +
          '<strong>Generated:</strong> ' + (data.generated_at ? new Date(data.generated_at).toLocaleString('en-IN') : 'N/A');
      } else {
        $result.className = 'verify-result invalid';
        $result.textContent = '❌ ' + data.message;
      }
    } catch (err) {
      $result.className = 'verify-result invalid';
      $result.textContent = '❌ Verification failed: ' + err.message;
    }
  });

  // PDF hash copy
  document.getElementById('btn-copy-hash').addEventListener('click', async function() {
    var hash = document.getElementById('pdf-hash-display').textContent;
    try {
      await navigator.clipboard.writeText(hash);
      showToast('📋 SHA-256 hash copied', 'success');
    } catch {
      showToast('Select and copy the hash manually.', 'warning');
    }
  });

  // Ctrl+Enter shortcut
  document.addEventListener('keydown', function(e) {
    var $btn = document.getElementById('btn-analyze');
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !$btn.disabled) {
      document.getElementById('analyze-form').requestSubmit();
    }
  });

  // Speech voices preload
  if ('speechSynthesis' in window) {
    window.speechSynthesis.onvoiceschanged = function() { window.speechSynthesis.getVoices(); };
  }
}

// ── Render results ─────────────────────────────────────────────────────────────
function renderResults(data) {
  var sat = data.satellite;
  var drought = data.drought;
  var hm = data.hydromet;

  // Drought banner
  var cls = stageClass(drought.stage);
  var droughtBanner = document.getElementById('drought-banner');
  droughtBanner.className = 'rec-card ' + cls;

  var badgeEl = document.getElementById('drought-badge-el');
  badgeEl.className = 'drought-badge ' + cls;
  badgeEl.textContent = drought.stage_label;

  document.getElementById('rec-title-en').textContent = drought.stage_label;
  document.getElementById('rec-text-en').textContent = drought.recommendation_en;
  document.getElementById('rec-text-kn').textContent = drought.recommendation_kn || '';

  // Metric cards
  document.querySelectorAll('.metric-card').forEach(function(c) {
    c.className = 'metric-card ' + cls;
  });

  document.getElementById('val-ndvi').textContent   = sat.ndvi.toFixed(4);
  document.getElementById('val-ndmi').textContent   = sat.ndmi.toFixed(4);
  document.getElementById('val-ndre').textContent   = sat.ndre.toFixed(4);
  document.getElementById('val-et0').textContent    = hm.et0_mm_day.toFixed(2);
  document.getElementById('val-precip').textContent = hm.precipitation_mm.toFixed(1);
  document.getElementById('val-soil').textContent   = hm.soil_moisture_0_7cm_pct.toFixed(1);
  document.getElementById('val-vsurv').textContent  = Number(hm.survival_liters).toLocaleString('en-IN');
  document.getElementById('val-deficit').textContent= hm.deficit_mm.toFixed(2);

  renderChart(sat.ndvi, sat.ndmi, sat.ndre);
  setupAudio(data.audio_base64, drought);

  if (data.pdf_sha256) {
    document.getElementById('pdf-hash-display').textContent = data.pdf_sha256;
    var dlLink = document.getElementById('pdf-download-link');
    dlLink.href = data.pdf_download_url || '#';
    dlLink.style.display = 'inline-flex';
    document.getElementById('btn-copy-hash').style.display = 'inline-flex';
  }
}

function stageClass(stage) {
  if (stage === 'healthy')          return 'healthy';
  if (stage === 'early_stress')     return 'early';
  if (stage === 'moderate_drought') return 'moderate';
  if (stage === 'severe_drought')   return 'severe';
  return 'healthy';
}

// ── Chart.js ──────────────────────────────────────────────────────────────────
function renderChart(ndvi, ndmi, ndre) {
  if (typeof Chart === 'undefined') return;
  var ctx = document.getElementById('indices-chart').getContext('2d');
  if (indicesChart) indicesChart.destroy();

  indicesChart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels: ['NDVI (Vegetation)', 'NDMI (Moisture)', 'NDRE (Red-Edge)'],
      datasets: [{
        label: 'Index Value',
        data: [ndvi, ndmi, ndre],
        backgroundColor: [
          ndvi > 0.3 ? 'rgba(0,102,204,0.75)'  : 'rgba(255,121,27,0.75)',
          ndmi > 0   ? 'rgba(0,102,204,0.75)'  : 'rgba(182,68,0,0.75)',
          ndre > 0.2 ? 'rgba(0,102,204,0.75)'  : 'rgba(255,121,27,0.75)'
        ],
        borderColor: ['#0066CC', '#0066CC', '#0066CC'],
        borderWidth: 2,
        borderRadius: 8
      }]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      plugins: {
        legend: { display: false },
        tooltip: {
          callbacks: {
            label: function(ctx) { return 'Value: ' + ctx.parsed.y.toFixed(4); }
          }
        }
      },
      scales: {
        y: {
          min: -1, max: 1,
          grid: { color: '#E8E8ED' },
          ticks: { color: '#6E6E73', font: { size: 12 } },
          title: { display: true, text: 'Index Value (−1 to +1)', color: '#6E6E73', font: { size: 12 } }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#1D1D1F', font: { size: 12, weight: '600' } }
        }
      }
    }
  });
}

// ── Audio ─────────────────────────────────────────────────────────────────────
function setupAudio(audioBase64, drought) {
  var $audio    = document.getElementById('advisory-audio');
  var $playBtn  = document.getElementById('btn-play-audio');
  var $srcLabel = document.getElementById('audio-source-label');

  if (audioBase64) {
    $audio.src = 'data:audio/wav;base64,' + audioBase64;
    $audio.load();
    $playBtn.disabled = false;
    $srcLabel.textContent = 'Sarvam AI · bulbul:v1 · ಕನ್ನಡ';

    $playBtn.onclick = function() {
      if ($audio.paused) {
        $audio.play().catch(console.warn);
        $playBtn.textContent = '⏸';
      } else {
        $audio.pause();
        $playBtn.textContent = '▶';
      }
    };
    $audio.onended = function() { $playBtn.textContent = '▶'; };

  } else {
    $playBtn.disabled = false;
    $srcLabel.textContent = 'Browser Speech Synthesis (offline fallback)';
    var text = drought.recommendation_kn || drought.recommendation_en || '';

    $playBtn.onclick = function() {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        var utter = new SpeechSynthesisUtterance(text);
        var voices = window.speechSynthesis.getVoices();
        var knVoice = voices.find(function(v) { return v.lang.startsWith('kn'); });
        if (knVoice) utter.voice = knVoice;
        utter.lang = 'kn-IN';
        utter.rate = 0.9;
        window.speechSynthesis.speak(utter);
        showToast('🔊 Playing via browser speech synthesis', 'success');
      } else {
        showToast('Speech synthesis not supported in this browser.', 'warning');
      }
    };
  }
}

// ── Plots ─────────────────────────────────────────────────────────────────────
function renderPlots(data) {
  var container = document.getElementById('plots-list-container');
  if (!data.plots || data.plots.length === 0) {
    container.innerHTML = '<div class="empty-state"><div class="empty-icon">🌾</div><p>No plots analysed yet.</p></div>';
    return;
  }
  var rows = data.plots.map(function(p) {
    var cls = stageClass(p.drought_stage || '');
    return '<div class="plot-row" role="listitem">' +
      '<div><div class="plot-row-name">' + escHtml(p.farmer_name) + '</div>' +
      '<div class="plot-row-meta">' + escHtml(p.crop_type) + ' · ' + escHtml(p.taluk) + ' · ' + p.area_acres.toFixed(1) + ' ac</div></div>' +
      '<span class="drought-badge ' + cls + '" style="font-size:var(--text-base);padding:var(--space-1) var(--space-4);">' +
        escHtml((p.drought_stage || 'unknown').replace('_', ' ')) + '</span>' +
      '<div class="plot-row-meta">' + new Date(p.created_at).toLocaleDateString('en-IN') + '</div>' +
      '</div>';
  }).join('');
  container.innerHTML = '<div class="plots-list" role="list">' + rows + '</div>' +
    '<p style="font-size:var(--text-base);color:var(--color-4);margin-top:var(--space-5);">' + data.total + ' plot' + (data.total !== 1 ? 's' : '') + ' total</p>';
}

// ── Modal helpers ─────────────────────────────────────────────────────────────
function openModal($modal) {
  $modal.classList.add('open');
  document.getElementById('verify-hash-input').focus();
  document.getElementById('verify-result').className = 'verify-result';
  document.getElementById('verify-result').textContent = '';
}

function closeModal($modal) {
  $modal.classList.remove('open');
  document.getElementById('btn-open-verify').focus();
}

// ── Polygon status ────────────────────────────────────────────────────────────
function updatePolygonStatus(vertexCount) {
  var $el = document.getElementById('polygon-status');
  if (vertexCount > 0) {
    $el.textContent = '✅ Polygon drawn with ' + vertexCount + ' vertices. Ready for analysis.';
    $el.style.color = 'var(--color-2)';
  } else {
    $el.textContent = 'No polygon drawn yet. Use the draw tool on the map.';
    $el.style.color = 'var(--color-4)';
  }
}

// ── API helpers ───────────────────────────────────────────────────────────────
async function fetchJSON(url, options) {
  var res = await fetch(API_BASE + url, options || {});
  if (!res.ok) {
    var detail = 'HTTP ' + res.status;
    try { var body = await res.json(); detail = body.detail || JSON.stringify(body); } catch(e) {}
    throw new Error(detail);
  }
  return res.json();
}

// ── Button state ──────────────────────────────────────────────────────────────
function setButtonLoading(btn, loading, error) {
  if (loading) {
    btn.classList.add('loading');
    btn.disabled = true;
    btn.setAttribute('aria-busy', 'true');
  } else {
    btn.classList.remove('loading');
    btn.disabled = false;
    btn.removeAttribute('aria-busy');
    if (error) {
      btn.classList.add('error');
      setTimeout(function() { btn.classList.remove('error'); }, 2500);
    }
  }
}

function showError($el, msg) {
  $el.textContent = '⚠ ' + msg;
  $el.style.display = 'block';
  $el.focus();
}
function hideErrors($el) {
  $el.style.display = 'none';
  $el.textContent = '';
}

// ── Toast ─────────────────────────────────────────────────────────────────────
function showToast(msg, type) {
  var $cont = document.getElementById('toast-container');
  var toast = document.createElement('div');
  toast.className = 'toast ' + (type || 'success');
  toast.textContent = msg;
  toast.setAttribute('role', 'status');
  $cont.appendChild(toast);
  setTimeout(function() {
    toast.style.animation = 'toast-out 0.3s ease forwards';
    toast.addEventListener('animationend', function() { toast.remove(); });
  }, 4000);
}

function escHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;').replace(/</g, '&lt;')
    .replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}
