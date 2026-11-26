/**
 * SookshmaJal – Frontend Application (Dual-Mode: Farmer Water Coach & Regional Office Monitor)
 * Team VECTORZZ · Hackwarts 2026 AgriTech Track
 *
 * Loaded as a plain <script> (not type="module") so Leaflet, Leaflet.Draw, and Chart.js
 * globals are available immediately on window load.
 */

// ── Config ───────────────────────────────────────────────────────────────────
var API_BASE = window.location.origin;

var TALUK_PRESETS = {
  Madhugiri: {
    center: [13.6621, 77.2017],
    demoFarmer: 'Ramaiah Gowda',
    demoCrop: 'Ragi',
    demoArea: '2.5',
    polygon: function() { return makeSquarePolygon(13.6621, 77.2017, 0.005); }
  },
  Koratagere: {
    center: [13.5225, 77.2365],
    demoFarmer: 'Basavaraju',
    demoCrop: 'Groundnut',
    demoArea: '2.0',
    polygon: function() { return makeSquarePolygon(13.5225, 77.2365, 0.005); }
  },
  Chikkanayakanahalli: {
    center: [13.4318, 76.9336],
    demoFarmer: 'Shivanna',
    demoCrop: 'Ragi',
    demoArea: '3.0',
    polygon: function() { return makeSquarePolygon(13.4318, 76.9336, 0.005); }
  }
};

var MODE_COPY = {
  farmer: {
    title: 'Precision Survival Water Coaching<br />for Karnataka Farmers',
    subtitle: 'Draw your farm plot or tap a Karnataka preset. Get exact V<sub>surv</sub> survival litres, 0–7 cm soil moisture, crop-stage borewell protection guidance, and a Kannada crop water advisory.'
  },
  officer: {
    title: 'Post-Harvest Drought Verification<br />&amp; PMFBY Claim Monitor',
    subtitle: 'Inspect Sentinel-2 spectral indices (NDVI, NDMI, NDRE), compare 2026 trajectories against healthy baselines to verify mid-season stress 60+ days post-harvest, and issue SHA-256 PMFBY dossiers.'
  }
};

function makeSquarePolygon(lat, lon, half) {
  return [
    [lon - half, lat - half],
    [lon + half, lat - half],
    [lon + half, lat + half],
    [lon - half, lat + half],
    [lon - half, lat - half]
  ];
}

// ── State ────────────────────────────────────────────────────────────────────
var activeMode = 'farmer';
var isHistoryOpen = false;
var drawnPolygon = null;
var currentResult = null;
var farmerChart = null;
var officerChart = null;
var map = null;
var drawnItems = null;
var regionalHeatLayer = null;
var regionalTalukFilter = 'ALL';
var regionalAuditFilter = 'ALL';
var regionalPlots = [];
var selectedRegionalPlotId = null;
var cadastralVillagesCache = [];
var selectedCadastral = null;
var officerToken = (function() {
  try { return sessionStorage.getItem('sookshmajal_officer_token') || ''; } catch (e) { return ''; }
})();
var pendingOfficerAction = null;
var capturedPhotoData = null; // { base64, filename, lat, lon, timestamp }

// ── Bootstrap ────────────────────────────────────────────────────────────────
window.addEventListener('load', function() {
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
  updateOfficerBadgeUI();
  checkServerHealth();
});

async function checkServerHealth() {
  var $pill = document.getElementById('server-status-pill');
  if (!$pill) return;
  try {
    var res = await fetch(API_BASE + '/api/health');
    if (res.ok) {
      $pill.textContent = '● Local Server Ready';
      $pill.classList.remove('offline');
    } else {
      $pill.textContent = '● Server Reconnecting';
      $pill.classList.add('offline');
    }
  } catch (e) {
    $pill.textContent = '● Offline';
    $pill.classList.add('offline');
  }
}

// ── Map initialisation ────────────────────────────────────────────────────────
function initMap() {
  delete L.Icon.Default.prototype._getIconUrl;
  L.Icon.Default.mergeOptions({
    iconRetinaUrl: 'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon-2x.png',
    iconUrl:       'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-icon.png',
    shadowUrl:     'https://cdn.jsdelivr.net/npm/leaflet@1.9.4/dist/images/marker-shadow.png'
  });

  map = L.map('map', {
    center: [13.53, 77.12],
    zoom: 10,
    zoomControl: true,
    preferCanvas: false
  });

  L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>',
    maxZoom: 19,
    crossOrigin: true
  }).addTo(map);

  drawnItems = new L.FeatureGroup();
  map.addLayer(drawnItems);
  regionalHeatLayer = new L.LayerGroup();
  map.addLayer(regionalHeatLayer);

  if (typeof L.Control !== 'undefined' && typeof L.Control.Draw !== 'undefined') {
    var drawControl = new L.Control.Draw({
      edit: { featureGroup: drawnItems, remove: true },
      draw: {
        polygon: {
          allowIntersection: false,
          showArea: true,
          shapeOptions: { color: '#0066CC', weight: 2, fillOpacity: 0.15 }
        },
        polyline: false,
        rectangle: false,
        circle: false,
        marker: false,
        circlemarker: false
      }
    });
    map.addControl(drawControl);

    map.on(L.Draw.Event.CREATED, function(e) {
      drawnItems.clearLayers();
      drawnItems.addLayer(e.layer);
      var geojson = e.layer.toGeoJSON();
      drawnPolygon = geojson.geometry.coordinates[0];
      selectedCadastral = null;
      var $cadMeta = document.getElementById('cad-parcel-meta');
      if ($cadMeta) { $cadMeta.textContent = ''; $cadMeta.classList.remove('visible'); }
      var $fb = document.getElementById('use-fallback');
      if ($fb) $fb.checked = false;
      updatePolygonStatus(drawnPolygon.length - 1);
    });

    map.on(L.Draw.Event.DELETED, function() {
      drawnPolygon = null;
      selectedCadastral = null;
      updatePolygonStatus(0);
    });
  } else {
    document.getElementById('polygon-status').textContent =
      '⚠ Draw plugin unavailable. Use a Tumakuru taluk preset instead.';
  }

  setTimeout(function() { map.invalidateSize(); }, 300);
}

// ── UI wiring ─────────────────────────────────────────────────────────────────
function initUI() {
  var $form       = document.getElementById('analyze-form');
  var $btnAnalyze = document.getElementById('btn-analyze');
  var $results    = document.getElementById('results-section');
  var $errSummary = document.getElementById('form-error-summary');

  // ── Mode Switcher ──────────────────────────────────────────────────────────
  document.querySelectorAll('.mode-segment').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var targetMode = btn.dataset.mode;
      if (targetMode === 'officer' && !officerToken) {
        openOfficerLoginModal('officer');
        return;
      }
      if (isHistoryOpen) closeHistoryPage(true);
      setMode(targetMode);
    });
  });

  // ── Officer Login / Logout / Photo Modal ───────────────────────────────────
  var $officerModal = document.getElementById('modal-officer-login');
  var $photoModal = document.getElementById('modal-photo-preview');

  document.getElementById('officer-login-close-btn').addEventListener('click', function() {
    $officerModal.classList.remove('open');
  });
  $officerModal.addEventListener('click', function(e) {
    if (e.target === $officerModal) $officerModal.classList.remove('open');
  });
  document.getElementById('photo-modal-close-btn').addEventListener('click', function() {
    $photoModal.classList.remove('open');
  });
  $photoModal.addEventListener('click', function(e) {
    if (e.target === $photoModal) $photoModal.classList.remove('open');
  });

  document.getElementById('btn-fill-officer-demo').addEventListener('click', function() {
    document.getElementById('officer-username').value = 'officer@tumakuru.gov.in';
    document.getElementById('officer-password').value = 'VECTORZZ2026';
    hideErrors(document.getElementById('officer-login-error'));
  });

  document.getElementById('officer-login-form').addEventListener('submit', async function(e) {
    e.preventDefault();
    var $err = document.getElementById('officer-login-error');
    var $submit = document.getElementById('btn-officer-login-submit');
    hideErrors($err);

    var username = document.getElementById('officer-username').value.trim();
    var password = document.getElementById('officer-password').value;
    if (!username || !password) {
      showError($err, 'Please enter officer email and password.');
      return;
    }
    setButtonLoading($submit, true);
    try {
      var auth = await fetchJSON('/api/officer/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, password: password })
      });
      officerToken = auth.access_token;
      try { sessionStorage.setItem('sookshmajal_officer_token', officerToken); } catch (err) {}
      updateOfficerBadgeUI();
      setButtonLoading($submit, false);
      $officerModal.classList.remove('open');
      showToast('🛡 Officer verified: ' + auth.officer_email, 'success');

      var action = pendingOfficerAction;
      pendingOfficerAction = null;
      if (action === 'history') {
        openHistoryPage(true);
      } else {
        if (isHistoryOpen) closeHistoryPage(true);
        setMode('officer');
      }
    } catch (err) {
      setButtonLoading($submit, false, true);
      showError($err, err.message || 'Invalid credentials');
    }
  });

  document.getElementById('btn-officer-logout').addEventListener('click', function() {
    clearOfficerSession();
    showToast('Logged out of Officer session.', 'warning');
  });

  // ── Regional Taluk Filter Pills & Dropdown ─────────────────────────────────
  function applyRegionalFilter(talukVal) {
    regionalTalukFilter = talukVal || 'ALL';
    selectedRegionalPlotId = null;
    document.querySelectorAll('.regional-pill').forEach(function(p) {
      var isActive = (p.dataset.regionalTaluk || '').toLowerCase() === regionalTalukFilter.toLowerCase();
      p.classList.toggle('active', isActive);
      p.setAttribute('aria-pressed', String(isActive));
    });
    var $sel = document.getElementById('regional-taluk-select');
    if ($sel) {
      $sel.value = regionalTalukFilter === 'C.N. Halli' ? 'Chikkanayakanahalli' : regionalTalukFilter;
    }
    if (officerToken) {
      loadRegionalSummary(regionalTalukFilter);
    }
  }

  document.querySelectorAll('.regional-pill').forEach(function(pill) {
    pill.addEventListener('click', function() {
      applyRegionalFilter(pill.dataset.regionalTaluk || 'ALL');
    });
  });

  var $regSelect = document.getElementById('regional-taluk-select');
  if ($regSelect) {
    $regSelect.addEventListener('change', function() {
      applyRegionalFilter($regSelect.value || 'ALL');
    });
  }

  // ── Symptoms Chips & Geotagged Photo Capture ───────────────────────────────
  document.querySelectorAll('.symptom-chip').forEach(function(chip) {
    chip.addEventListener('click', function() {
      var active = chip.classList.toggle('active');
      chip.setAttribute('aria-pressed', String(active));
    });
  });

  var $photoInput = document.getElementById('field-photo-input');
  var $lockGpsBtn = document.getElementById('btn-lock-gps');
  var $demoPlotBtn = document.getElementById('btn-demo-plot-gps');
  var $demoMismatchBtn = document.getElementById('btn-demo-mismatch-gps');
  var $clearGpsBtn = document.getElementById('btn-clear-gps');

  function getPlotCenterFallback() {
    if (drawnPolygon && drawnPolygon.length) {
      var lons = drawnPolygon.map(function(c) { return c[0]; });
      var lats = drawnPolygon.map(function(c) { return c[1]; });
      return {
        lat: lats.reduce(function(a, b) { return a + b; }, 0) / lats.length,
        lon: lons.reduce(function(a, b) { return a + b; }, 0) / lons.length
      };
    }
    var talukVal = document.getElementById('taluk') ? document.getElementById('taluk').value : '';
    if (talukVal && TALUK_PRESETS[talukVal]) {
      return { lat: TALUK_PRESETS[talukVal].center[0], lon: TALUK_PRESETS[talukVal].center[1] };
    }
    return { lat: 13.6621, lon: 77.2017 };
  }

  function lockDeviceGps(onDone) {
    if ('geolocation' in navigator) {
      navigator.geolocation.getCurrentPosition(
        function(pos) {
          onDone({
            lat: pos.coords.latitude,
            lon: pos.coords.longitude,
            source: 'device GPS'
          });
        },
        function() {
          onDone({ lat: null, lon: null, source: 'unavailable' });
        },
        { enableHighAccuracy: true, timeout: 4000 }
      );
    } else {
      onDone({ lat: null, lon: null, source: 'unavailable' });
    }
  }

  function updatePhotoPreviewUI() {
    var $box = document.getElementById('photo-preview-box');
    var $img = document.getElementById('photo-preview-img');
    var $coords = document.getElementById('photo-gps-coords');
    var $ts = document.getElementById('photo-timestamp-label');
    var $badge = document.getElementById('photo-gps-badge');
    var $ev = document.getElementById('photo-evidence-status');
    if (!capturedPhotoData) {
      $box.style.display = 'none';
      return;
    }
    $box.style.display = 'flex';
    if (capturedPhotoData.base64) {
      $img.src = capturedPhotoData.base64;
      $img.style.display = 'block';
    } else {
      $img.style.display = 'none';
    }
    var hasGps = capturedPhotoData.lat != null && capturedPhotoData.lon != null;
    if ($ev) {
      $ev.textContent = capturedPhotoData.base64
        ? '📷 Real camera photo attached (' + escHtml(capturedPhotoData.filename || 'photo') + ')'
        : '🧪 No camera photo attached (GPS simulation / coordinates only)';
    }
    if (hasGps) {
      $badge.className = 'geolock-pill ' + (capturedPhotoData.isMismatchDemo ? 'outside' : 'verified');
      $badge.textContent = capturedPhotoData.isMismatchDemo
        ? '🏙 Simulated Far/City GPS (Expect OUTSIDE_REGION)'
        : '📍 GPS Coordinates Locked';
      $coords.textContent = 'Lat: ' + Number(capturedPhotoData.lat).toFixed(5) + '°N · Lon: ' +
        Number(capturedPhotoData.lon).toFixed(5) + '°E';
      $ts.textContent = 'Timestamp: ' + new Date(capturedPhotoData.timestamp).toLocaleString('en-IN');
    } else {
      $badge.className = 'geolock-pill missing';
      $badge.textContent = '⚠ MISSING_GPS — Device GPS unavailable (will check photo EXIF or mark MISSING_GPS)';
      $coords.textContent = 'Lat: — · Lon: —';
      $ts.textContent = 'Tip: Use "Use Plot Coordinates as GPS" for city/laptop demos.';
    }
  }

  if ($photoInput) {
    $photoInput.addEventListener('change', function() {
      var file = $photoInput.files && $photoInput.files[0];
      if (!file) return;
      var reader = new FileReader();
      reader.onload = function(ev) {
        var b64 = ev.target.result;
        var existingLat = capturedPhotoData ? capturedPhotoData.lat : null;
        var existingLon = capturedPhotoData ? capturedPhotoData.lon : null;
        var existingTs = capturedPhotoData ? capturedPhotoData.timestamp : null;
        var existingMismatch = capturedPhotoData ? capturedPhotoData.isMismatchDemo : false;

        // Immediately attach photo so clicking Analyse Plot never drops it
        capturedPhotoData = {
          base64: b64,
          filename: file.name,
          lat: existingLat,
          lon: existingLon,
          timestamp: existingTs || new Date().toISOString(),
          isMismatchDemo: existingMismatch
        };
        updatePhotoPreviewUI();

        if (existingLat == null || existingLon == null) {
          lockDeviceGps(function(gps) {
            if (!capturedPhotoData) return;
            if (gps.lat != null && capturedPhotoData.lat == null) {
              capturedPhotoData.lat = gps.lat;
              capturedPhotoData.lon = gps.lon;
              capturedPhotoData.timestamp = new Date().toISOString();
              updatePhotoPreviewUI();
              showToast('📷 Photo attached & GPS locked (' + gps.source + ')', 'success');
            } else {
              showToast('📷 Photo attached (EXIF GPS will be checked or use Demo GPS)', 'success');
            }
          });
        } else {
          showToast('📷 Photo attached with locked GPS coordinates', 'success');
        }
      };
      reader.readAsDataURL(file);
    });
  }

  if ($lockGpsBtn) {
    $lockGpsBtn.addEventListener('click', function() {
      lockDeviceGps(function(gps) {
        if (gps.lat == null) {
          showToast('⚠ Browser GPS permission unavailable. Use Demo GPS buttons for simulation.', 'warning');
          return;
        }
        capturedPhotoData = capturedPhotoData || { base64: null, filename: null };
        capturedPhotoData.lat = gps.lat;
        capturedPhotoData.lon = gps.lon;
        capturedPhotoData.timestamp = new Date().toISOString();
        capturedPhotoData.isMismatchDemo = false;
        updatePhotoPreviewUI();
        showToast('📍 Device GPS Locked (' + gps.lat.toFixed(4) + ', ' + gps.lon.toFixed(4) + ')', 'success');
      });
    });
  }

  if ($demoPlotBtn) {
    $demoPlotBtn.addEventListener('click', function() {
      var c = getPlotCenterFallback();
      capturedPhotoData = capturedPhotoData || { base64: null, filename: null };
      capturedPhotoData.lat = c.lat;
      capturedPhotoData.lon = c.lon;
      capturedPhotoData.timestamp = new Date().toISOString();
      capturedPhotoData.isMismatchDemo = false;
      updatePhotoPreviewUI();
      showToast('📍 Simulated Plot GPS locked (' + c.lat.toFixed(4) + ', ' + c.lon.toFixed(4) + ')', 'success');
    });
  }

  if ($demoMismatchBtn) {
    $demoMismatchBtn.addEventListener('click', function() {
      var c = getPlotCenterFallback();
      // Pick Bengaluru (12.9716, 77.5946) or Hubballi if plot is already near Bengaluru
      var farLat = Math.abs(c.lat - 12.9716) > 0.45 ? 12.9716 : 15.3647;
      var farLon = Math.abs(c.lat - 12.9716) > 0.45 ? 77.5946 : 75.1240;
      capturedPhotoData = capturedPhotoData || { base64: null, filename: null };
      capturedPhotoData.lat = farLat;
      capturedPhotoData.lon = farLon;
      capturedPhotoData.timestamp = new Date().toISOString();
      capturedPhotoData.isMismatchDemo = true;
      updatePhotoPreviewUI();
      showToast('🏙 City/Far GPS set (' + farLat.toFixed(4) + ', ' + farLon.toFixed(4) + ') — will flag OUTSIDE_REGION', 'warning');
    });
  }

  if ($clearGpsBtn) {
    $clearGpsBtn.addEventListener('click', function() {
      if (capturedPhotoData && capturedPhotoData.base64) {
        capturedPhotoData.lat = null;
        capturedPhotoData.lon = null;
        capturedPhotoData.timestamp = null;
        capturedPhotoData.isMismatchDemo = false;
      } else {
        capturedPhotoData = null;
      }
      updatePhotoPreviewUI();
      showToast('GPS coordinates cleared (will submit as MISSING_GPS).', 'warning');
    });
  }

  // ── Bhoomi / Dishaank Cadastral Lookup ────────────────────────────────────
  var $cadTaluk = document.getElementById('cad-taluk');
  var $cadVillage = document.getElementById('cad-village');
  var $cadSurvey = document.getElementById('cad-survey');
  var $cadMeta = document.getElementById('cad-parcel-meta');

  if ($cadTaluk && $cadVillage && $cadSurvey) {
    $cadTaluk.addEventListener('change', async function() {
      var talukVal = $cadTaluk.value;
      $cadVillage.innerHTML = '<option value="">Select village…</option>';
      $cadSurvey.innerHTML = '<option value="">Select survey…</option>';
      $cadVillage.disabled = true;
      $cadSurvey.disabled = true;
      $cadMeta.textContent = '';
      $cadMeta.classList.remove('visible');
      selectedCadastral = null;
      if (!talukVal) return;

      try {
        var data = await fetchJSON('/api/cadastral/villages?taluk=' + encodeURIComponent(talukVal));
        cadastralVillagesCache = data.villages || [];
        cadastralVillagesCache.forEach(function(v) {
          var opt = document.createElement('option');
          opt.value = v.village;
          opt.textContent = v.village + ' (' + v.hobli + ' Hobli)';
          $cadVillage.appendChild(opt);
        });
        $cadVillage.disabled = cadastralVillagesCache.length === 0;
      } catch (err) {
        showToast('❌ Failed to load villages: ' + err.message, 'error');
      }
    });

    $cadVillage.addEventListener('change', function() {
      var villageVal = $cadVillage.value;
      $cadSurvey.innerHTML = '<option value="">Select survey…</option>';
      $cadSurvey.disabled = true;
      $cadMeta.textContent = '';
      $cadMeta.classList.remove('visible');
      selectedCadastral = null;
      if (!villageVal) return;

      var found = cadastralVillagesCache.find(function(v) { return v.village === villageVal; });
      if (found && found.survey_numbers) {
        found.survey_numbers.forEach(function(sn) {
          var opt = document.createElement('option');
          opt.value = sn;
          opt.textContent = 'Sy. No. ' + sn;
          $cadSurvey.appendChild(opt);
        });
        $cadSurvey.disabled = found.survey_numbers.length === 0;
      }
    });

    $cadSurvey.addEventListener('change', async function() {
      var talukVal = $cadTaluk.value;
      var villageVal = $cadVillage.value;
      var surveyVal = $cadSurvey.value;
      if (!talukVal || !villageVal || !surveyVal) return;

      try {
        var parcel = await fetchJSON(
          '/api/cadastral/parcel?taluk=' + encodeURIComponent(talukVal) +
          '&village=' + encodeURIComponent(villageVal) +
          '&survey_no=' + encodeURIComponent(surveyVal)
        );

        drawnPolygon = parcel.coordinates;
        selectedCadastral = {
          hobli: parcel.hobli,
          village: parcel.village,
          survey_no: parcel.survey_no
        };

        if (map && drawnItems && parcel.coordinates && parcel.coordinates.length >= 4) {
          drawnItems.clearLayers();
          var latlngs = parcel.coordinates.slice(0, -1).map(function(c) { return [c[1], c[0]]; });
          var poly = L.polygon(latlngs, {
            color: '#0066CC',
            weight: 3,
            fillColor: '#0066CC',
            fillOpacity: 0.24
          });
          drawnItems.addLayer(poly);
          map.fitBounds(poly.getBounds(), { padding: [28, 28] });
          map.invalidateSize();
          updatePolygonStatus(parcel.coordinates.length - 1);
        }

        document.getElementById('taluk').value = parcel.taluk;
        document.getElementById('area-acres').value = parcel.acres;
        document.getElementById('crop-type').value = parcel.default_crop;
        var $surveyInput = document.getElementById('survey-no');
        if ($surveyInput) $surveyInput.value = parcel.survey_no;

        $cadMeta.textContent = '📍 ' + parcel.village + ' (' + parcel.hobli + ' Hobli) · Sy. No. ' +
          parcel.survey_no + ' · ' + parcel.acres + ' ac · ' + parcel.soil_type;
        $cadMeta.classList.add('visible');

        showToast('🏛 Loaded Bhoomi Sy. No. ' + parcel.survey_no + ' (' + parcel.village + ')', 'success');
      } catch (err) {
        showToast('❌ Failed to load parcel: ' + err.message, 'error');
      }
    });
  }

  // ── Taluk preset buttons ───────────────────────────────────────────────────
  document.querySelectorAll('.btn-preset').forEach(function(btn) {
    btn.addEventListener('click', function() {
      var taluk  = btn.dataset.taluk;
      var preset = TALUK_PRESETS[taluk];
      if (!preset || !map) return;

      drawnItems.clearLayers();
      selectedCadastral = null;
      var $cadMeta = document.getElementById('cad-parcel-meta');
      if ($cadMeta) { $cadMeta.textContent = ''; $cadMeta.classList.remove('visible'); }
      var $surveyInput = document.getElementById('survey-no');
      if ($surveyInput) $surveyInput.value = '';

      var coords = preset.polygon();
      drawnPolygon = coords;

      var latlngs = coords.slice(0, -1).map(function(c) { return [c[1], c[0]]; });
      var poly = L.polygon(latlngs, { color: '#0066CC', weight: 2, fillOpacity: 0.15 });
      drawnItems.addLayer(poly);
      map.fitBounds(poly.getBounds(), { padding: [20, 20] });
      map.invalidateSize();

      document.getElementById('taluk').value = taluk;

      var $farmer = document.getElementById('farmer-name');
      var $crop = document.getElementById('crop-type');
      var $area = document.getElementById('area-acres');
      if (!$farmer.value.trim()) $farmer.value = preset.demoFarmer;
      if (!$crop.value) $crop.value = preset.demoCrop;
      if (!$area.value) $area.value = preset.demoArea;
      document.getElementById('use-fallback').checked = true;

      updatePolygonStatus(coords.length - 1);

      document.querySelectorAll('.btn-preset').forEach(function(b) {
        b.classList.remove('selected');
        b.setAttribute('aria-pressed', 'false');
      });
      btn.classList.add('selected');
      btn.setAttribute('aria-pressed', 'true');

      showToast('📍 ' + taluk + ' preset loaded (Kharif 2026 demo ready)', 'success');
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

    var farmerName  = document.getElementById('farmer-name').value.trim() || 'Tumakuru Farmer';
    var phoneNumber = document.getElementById('farmer-phone') ? document.getElementById('farmer-phone').value.trim() : '';
    var cropType    = document.getElementById('crop-type').value;
    var taluk       = document.getElementById('taluk').value;
    var areaAcres   = parseFloat(document.getElementById('area-acres').value);
    var surveyNoEl  = document.getElementById('survey-no');
    var surveyNo    = surveyNoEl ? surveyNoEl.value.trim() : '';
    var irrEl       = document.getElementById('irrigation-source');
    var irrSource   = irrEl ? irrEl.value : 'Purely Rain-Fed';
    var symptoms    = Array.from(document.querySelectorAll('.symptom-chip.active'))
      .map(function(c) { return c.dataset.symptom; })
      .filter(Boolean);
    var useFallback = document.getElementById('use-fallback').checked;

    var errors = [];
    if (!cropType)     errors.push('Crop Type is required.');
    if (!taluk)        errors.push('Taluk is required.');
    if (isNaN(areaAcres) || areaAcres < 0.1 || areaAcres > 50) {
      errors.push('Plot area must be between 0.1 and 50 acres.');
    }

    if (errors.length) {
      showError($errSummary, errors.join(' '));
      return;
    }

    setButtonLoading($btnAnalyze, true);
    $results.classList.remove('visible');

    var payload = {
      farmer_name:         farmerName,
      phone_number:        phoneNumber || null,
      crop_type:           cropType,
      taluk:               taluk,
      hobli:               selectedCadastral ? selectedCadastral.hobli : null,
      village:             selectedCadastral ? selectedCadastral.village : null,
      survey_no:           surveyNo || (selectedCadastral ? selectedCadastral.survey_no : null),
      area_acres:          areaAcres,
      irrigation_source:   irrSource,
      observed_symptoms:   symptoms,
      photo_base64:        capturedPhotoData && capturedPhotoData.base64 ? capturedPhotoData.base64 : null,
      photo_filename:      capturedPhotoData && capturedPhotoData.filename ? capturedPhotoData.filename : null,
      photo_lat:           capturedPhotoData && capturedPhotoData.lat != null ? capturedPhotoData.lat : null,
      photo_lon:           capturedPhotoData && capturedPhotoData.lon != null ? capturedPhotoData.lon : null,
      photo_timestamp:     capturedPhotoData && capturedPhotoData.timestamp ? capturedPhotoData.timestamp : null,
      polygon_coordinates: drawnPolygon,
      use_fallback:        useFallback
    };

    try {
      var res = await fetchJSON('/api/analyze-plot', {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify(payload)
      });

      currentResult = res;
      selectedRegionalPlotId = res.plot_id;
      renderResults(res);
      setButtonLoading($btnAnalyze, false);
      $results.classList.add('visible');
      if (activeMode === 'officer') {
        loadRegionalSummary(regionalTalukFilter);
      }
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

  // ── Regional Officer: Generate & Verify PMFBY Audit Dossier ────────────────
  document.getElementById('btn-generate-dossier').addEventListener('click', async function() {
    if (!currentResult || !currentResult.plot_id) {
      showToast('Please analyse a plot first.', 'warning');
      return;
    }
    var $btn = this;
    var $statusPill = document.getElementById('dossier-verify-status');
    setButtonLoading($btn, true);
    $statusPill.className = 'verify-pill';
    $statusPill.textContent = '⏳ Generating & verifying dossier…';

    try {
      var dossier = await fetchJSON('/api/plots/' + encodeURIComponent(currentResult.plot_id) + '/dossier', {
        method: 'POST'
      });

      // Confirm against /api/verify/{sha256}
      var verified = await fetchJSON('/api/verify/' + encodeURIComponent(dossier.sha256_hash));

      currentResult.pdf_sha256 = dossier.sha256_hash;
      currentResult.pdf_download_url = dossier.pdf_download_url;

      updateDossierUI(dossier.sha256_hash, dossier.pdf_download_url, verified.is_valid, dossier.plot_id, dossier.verified_at || dossier.generated_at);
      setButtonLoading($btn, false);
      if (activeMode === 'officer') {
        loadRegionalSummary(regionalTalukFilter);
      }
      showToast('📄 PMFBY Audit Dossier generated & SHA-256 verified', 'success');
    } catch (err) {
      setButtonLoading($btn, false, true);
      $statusPill.className = 'verify-pill error';
      $statusPill.textContent = '❌ Dossier generation failed';
      showToast('❌ ' + err.message, 'error');
    }
  });

  // ── Plots history page navigation ──────────────────────────────────────────
  document.getElementById('btn-view-plots').addEventListener('click', function() {
    if (!officerToken) {
      openOfficerLoginModal('history');
      return;
    }
    if (isHistoryOpen) {
      closeHistoryPage(true);
    } else {
      openHistoryPage(true);
    }
  });
  document.getElementById('btn-history-back').addEventListener('click', function() {
    closeHistoryPage(true);
  });
  document.getElementById('btn-history-refresh').addEventListener('click', function() {
    loadPlotsHistory();
  });
  window.addEventListener('hashchange', function() {
    if (window.location.hash === '#history') {
      if (!isHistoryOpen) openHistoryPage(false);
    } else if (isHistoryOpen) {
      closeHistoryPage(false);
    }
  });
  if (window.location.hash === '#history' && officerToken) {
    openHistoryPage(false);
  }

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
        $result.innerHTML = escHtml(data.message) + '<br/>' +
          '<strong>Farmer:</strong> ' + escHtml(data.farmer_name || '') + '<br/>' +
          '<strong>Plot ID:</strong> ' + escHtml(data.plot_id || '') + '<br/>' +
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
    } catch (err) {
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

  if ('speechSynthesis' in window) {
    window.speechSynthesis.onvoiceschanged = function() { window.speechSynthesis.getVoices(); };
  }

  // ── PMFBY Guidelines Tabs & Live Estimators ───────────────────────────────
  document.querySelectorAll('.pmfby-tab').forEach(function(tab) {
    tab.addEventListener('click', function() {
      var target = tab.dataset.pmfbyTab || 'all';
      document.querySelectorAll('.pmfby-tab').forEach(function(t) {
        var active = t === tab;
        t.classList.toggle('active', active);
        t.setAttribute('aria-selected', String(active));
      });
      document.querySelectorAll('.pmfby-card').forEach(function(card) {
        card.style.display = (target === 'all' || card.dataset.pmfbyCard === target) ? 'flex' : 'none';
      });
    });
  });

  ['area-acres', 'crop-type', 'taluk', 'survey-no', 'irrigation-source'].forEach(function(id) {
    var el = document.getElementById(id);
    if (el) {
      el.addEventListener('input', function() { updatePmfbyGuidelinesUI(currentResult); });
      el.addEventListener('change', function() {
        if (id === 'taluk') updateFarmerHeroTitle();
        updatePmfbyGuidelinesUI(currentResult);
      });
    }
  });

  var $trustVerifyBtn = document.getElementById('btn-trust-verify');
  if ($trustVerifyBtn) {
    $trustVerifyBtn.addEventListener('click', function() {
      if (!currentResult || !currentResult.pdf_sha256) return;
      openModal($modal);
      document.getElementById('verify-hash-input').value = currentResult.pdf_sha256;
      document.getElementById('btn-verify-hash').click();
    });
  }

  var $copySummaryBtn = document.getElementById('btn-copy-claim-summary');
  if ($copySummaryBtn) {
    $copySummaryBtn.addEventListener('click', async function() {
      if (!currentResult) return;
      var locParts = [currentResult.taluk, currentResult.village, currentResult.survey_no ? ('Sy. ' + currentResult.survey_no) : '']
        .filter(Boolean).join(' · ');
      var ndmiVal = currentResult.satellite && currentResult.satellite.ndmi != null
        ? Number(currentResult.satellite.ndmi).toFixed(3) : 'N/A';
      var stageLabel = (currentResult.drought && currentResult.drought.stage_label) || 'N/A';
      var summaryText = [
        'SookshmaJal PMFBY Claim Summary',
        'Dossier / Plot ID: ' + (currentResult.dossier_id || currentResult.plot_id || 'N/A'),
        'Farmer: ' + (currentResult.farmer_name || 'N/A'),
        'Location: ' + (locParts || 'Tumakuru'),
        'Crop & Area: ' + (currentResult.crop_type || 'N/A') + ' · ' + Number(currentResult.area_acres || 0).toFixed(1) + ' acres',
        'Moisture (NDMI) / Stage: ' + ndmiVal + ' · ' + stageLabel,
        'Geolock Status: ' + (currentResult.geolock_status || 'MISSING_GPS'),
        'Dossier SHA-256: ' + (currentResult.pdf_sha256 || 'Pending')
      ].join('\n');
      try {
        await navigator.clipboard.writeText(summaryText);
        var origLabel = $copySummaryBtn.textContent;
        $copySummaryBtn.textContent = '✅ Copied!';
        setTimeout(function() { $copySummaryBtn.textContent = origLabel; }, 2000);
        showToast('📋 Claim summary copied', 'success');
      } catch (err) {
        showToast('Unable to copy automatically.', 'warning');
      }
    });
  }

  var $clearPlotBtn = document.getElementById('btn-clear-plot');
  if ($clearPlotBtn) {
    $clearPlotBtn.addEventListener('click', function() {
      resetFarmerPlotForm();
    });
  }

  updatePmfbyGuidelinesUI(null);

  // ── Officer Audit Toolbar (Status/Photo Filters & Cleanup) ─────────────────
  document.querySelectorAll('[data-audit-filter]').forEach(function(pill) {
    pill.addEventListener('click', function() {
      regionalAuditFilter = pill.dataset.auditFilter || 'ALL';
      document.querySelectorAll('[data-audit-filter]').forEach(function(p) {
        var isAct = p === pill;
        p.classList.toggle('active', isAct);
        p.setAttribute('aria-pressed', String(isAct));
      });
      renderRegionalTable(getFilteredRegionalPlots());
    });
  });

  var $cleanupBtn = document.getElementById('btn-remove-nophoto');
  if ($cleanupBtn) {
    $cleanupBtn.addEventListener('click', async function() {
      if (!window.confirm('Remove all entries that have no uploaded field photo?')) return;
      try {
        var res = await authFetchJSON('/api/audit/cleanup/no-photo', { method: 'DELETE' });
        showToast('🧹 ' + (res.message || 'Removed no-photo entries.'), 'success');
        loadRegionalSummary(regionalTalukFilter);
      } catch (err) {
        showToast('❌ ' + err.message, 'error');
      }
    });
  }
}

// ── Mode Switcher Logic ──────────────────────────────────────────────────────
function setMode(mode) {
  if (mode !== 'farmer' && mode !== 'officer') return;
  if (mode === 'officer' && !officerToken) {
    openOfficerLoginModal('officer');
    return;
  }
  activeMode = mode;
  document.body.dataset.mode = mode;

  var $farmerBtn = document.getElementById('mode-btn-farmer');
  var $officerBtn = document.getElementById('mode-btn-officer');
  $farmerBtn.classList.toggle('active', mode === 'farmer');
  $officerBtn.classList.toggle('active', mode === 'officer');
  $farmerBtn.setAttribute('aria-selected', String(mode === 'farmer'));
  $officerBtn.setAttribute('aria-selected', String(mode === 'officer'));

  var copy = MODE_COPY[mode];
  document.getElementById('hero-title').innerHTML = copy.title;
  document.getElementById('hero-subtitle').innerHTML = copy.subtitle;
  if (mode === 'farmer') updateFarmerHeroTitle();

  document.getElementById('farmer-view').style.display = mode === 'farmer' ? 'block' : 'none';
  document.getElementById('officer-view').style.display = mode === 'officer' ? 'block' : 'none';
  var $pmfbyGuide = document.getElementById('pmfby-guidelines-section');
  if ($pmfbyGuide) {
    $pmfbyGuide.style.display = mode === 'farmer' ? 'block' : 'none';
  }
  var $regSection = document.getElementById('regional-monitor-section');
  if ($regSection) {
    $regSection.style.display = mode === 'officer' ? 'block' : 'none';
  }
  var $heatLegend = document.getElementById('regional-heatmap-legend');
  if ($heatLegend) {
    $heatLegend.style.display = mode === 'officer' ? 'flex' : 'none';
  }
  if (mode === 'officer') {
    loadRegionalSummary(regionalTalukFilter);
  } else if (regionalHeatLayer) {
    regionalHeatLayer.clearLayers();
  }

  // Re-render charts cleanly when switching tabs after analysis
  if (currentResult) {
    var ts = currentResult.time_series || {};
    if (mode === 'farmer') {
      var vs = currentResult.hydromet ? Number(currentResult.hydromet.survival_liters || 0) : 0;
      renderFarmerChart(ts, vs);
    } else {
      renderOfficerChart(ts, currentResult.drought);
    }
  }
}

// ── Render results ─────────────────────────────────────────────────────────────
function renderResults(data) {
  var sat = data.satellite;
  var drought = data.drought;
  var hm = data.hydromet;
  var ts = data.time_series || {};
  var guidance = data.irrigation_guidance || {};
  var cls = stageClass(drought.stage);

  // Meta summary pill
  document.getElementById('plot-meta-summary').textContent =
    data.farmer_name + ' · ' + data.crop_type + ' · ' + data.taluk +
    ' (' + data.area_acres.toFixed(1) + ' ac · ' + sat.scene_date + ')';

  // Shared drought banner
  document.getElementById('drought-banner').className = 'rec-card ' + cls;
  var badgeEl = document.getElementById('drought-badge-el');
  badgeEl.className = 'drought-badge ' + cls;
  badgeEl.textContent = drought.stage_label;

  document.getElementById('rec-title-en').textContent = drought.stage_label;
  document.getElementById('rec-text-en').textContent = drought.recommendation_en;
  document.getElementById('rec-text-kn').textContent = drought.recommendation_kn || '';

  // Accent styling on metric cards
  document.querySelectorAll('.metric-card').forEach(function(c) {
    var isHero = c.classList.contains('metric-card-hero');
    c.className = 'metric-card ' + (isHero ? 'metric-card-hero ' : '') + cls;
  });

  // ── Farmer PMFBY Eligibility Pre-Check Card ────────────────────────────────
  var $eligCard = document.getElementById('farmer-eligibility-card');
  var $eligBadge = document.getElementById('farmer-eligibility-badge');
  var $eligText = document.getElementById('farmer-eligibility-text');
  var $farmerPdfLink = document.getElementById('farmer-pdf-receipt-link');
  if ($eligCard && $eligBadge && $eligText) {
    var eligStr = data.pmfby_eligible || (
      drought.stage === 'severe_drought'
        ? 'ELIGIBLE — Severe Moisture Deficit'
        : (drought.stage === 'healthy' ? 'NOT ELIGIBLE — Normal Moisture' : 'WATCHLIST — Moderate Stress')
    );
    var eligClass = drought.stage === 'severe_drought'
      ? 'eligible'
      : (drought.stage === 'healthy' ? 'not-eligible' : 'watchlist');
    $eligCard.className = 'card eligibility-card ' + eligClass;
    $eligCard.style.display = 'block';
    $eligBadge.textContent = eligStr;
    $eligText.textContent = drought.stage === 'severe_drought'
      ? 'Satellite NDMI & FAO-56 deficit cross severe PMFBY trigger thresholds. Download your SHA-256 receipt below.'
      : (drought.stage === 'healthy'
        ? 'Moisture indices are within normal bounds; follow standard irrigation coaching below.'
        : 'Plot is under stress watchlist. Save your SHA-256 receipt and monitor weekly.');
    var $geolockPill = document.getElementById('farmer-geolock-pill');
    if ($geolockPill) {
      var gStatus = data.geolock_status || 'MISSING_GPS';
      var gCls = geolockPillClass(gStatus);
      var distPart = data.distance_km != null ? (' · ' + Number(data.distance_km).toFixed(2) + ' km from plot') : '';
      var matchPart = ' · Region Match: ' + (data.region_match ? 'Yes' : 'No');
      var photoPart = data.photo_attached ? ' · Camera Photo Attached' : ' · No Camera Photo';
      $geolockPill.innerHTML = '<span class="geolock-pill ' + gCls + '">' +
        escHtml(gStatus) + distPart + matchPart + photoPart + '</span>';
    }
    if ($farmerPdfLink) {
      if (data.pdf_download_url) {
        $farmerPdfLink.href = data.pdf_download_url;
        $farmerPdfLink.style.display = 'inline-flex';
      } else {
        $farmerPdfLink.style.display = 'none';
      }
    }
    var $eligPhotoWrap = document.getElementById('farmer-elig-photo-wrap');
    var $eligPhotoImg = document.getElementById('farmer-elig-photo-img');
    var $eligPhotoMeta = document.getElementById('farmer-elig-photo-meta');
    if ($eligPhotoWrap && $eligPhotoImg && $eligPhotoMeta) {
      if (data.photo_attached && capturedPhotoData && capturedPhotoData.base64) {
        $eligPhotoImg.src = capturedPhotoData.base64;
        $eligPhotoMeta.textContent = 'Field Photo Proof · ' + (data.geolock_status || 'MISSING_GPS') +
          (data.photo_sha256 ? ' · SHA-256: ' + data.photo_sha256.slice(0, 14) + '…' : '');
        $eligPhotoWrap.style.display = 'flex';
      } else {
        $eligPhotoImg.removeAttribute('src');
        $eligPhotoWrap.style.display = 'none';
      }
    }
  }

  // ── Farmer Water Coach fields ──────────────────────────────────────────────
  var vsurv = Number(hm.survival_liters || 0);
  var dailyVsurv = guidance.daily_survival_liters != null
    ? Number(guidance.daily_survival_liters)
    : vsurv / 7.0;

  document.getElementById('val-vsurv').textContent = vsurv.toLocaleString('en-IN');
  document.getElementById('val-vsurv-daily').textContent =
    '~' + Math.round(dailyVsurv).toLocaleString('en-IN') + ' L/day survival ration';
  document.getElementById('val-soil').textContent = hm.soil_moisture_0_7cm_pct.toFixed(1);
  document.getElementById('val-soil-status').textContent =
    hm.soil_moisture_0_7cm_pct < 15
      ? 'Critical root-zone dryness (0–7 cm)'
      : (hm.soil_moisture_0_7cm_pct < 22 ? 'Low topsoil moisture (0–7 cm)' : 'Adequate topsoil moisture (0–7 cm)');
  document.getElementById('val-et0').textContent = hm.et0_mm_day.toFixed(2);
  document.getElementById('val-precip').textContent = hm.precipitation_mm.toFixed(1);
  document.getElementById('val-deficit').textContent = hm.deficit_mm.toFixed(2);

  document.getElementById('guidance-window').textContent =
    guidance.critical_window || 'Flowering & Grain-Filling Reproductive Window';
  document.getElementById('guidance-borewell').textContent =
    guidance.borewell_advisory || 'Avoid excess borewell pumping; ration to V_surv root-zone volume.';
  document.getElementById('guidance-schedule').textContent =
    guidance.irrigation_schedule || drought.recommendation_en;

  var $chips = document.getElementById('advisory-metrics-chips');
  if ($chips) {
    var cropKnMap = {
      ragi: 'ರಾಗಿ', groundnut: 'ಶೇಂಗಾ', maize: 'ಮೆಕ್ಕೆಜೋಳ',
      'pigeon pea': 'ತೊಗರಿ', togari: 'ತೊಗರಿ', tur: 'ತೊಗರಿ',
      tomato: 'ಟೊಮೇಟೊ', sunflower: 'ಸೂರ್ಯಕಾಂತಿ', sorghum: 'ಜೋಳ',
      cotton: 'ಹತ್ತಿ', rice: 'ಭತ್ತ'
    };
    var cropKn = cropKnMap[(data.crop_type || '').toLowerCase()] || data.crop_type;
    $chips.innerHTML =
      '<span class="advisory-chip">🌱 ' + escHtml(cropKn) + ' (' + escHtml(data.crop_type) + ')</span>' +
      '<span class="advisory-chip">💧 7-Day Need: ' + Math.round(vsurv).toLocaleString('en-IN') + ' L</span>' +
      '<span class="advisory-chip">🚿 Daily Ration: ~' + Math.round(dailyVsurv).toLocaleString('en-IN') + ' L/day</span>' +
      '<span class="advisory-chip">🌡 Moisture Index: ' + sat.ndmi.toFixed(2) + '</span>';
  }

  document.getElementById('farmer-kn-script').textContent =
    drought.recommendation_kn || drought.recommendation_en;

  updatePmfbyGuidelinesUI(data);

  // ── Regional Office Monitor fields ─────────────────────────────────────────
  document.getElementById('val-officer-stage').textContent = drought.stage_label;
  document.getElementById('val-officer-scene').textContent =
    'Scene: ' + sat.scene_date + ' · ' + sat.data_source;
  document.getElementById('val-ndvi').textContent = sat.ndvi.toFixed(4);
  document.getElementById('val-ndmi').textContent = sat.ndmi.toFixed(4);
  document.getElementById('val-ndre').textContent = sat.ndre.toFixed(4);

  var baselineArr = ts.baseline_ndvi || [];
  var latestBase = baselineArr.length ? baselineArr[baselineArr.length - 1] : null;
  if (latestBase !== null) {
    var diff = sat.ndvi - latestBase;
    var sign = diff >= 0 ? '+' : '';
    document.getElementById('val-ndvi-delta').textContent =
      sign + diff.toFixed(3) + ' vs baseline (' + latestBase.toFixed(2) + ')';
  }

  renderForensicSummary(ts, sat);

  if (data.pdf_sha256) {
    updateDossierUI(data.pdf_sha256, data.pdf_download_url, true, data.plot_id, data.analysed_at);
  } else {
    updateDossierUI(null, null, false, data.plot_id, null);
  }

  // Render charts for active mode
  if (activeMode === 'farmer') {
    renderFarmerChart(ts, vsurv);
  } else {
    renderOfficerChart(ts, drought);
  }
}

function updateDossierUI(sha256, downloadUrl, isVerified, plotId, timestampIso) {
  var $pill = document.getElementById('dossier-verify-status');
  var $hash = document.getElementById('pdf-hash-display');
  var $meta = document.getElementById('dossier-meta-display');
  var $dl   = document.getElementById('pdf-download-link');
  var $copy = document.getElementById('btn-copy-hash');

  $meta.textContent = 'Plot ID: ' + (plotId || '—') +
    (timestampIso ? ' · Verified: ' + new Date(timestampIso).toLocaleString('en-IN') : '');

  if (sha256) {
    $hash.textContent = sha256;
    $dl.href = downloadUrl || '#';
    $dl.style.display = downloadUrl ? 'inline-flex' : 'none';
    $copy.style.display = 'inline-flex';
    $pill.className = isVerified ? 'verify-pill verified' : 'verify-pill';
    $pill.textContent = isVerified
      ? '✅ ClaimDossier Verified (SHA-256 Registry)'
      : '⏳ Generated (Click Generate to Verify)';
  } else {
    $hash.textContent = '—';
    $dl.style.display = 'none';
    $copy.style.display = 'none';
    $pill.className = 'verify-pill';
    $pill.textContent = '⏳ Click "Generate PMFBY Audit Dossier (PDF)"';
  }
}

function renderForensicSummary(ts, sat) {
  var $badge    = document.getElementById('forensic-onset-badge');
  var $sum      = document.getElementById('forensic-summary');
  var $takeaway = document.getElementById('officer-chart-takeaway');
  var dates     = ts.dates || [];
  var ndvi      = ts.ndvi || [];
  var base      = ts.baseline_ndvi || [];

  var maxDropPct = 0;
  for (var i = 0; i < Math.min(ndvi.length, base.length); i++) {
    if (base[i] > 0.1) {
      var drop = ((base[i] - ndvi[i]) / base[i]) * 100;
      if (drop > maxDropPct) {
        maxDropPct = drop;
      }
    }
  }

  if (ts.stress_onset_date) {
    var days = ts.days_since_stress_onset != null ? ts.days_since_stress_onset : 60;
    $badge.className = 'forensic-badge stress';
    $badge.textContent = '⚠ Drought Started: ' + ts.stress_onset_date + ' (' + days + 'd proof)';
    $sum.innerHTML =
      '<span><strong>Drought Started:</strong> ' + escHtml(ts.stress_onset_date) + '</span>' +
      '<span><strong>Crop Drop (%):</strong> −' + maxDropPct.toFixed(0) + '% below normal</span>' +
      '<span><strong>Proof Window (Days):</strong> ' + days + ' days tracked (60+ day post-harvest proof)</span>' +
      '<span><strong>Cloud Cover:</strong> ' + Number(sat.cloud_cover_pct || 0).toFixed(1) + '%</span>';
    if ($takeaway) {
      $takeaway.className = 'officer-takeaway stress';
      $takeaway.textContent =
        'Takeaway: Crop condition dropped ' + maxDropPct.toFixed(0) + '% below a normal year starting ' +
        ts.stress_onset_date + ' — this ' + days +
        '-day satellite trail proves drought loss even after harvest or late rain.';
    }
  } else {
    $badge.className = 'forensic-badge';
    $badge.textContent = '✅ Healthy Season';
    $sum.innerHTML =
      '<span><strong>Drought Started:</strong> None (Healthy)</span>' +
      '<span><strong>Crop Drop (%):</strong> ' + maxDropPct.toFixed(0) + '% vs normal</span>' +
      '<span><strong>Proof Window (Days):</strong> ' + dates.length + ' seasonal checks</span>' +
      '<span><strong>Cloud Cover:</strong> ' + Number(sat.cloud_cover_pct || 0).toFixed(1) + '%</span>';
    if ($takeaway) {
      $takeaway.className = 'officer-takeaway';
      $takeaway.textContent =
        'Takeaway: Crop health stayed close to a normal healthy year across all ' + dates.length +
        ' satellite checks, with no drought trigger.';
    }
  }
}

function stageClass(stage) {
  if (stage === 'healthy')          return 'healthy';
  if (stage === 'early_stress')     return 'early';
  if (stage === 'moderate_drought') return 'moderate';
  if (stage === 'severe_drought')   return 'severe';
  return 'healthy';
}

// ── Chart.js: Simple Single-Axis Farmer Soil Water Level Chart ───────────────
function renderFarmerChart(ts, survivalLiters) {
  if (typeof Chart === 'undefined') return;
  var canvas = document.getElementById('farmer-trend-chart');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  if (farmerChart) farmerChart.destroy();

  var dates = ts.dates || [];
  var sm    = ts.soil_moisture || [];
  var safeThreshold = 20;
  var safeLine = dates.map(function() { return safeThreshold; });

  var dangerZonePlugin = {
    id: 'survivalDangerZone',
    beforeDatasetsDraw: function(chart) {
      var yScale = chart.scales.y;
      var xScale = chart.scales.x;
      var y20 = yScale.getPixelForValue(safeThreshold);
      var y0 = yScale.getPixelForValue(0);
      var c = chart.ctx;

      c.save();
      c.fillStyle = 'rgba(220, 38, 38, 0.09)';
      c.fillRect(xScale.left, y20, xScale.right - xScale.left, Math.max(0, y0 - y20));

      c.fillStyle = '#b91c1c';
      c.font = '600 11px -apple-system, BlinkMacSystemFont, sans-serif';
      c.textAlign = 'right';
      c.fillText('Survival Irrigation Needed (< 20%)', xScale.right - 8, Math.min(y0 - 8, y20 + 16));
      c.restore();
    }
  };

  farmerChart = new Chart(ctx, {
    type: 'line',
    plugins: [dangerZonePlugin],
    data: {
      labels: dates,
      datasets: [
        {
          label: "Your Plot's Soil Water (%)",
          data: sm,
          borderColor: '#0066CC',
          backgroundColor: 'rgba(0, 102, 204, 0.12)',
          borderWidth: 3,
          fill: true,
          tension: 0.35,
          pointRadius: 4
        },
        {
          label: 'Minimum Safe Level for Crop Survival (20%)',
          data: safeLine,
          borderColor: '#DC2626',
          borderWidth: 2,
          borderDash: [6, 4],
          fill: false,
          pointRadius: 0
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#1D1D1F', font: { size: 12, weight: '600' } }
        },
        tooltip: {
          callbacks: {
            label: function(item) {
              var v = Number(item.parsed.y).toFixed(1);
              return item.dataset.label + ': ' + v + '%';
            }
          }
        }
      },
      scales: {
        y: {
          type: 'linear',
          position: 'left',
          min: 0,
          max: 50,
          grid: { color: '#E8E8ED' },
          ticks: {
            color: '#0066CC',
            font: { size: 12 },
            callback: function(v) { return v + '%'; }
          },
          title: { display: true, text: 'Soil Water (%)', color: '#0066CC' }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#6E6E73', font: { size: 11 } }
        }
      }
    }
  });

  var $takeaway = document.getElementById('farmer-chart-takeaway');
  if ($takeaway) {
    var dropIdx = sm.findIndex(function(v) { return Number(v) < safeThreshold; });
    var litresTxt = survivalLiters ? Math.round(Number(survivalLiters)).toLocaleString('en-IN') : '0';
    if (dropIdx !== -1) {
      $takeaway.className = 'farmer-chart-takeaway needs-water';
      $takeaway.textContent =
        'Soil water dropped below the 20% safe line around ' + (dates[dropIdx] || 'mid-season') +
        ' — irrigate only the root zone with the exact ' + litresTxt + ' litres shown above.';
    } else {
      $takeaway.className = 'farmer-chart-takeaway';
      $takeaway.textContent =
        'Soil water stayed above the 20% safe line across the season — no emergency survival irrigation needed.';
    }
  }
}

// ── Chart.js: Regional Office Simple-Language Crop & Moisture Audit Chart ────
function toConditionPct(v) {
  return Math.round(Math.max(0, Math.min(100, Number(v || 0) * 100)));
}
function toMoisturePct(v) {
  return Math.round(Math.max(0, Math.min(100, ((Number(v || 0) + 0.6) / 1.0) * 100)));
}

function renderOfficerChart(ts, drought) {
  if (typeof Chart === 'undefined') return;
  var canvas = document.getElementById('officer-timeseries-chart');
  if (!canvas) return;
  var ctx = canvas.getContext('2d');
  if (officerChart) officerChart.destroy();

  var dates    = ts.dates || [];
  var ndvi     = (ts.ndvi || []).map(toConditionPct);
  var baseNdvi = (ts.baseline_ndvi || []).map(toConditionPct);
  var ndmi     = (ts.ndmi || []).map(toMoisturePct);
  var ndre     = (ts.ndre || []).map(toConditionPct);
  var onsetIdx = ts.stress_onset_index;
  var onsetDate = ts.stress_onset_date;
  var daysSince = ts.days_since_stress_onset;

  var isSevere = drought && drought.stage === 'severe_drought';
  var accentColor = isSevere ? '#B64400' : '#FF791B';

  // Inline annotation plugin to mark when drought started for post-harvest proof
  var stressAnnotationPlugin = {
    id: 'stressOnsetMarker',
    afterDatasetsDraw: function(chart) {
      if (onsetIdx === null || onsetIdx === undefined || onsetIdx < 0 || onsetIdx >= dates.length) {
        return;
      }
      var xScale = chart.scales.x;
      var yScale = chart.scales.y;
      var xPos = xScale.getPixelForValue(onsetIdx);
      var rightX = xScale.getPixelForValue(dates.length - 1);
      var c = chart.ctx;

      c.save();

      c.fillStyle = isSevere ? 'rgba(182, 68, 0, 0.08)' : 'rgba(255, 121, 27, 0.08)';
      c.fillRect(xPos, yScale.top, Math.max(0, rightX - xPos), yScale.bottom - yScale.top);

      c.beginPath();
      c.setLineDash([6, 4]);
      c.strokeStyle = accentColor;
      c.lineWidth = 2;
      c.moveTo(xPos, yScale.top);
      c.lineTo(xPos, yScale.bottom);
      c.stroke();

      var label = 'Drought Started: ' + (onsetDate || dates[onsetIdx]) +
        (daysSince ? ' (' + daysSince + 'd proof)' : '');
      c.font = '600 11px -apple-system, BlinkMacSystemFont, sans-serif';
      var textW = c.measureText(label).width;
      var padX = 8;
      var boxW = textW + padX * 2;
      var boxH = 22;
      var boxX = Math.min(Math.max(xPos - boxW / 2, yScale.left + 4), xScale.right - boxW - 4);
      var boxY = yScale.top + 6;

      c.fillStyle = accentColor;
      c.beginPath();
      if (c.roundRect) {
        c.roundRect(boxX, boxY, boxW, boxH, 11);
      } else {
        c.rect(boxX, boxY, boxW, boxH);
      }
      c.fill();

      c.fillStyle = '#FFFFFF';
      c.textAlign = 'center';
      c.textBaseline = 'middle';
      c.fillText(label, boxX + boxW / 2, boxY + boxH / 2);

      c.restore();
    }
  };

  officerChart = new Chart(ctx, {
    type: 'line',
    plugins: [stressAnnotationPlugin],
    data: {
      labels: dates,
      datasets: [
        {
          label: 'Normal Healthy Crop (%)',
          data: baseNdvi,
          borderColor: '#0066CC',
          backgroundColor: 'rgba(0, 102, 204, 0.06)',
          borderWidth: 2,
          borderDash: [6, 5],
          tension: 0.35,
          pointRadius: 3
        },
        {
          label: 'Actual Crop Condition (%)',
          data: ndvi,
          borderColor: accentColor,
          backgroundColor: isSevere ? 'rgba(182, 68, 0, 0.12)' : 'rgba(255, 121, 27, 0.12)',
          borderWidth: 3,
          fill: false,
          tension: 0.3,
          pointRadius: 4
        },
        {
          label: 'Leaf Moisture Trend (%)',
          data: ndmi,
          borderColor: '#1D1D1F',
          borderWidth: 2,
          tension: 0.3,
          pointRadius: 3
        },
        {
          label: 'Leaf Greenness (%)',
          data: ndre,
          borderColor: '#6E6E73',
          borderWidth: 2,
          borderDash: [2, 3],
          tension: 0.3,
          pointRadius: 2
        }
      ]
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      interaction: { mode: 'index', intersect: false },
      plugins: {
        legend: {
          position: 'top',
          labels: { color: '#1D1D1F', font: { size: 12, weight: '600' } }
        },
        tooltip: {
          callbacks: {
            label: function(item) {
              var val = Math.round(Number(item.parsed.y));
              var note = val >= 50 ? 'Healthy' : (val >= 28 ? 'Moderate stress' : 'Severe stress');
              return item.dataset.label + ': ' + val + '% (' + note + ')';
            }
          }
        }
      },
      scales: {
        y: {
          min: 0,
          max: 100,
          grid: { color: '#E8E8ED' },
          ticks: {
            color: '#6E6E73',
            font: { size: 12 },
            callback: function(v) { return v + '%'; }
          },
          title: { display: true, text: 'Crop & Moisture Health (0–100%)', color: '#6E6E73' }
        },
        x: {
          grid: { display: false },
          ticks: { color: '#1D1D1F', font: { size: 11, weight: '600' } }
        }
      }
    }
  });
}

// ── Plots History Page ────────────────────────────────────────────────────────
async function loadPlotsHistory() {
  var $container = document.getElementById('plots-list-container');
  $container.innerHTML = '<div class="empty-state"><p>Loading analysed plots…</p></div>';
  try {
    var data = await authFetchJSON('/api/history');
    renderPlots(data);
  } catch (err) {
    $container.innerHTML =
      '<p style="color:var(--color-3);">Failed to load plots: ' + escHtml(err.message) + '</p>';
  }
}

function openHistoryPage(updateHash) {
  isHistoryOpen = true;
  document.getElementById('workspace-view').style.display = 'none';
  document.getElementById('plots-section').style.display = 'block';

  var $btn = document.getElementById('btn-view-plots');
  $btn.setAttribute('aria-expanded', 'true');
  $btn.classList.add('active');

  if (updateHash && window.location.hash !== '#history') {
    window.history.pushState(null, '', '#history');
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
  loadPlotsHistory();
}

function closeHistoryPage(updateHash) {
  isHistoryOpen = false;
  document.getElementById('plots-section').style.display = 'none';
  document.getElementById('workspace-view').style.display = 'block';

  var $btn = document.getElementById('btn-view-plots');
  $btn.setAttribute('aria-expanded', 'false');
  $btn.classList.remove('active');

  if (updateHash && window.location.hash === '#history') {
    window.history.pushState(null, '', window.location.pathname + window.location.search);
  }
  if (map) {
    setTimeout(function() { map.invalidateSize(); }, 80);
  }
  window.scrollTo({ top: 0, behavior: 'smooth' });
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
    var ndviTxt = p.ndvi != null ? 'NDVI ' + Number(p.ndvi).toFixed(2) : '';
    var ndmiTxt = p.ndmi != null ? 'NDMI ' + Number(p.ndmi).toFixed(2) : '';
    var surveyTxt = p.survey_no ? ('Sy. ' + p.survey_no + (p.village ? ' (' + p.village + ')' : '')) : (p.village || '');
    var indices = [surveyTxt, ndviTxt, ndmiTxt].filter(Boolean).join(' · ');
    var thumbHtml = p.photo_url
      ? '<img class="audit-photo-thumb" data-auth-photo-url="' + escHtml(p.photo_url) + '" alt="Field photo for ' + escHtml(p.farmer_name) + '" />'
      : '';
    var gpsStatus = p.geolock_status || 'MISSING_GPS';
    var photoMeta = p.photo_sha256
      ? (' · ' + gpsStatus + ' · Photo SHA-256: ' + p.photo_sha256.slice(0, 12) + '…')
      : (' · ' + gpsStatus);
    var pdfLink = p.pdf_download_url
      ? ' <a href="' + escHtml(p.pdf_download_url) + '" download class="btn-secondary regional-row-btn" style="text-decoration:none;margin-left:6px;">⬇ PDF</a>'
      : '';
    return '<div class="plot-row" role="listitem">' +
      (thumbHtml ? '<div style="margin-right:10px;">' + thumbHtml + '</div>' : '') +
      '<div style="flex:1;"><div class="plot-row-name">' + escHtml(p.farmer_name) + '</div>' +
      '<div class="plot-row-meta">' + escHtml(p.crop_type) + ' · ' + escHtml(p.taluk) + ' · ' + p.area_acres.toFixed(1) + ' ac' +
      (indices ? ' · ' + escHtml(indices) : '') + escHtml(photoMeta) + '</div></div>' +
      '<span class="drought-badge ' + cls + '" style="font-size:var(--text-base);padding:var(--space-1) var(--space-4);">' +
        escHtml((p.drought_stage || 'unknown').replace('_', ' ')) + '</span>' +
      '<div class="plot-row-meta">' + new Date(p.created_at).toLocaleString('en-IN') + pdfLink + '</div>' +
      '</div>';
  }).join('');
  container.innerHTML = '<div class="plots-list" role="list">' + rows + '</div>' +
    '<p style="font-size:var(--text-base);color:var(--color-4);margin-top:var(--space-5);">' + data.total + ' plot' + (data.total !== 1 ? 's' : '') + ' total</p>';
  loadAuthenticatedPhotoThumbs(container);
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
    $el.textContent = 'No polygon drawn yet. Use the draw tool on the map or tap a preset.';
    $el.style.color = 'var(--color-4)';
  }
}

// ── API helpers ───────────────────────────────────────────────────────────────
async function fetchJSON(url, options) {
  var res = await fetch(API_BASE + url, options || {});
  if (!res.ok) {
    var detail = 'HTTP ' + res.status;
    try { var body = await res.json(); detail = body.detail || JSON.stringify(body); } catch (e) {}
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

// ── PMFBY Guidelines, Payout Estimator & Live Checklist ──────────────────────
var CROP_SCALE_PER_ACRE = {
  ragi: 45000,
  groundnut: 45000,
  maize: 42000,
  tomato: 65000,
  cotton: 52000,
  rice: 58000,
  sunflower: 40000,
  sorghum: 38000
};

function resetFarmerPlotForm() {
  var $form = document.getElementById('analyze-form');
  if ($form) $form.reset();
  document.querySelectorAll('.symptom-chip.active').forEach(function(c) {
    c.classList.remove('active');
    c.setAttribute('aria-pressed', 'false');
  });
  document.querySelectorAll('.btn-preset.selected').forEach(function(b) {
    b.classList.remove('selected');
    b.setAttribute('aria-pressed', 'false');
  });
  capturedPhotoData = null;
  var $photoPreview = document.getElementById('photo-preview-box');
  if ($photoPreview) $photoPreview.style.display = 'none';
  var $photoInput = document.getElementById('field-photo-input');
  if ($photoInput) $photoInput.value = '';
  drawnPolygon = null;
  selectedCadastral = null;
  if (drawnItems) drawnItems.clearLayers();
  updatePolygonStatus(0);
  var $cadMeta = document.getElementById('cad-parcel-meta');
  if ($cadMeta) { $cadMeta.textContent = ''; $cadMeta.classList.remove('visible'); }
  currentResult = null;
  var $results = document.getElementById('results-section');
  if ($results) $results.classList.remove('visible');
  var $eligCard = document.getElementById('farmer-eligibility-card');
  if ($eligCard) $eligCard.style.display = 'none';
  updatePmfbyGuidelinesUI(null);
  updateFarmerHeroTitle();
  showToast('🧹 Cleared form for a new plot', 'success');
}

function updatePmfbyGuidelinesUI(analysisData) {
  var $checkSubbox = document.getElementById('pmfby-checklist-subbox');
  var $estSubbox = document.getElementById('pmfby-estimator-subbox');
  var $proofSubbox = document.getElementById('pmfby-trust-proof-box');
  var hasAnalysis = Boolean(analysisData && analysisData.plot_id);
  if ($checkSubbox) $checkSubbox.style.display = hasAnalysis ? 'block' : 'none';
  if ($estSubbox) $estSubbox.style.display = hasAnalysis ? 'block' : 'none';
  if ($proofSubbox) $proofSubbox.style.display = hasAnalysis ? 'block' : 'none';
  var $copyBtn = document.getElementById('btn-copy-claim-summary');
  if ($copyBtn) $copyBtn.disabled = !hasAnalysis;
  if (!hasAnalysis) {
    var $vBtnReset = document.getElementById('btn-trust-verify');
    if ($vBtnReset) $vBtnReset.disabled = true;
    return;
  }
  var areaEl = document.getElementById('area-acres');
  var cropEl = document.getElementById('crop-type');
  var talukEl = document.getElementById('taluk');
  var surveyEl = document.getElementById('survey-no');
  var irrEl = document.getElementById('irrigation-source');

  var acres = parseFloat(areaEl && areaEl.value ? areaEl.value : '2.5');
  if (isNaN(acres) || acres <= 0) acres = 2.5;
  var crop = (analysisData && analysisData.crop_type) || (cropEl && cropEl.value) || 'Ragi';
  var taluk = (analysisData && analysisData.taluk) || (talukEl && talukEl.value) || '';
  var surveyNo = (analysisData && analysisData.survey_no) || (surveyEl && surveyEl.value.trim()) || '';
  var irrSource = (analysisData && analysisData.irrigation_source) || (irrEl && irrEl.value) || 'Purely Rain-Fed';

  var cropKey = crop.toLowerCase();
  var scalePerAcre = CROP_SCALE_PER_ACRE[cropKey] || 45000;
  var isCommercial = cropKey === 'tomato' || cropKey === 'cotton';
  var farmerRate = isCommercial ? 0.05 : 0.02;
  var actuarialRate = isCommercial ? 0.12 : 0.10;

  var sumInsured = Math.round(acres * scalePerAcre);
  var farmerPrem = Math.round(sumInsured * farmerRate);
  var govtSubsidy = Math.max(0, Math.round(sumInsured * actuarialRate) - farmerPrem);
  var minTrigger = Math.round(sumInsured * 0.25);
  var maxTrigger = Math.round(sumInsured * 0.60);

  var $sub = document.getElementById('pmfby-estimator-subtitle');
  if ($sub) {
    $sub.textContent = '💰 Dynamic Plot Payout Estimator (' + acres.toFixed(1) + ' ac · ' + crop + ')';
  }
  var $sumEl = document.getElementById('est-sum-insured');
  var $rateEl = document.getElementById('est-rate-label');
  var $premEl = document.getElementById('est-farmer-premium');
  var $subEl = document.getElementById('est-govt-subsidy');
  var $rngEl = document.getElementById('est-claim-range');
  if ($sumEl) $sumEl.textContent = '₹' + sumInsured.toLocaleString('en-IN');
  if ($rateEl) $rateEl.textContent = 'Farmer Share (' + (farmerRate * 100).toFixed(1) + '%)';
  if ($premEl) $premEl.textContent = '₹' + farmerPrem.toLocaleString('en-IN');
  if ($subEl) $subEl.textContent = '₹' + govtSubsidy.toLocaleString('en-IN');
  if ($rngEl) $rngEl.textContent = '₹' + minTrigger.toLocaleString('en-IN') + ' – ₹' + maxTrigger.toLocaleString('en-IN');

  var $list = document.getElementById('pmfby-live-checklist');
  if ($list) {
    var hasCrop = Boolean(cropEl && cropEl.value) || Boolean(analysisData);
    var hasLoc = Boolean(taluk) || Boolean(surveyNo);
    var hasGps = analysisData
      ? (analysisData.geolock_status === 'VERIFIED_IN_REGION' || analysisData.geolock_status === 'DISTRICT_MATCH_NEARBY')
      : Boolean(capturedPhotoData && capturedPhotoData.lat != null && !capturedPhotoData.isMismatchDemo);
    var gpsWarn = analysisData
      ? analysisData.geolock_status
      : (capturedPhotoData && capturedPhotoData.isMismatchDemo ? 'OUTSIDE_REGION_WARNING' : (hasGps ? 'GPS Locked' : 'Pending GPS'));

    var deficitStatus = analysisData
      ? (analysisData.pmfby_eligible || 'Evaluated')
      : 'Run Analyse Plot to check satellite deficit';
    var deficitPass = analysisData && analysisData.drought && analysisData.drought.stage !== 'healthy';

    var items = [
      { ok: hasCrop, text: hasCrop ? ('Notified Crop: ' + crop) : 'Select a notified crop (e.g. Ragi, Groundnut)' },
      { ok: hasLoc, text: hasLoc ? ('Taluk / Survey: ' + (taluk || 'Tumakuru') + (surveyNo ? ' · Sy. ' + surveyNo : '')) : 'Select Taluk or Bhoomi Survey No.' },
      { ok: Boolean(irrSource), text: 'Water Source: ' + irrSource },
      { ok: hasGps, text: 'Field Photo GPS: ' + gpsWarn },
      { ok: deficitPass, text: 'Moisture Deficit Check: ' + deficitStatus }
    ];

    $list.innerHTML = items.map(function(it) {
      return '<li class="pmfby-check-item ' + (it.ok ? 'pass' : 'warn') + '">' +
        '<span>' + (it.ok ? '✅' : '⚠️') + '</span>' +
        '<span>' + escHtml(it.text) + '</span>' +
      '</li>';
    }).join('');
  }

  var $dId = document.getElementById('trust-dossier-id');
  var $pHash = document.getElementById('trust-photo-hash');
  var $dHash = document.getElementById('trust-dossier-hash');
  var $satTs = document.getElementById('trust-sat-timestamp');
  var $vBtn = document.getElementById('btn-trust-verify');
  if ($dId && $pHash && $dHash && $satTs) {
    if (analysisData) {
      $dId.textContent = analysisData.dossier_id || analysisData.plot_id || '—';
      $pHash.textContent = analysisData.photo_sha256 || 'No camera photo uploaded';
      $dHash.textContent = analysisData.pdf_sha256 || 'Pending PDF generation';
      $satTs.textContent = (analysisData.satellite && analysisData.satellite.scene_date) || analysisData.analysed_at || '—';
      if ($vBtn) $vBtn.disabled = !analysisData.pdf_sha256;
    } else {
      $dId.textContent = 'Run Analyse Plot to generate';
      $pHash.textContent = '—';
      $dHash.textContent = '—';
      $satTs.textContent = '—';
      if ($vBtn) $vBtn.disabled = true;
    }
  }
  var $proofPhotoWrap = document.getElementById('farmer-proof-photo-wrap');
  var $proofPhotoImg = document.getElementById('farmer-proof-photo-img');
  var $proofPhotoMeta = document.getElementById('farmer-proof-photo-meta');
  if ($proofPhotoWrap && $proofPhotoImg && $proofPhotoMeta) {
    var hasLocalPhoto = Boolean(capturedPhotoData && capturedPhotoData.base64);
    if (hasLocalPhoto && (!analysisData || analysisData.photo_attached)) {
      $proofPhotoImg.src = capturedPhotoData.base64;
      $proofPhotoMeta.textContent = analysisData
        ? ('Saved Field Photo · ' + (analysisData.geolock_status || 'MISSING_GPS') +
           (analysisData.photo_sha256 ? ' · SHA-256: ' + analysisData.photo_sha256.slice(0, 14) + '…' : ''))
        : ('Attached Field Photo ready for submission (' + (capturedPhotoData.filename || 'photo') + ')');
      $proofPhotoWrap.style.display = 'flex';
    } else {
      $proofPhotoImg.removeAttribute('src');
      $proofPhotoWrap.style.display = 'none';
    }
  }
}

// ── Officer Auth Helpers ─────────────────────────────────────────────────────
function openOfficerLoginModal(nextAction) {
  pendingOfficerAction = nextAction || 'officer';
  var $modal = document.getElementById('modal-officer-login');
  hideErrors(document.getElementById('officer-login-error'));
  $modal.classList.add('open');
  document.getElementById('officer-username').focus();
}

function updateOfficerBadgeUI() {
  var $badge = document.getElementById('officer-auth-badge');
  if ($badge) {
    $badge.style.display = officerToken ? 'inline-flex' : 'none';
  }
}

function clearOfficerSession() {
  officerToken = '';
  try { sessionStorage.removeItem('sookshmajal_officer_token'); } catch (e) {}
  updateOfficerBadgeUI();
  if (regionalHeatLayer) regionalHeatLayer.clearLayers();
  if (isHistoryOpen) closeHistoryPage(true);
  if (activeMode === 'officer') setMode('farmer');
}

async function authFetchJSON(url, options) {
  var opts = Object.assign({}, options || {});
  opts.headers = Object.assign({}, opts.headers || {}, {
    Authorization: 'Bearer ' + officerToken
  });
  var res = await fetch(API_BASE + url, opts);
  if (res.status === 401) {
    clearOfficerSession();
    openOfficerLoginModal(isHistoryOpen ? 'history' : 'officer');
    throw new Error('Officer session required or expired.');
  }
  if (!res.ok) {
    var detail = 'HTTP ' + res.status;
    try { var body = await res.json(); detail = body.detail || JSON.stringify(body); } catch (e) {}
    throw new Error(detail);
  }
  return res.json();
}

var TALUK_TO_DISTRICT = {
  Madhugiri: 'Tumakuru', Koratagere: 'Tumakuru', Chikkanayakanahalli: 'Tumakuru',
  Tumakuru: 'Tumakuru', Pavagada: 'Tumakuru', Tiptur: 'Tumakuru',
  Turuvekere: 'Tumakuru', Kunigal: 'Tumakuru', Sira: 'Tumakuru', Gubbi: 'Tumakuru',
  Challakere: 'Chitradurga', Hiriyur: 'Chitradurga',
  Bagepalli: 'Chikkaballapur', Mulbagal: 'Kolar', Kolar: 'Kolar',
  Kalaburagi: 'Kalaburagi', Vijayapura: 'Vijayapura',
  Ballari: 'Ballari', Koppal: 'Koppal', Raichur: 'Raichur', Haveri: 'Haveri'
};

function updateFarmerHeroTitle() {
  if (activeMode !== 'farmer') return;
  var $taluk = document.getElementById('taluk');
  var $heroTitle = document.getElementById('hero-title');
  if (!$heroTitle) return;
  var talukVal = $taluk && $taluk.value ? $taluk.value : '';
  var dist = TALUK_TO_DISTRICT[talukVal] || 'Karnataka';
  $heroTitle.innerHTML = 'Precision Survival Water Coaching<br />for ' + escHtml(dist) + ' Farmers';
}

function markPhotoUnavailable(img) {
  if (!img || !img.parentNode) return;
  var span = document.createElement('span');
  span.className = 'photo-unavailable-label';
  span.textContent = 'Photo unavailable';
  img.parentNode.replaceChild(span, img);
}

function loadAuthenticatedPhotoThumbs(containerEl) {
  if (!containerEl || !officerToken) return;
  containerEl.querySelectorAll('img[data-auth-photo-url]').forEach(async function(img) {
    var url = img.getAttribute('data-auth-photo-url');
    if (!url) {
      markPhotoUnavailable(img);
      return;
    }
    img.onerror = function() { markPhotoUnavailable(img); };
    try {
      var res = await fetch(url, {
        headers: { Authorization: 'Bearer ' + officerToken }
      });
      if (!res.ok) {
        markPhotoUnavailable(img);
        return;
      }
      var blob = await res.blob();
      img.src = URL.createObjectURL(blob);
    } catch (e) {
      markPhotoUnavailable(img);
    }
  });
}

async function openOfficerPhotoPreview(plotId) {
  var item = regionalPlots.find(function(p) { return p.plot_id === plotId; });
  if (!item || !item.photo_url) return;
  try {
    var res = await fetch(item.photo_url, {
      headers: { Authorization: 'Bearer ' + officerToken }
    });
    if (!res.ok) throw new Error('HTTP ' + res.status);
    var blob = await res.blob();
    var objUrl = URL.createObjectURL(blob);
    var $img = document.getElementById('photo-modal-img');
    $img.src = objUrl;
    var gpsTxt = (item.photo_lat != null && item.photo_lon != null)
      ? Number(item.photo_lat).toFixed(5) + '°N, ' + Number(item.photo_lon).toFixed(5) + '°E'
      : 'Plot centroid';
    document.getElementById('photo-modal-meta').textContent =
      item.farmer_name + ' · GPS: ' + gpsTxt +
      (item.photo_sha256 ? ' · Photo SHA-256: ' + item.photo_sha256.slice(0, 16) + '…' : '');
    document.getElementById('modal-photo-preview').classList.add('open');
  } catch (err) {
    showToast('❌ Could not load field photo: ' + err.message, 'error');
  }
}

// ── Regional Taluk Monitor (Insurance Claim Mode) ────────────────────────────
var STAGE_LABELS = {
  healthy: 'Healthy',
  early_stress: 'Early Stress',
  moderate_drought: 'Moderate Drought',
  severe_drought: 'Severe Drought'
};

function renderRegionalHeatmap(plots) {
  if (!map || !regionalHeatLayer) return;
  regionalHeatLayer.clearLayers();
  if (activeMode !== 'officer' || !plots || plots.length === 0) return;

  var bounds = [];
  plots.forEach(function(p) {
    var stage = p.drought_stage || 'healthy';
    var color = stage === 'severe_drought'
      ? '#dc2626'
      : (stage === 'healthy' ? '#16a34a' : '#f59e0b');

    var circle = L.circle([p.centroid_lat, p.centroid_lon], {
      radius: 4500,
      color: color,
      weight: 1.5,
      fillColor: color,
      fillOpacity: 0.28
    });
    var surveyLabel = p.survey_no ? ('Sy. No. ' + escHtml(p.survey_no)) : 'Polygon';
    circle.bindPopup(
      '<strong>' + escHtml(p.farmer_name) + '</strong><br/>' +
      escHtml(p.taluk) + ' (' + escHtml(p.district || 'Tumakuru') + ') · ' + surveyLabel + '<br/>' +
      'Stage: <strong>' + escHtml(STAGE_LABELS[stage] || stage) + '</strong>'
    );
    circle.on('click', function() { selectRegionalPlot(p.plot_id, false); });
    regionalHeatLayer.addLayer(circle);

    if (p.polygon_coordinates && p.polygon_coordinates.length >= 4) {
      var latlngs = p.polygon_coordinates.slice(0, -1).map(function(c) { return [c[1], c[0]]; });
      var poly = L.polygon(latlngs, { color: color, weight: 2, fillColor: color, fillOpacity: 0.35 });
      poly.on('click', function() { selectRegionalPlot(p.plot_id, false); });
      regionalHeatLayer.addLayer(poly);
    }
    bounds.push([p.centroid_lat, p.centroid_lon]);
  });

  if (bounds.length > 0 && !selectedRegionalPlotId) {
    map.fitBounds(bounds, { padding: [35, 35], maxZoom: 11 });
    map.invalidateSize();
  }
}

async function loadRegionalSummary(taluk) {
  var $tbody = document.getElementById('regional-table-body');
  if (!$tbody || !officerToken) return;
  try {
    var data = await authFetchJSON('/api/regional/summary?taluk=' + encodeURIComponent(taluk || 'ALL'));
    regionalPlots = data.plots || [];

    document.getElementById('reg-kpi-total').textContent = String(data.total_plots || 0);
    document.getElementById('reg-kpi-acres').textContent =
      Number(data.total_acres || 0).toFixed(1) + ' total acres';
    document.getElementById('reg-kpi-severe').textContent = String(data.severe_count || 0);
    document.getElementById('reg-kpi-moderate').textContent =
      (data.moderate_count || 0) + ' moderate / early stress';
    document.getElementById('reg-kpi-audit').textContent = String(data.ready_for_audit_count || 0);
    document.getElementById('reg-kpi-normal').textContent =
      (data.normal_count || 0) + ' healthy plots';

    renderRegionalHeatmap(regionalPlots);
    renderRegionalTable(getFilteredRegionalPlots());
  } catch (err) {
    $tbody.innerHTML =
      '<tr><td colspan="8" class="regional-empty" style="color:var(--color-3);">Failed to load regional plots: ' +
      escHtml(err.message) + '</td></tr>';
  }
}

function getFilteredRegionalPlots() {
  if (!regionalPlots) return [];
  if (regionalAuditFilter === 'ALL') return regionalPlots;
  if (regionalAuditFilter === 'HAS_PHOTO') {
    return regionalPlots.filter(function(p) { return Boolean(p.photo_attached || p.photo_url); });
  }
  return regionalPlots.filter(function(p) {
    return (p.audit_status || 'PENDING') === regionalAuditFilter;
  });
}

function geolockPillClass(status) {
  if (status === 'VERIFIED_IN_REGION') return 'verified';
  if (status === 'DISTRICT_MATCH_NEARBY') return 'nearby';
  if (status === 'OUTSIDE_REGION_WARNING') return 'outside';
  return 'missing';
}

function renderRegionalTable(plots) {
  var $tbody = document.getElementById('regional-table-body');
  if (!plots || plots.length === 0) {
    $tbody.innerHTML =
      '<tr><td colspan="8" class="regional-empty">No farmer plots match this filter.</td></tr>';
    return;
  }

  $tbody.innerHTML = plots.map(function(p) {
    var stage = p.drought_stage || 'healthy';
    var cls = stageClass(stage);
    var stageText = STAGE_LABELS[stage] || stage.replace('_', ' ');
    var vsurvTxt = p.survival_liters != null
      ? Math.round(Number(p.survival_liters)).toLocaleString('en-IN') + ' L'
      : '—';
    var isSel = selectedRegionalPlotId === p.plot_id;
    var surveyTxt = p.survey_no
      ? ('Sy. ' + escHtml(p.survey_no) + (p.village ? '<br/><span class="plot-row-meta">' + escHtml(p.village) + '</span>' : ''))
      : (p.village ? escHtml(p.village) : '<span class="plot-row-meta">Custom polygon</span>');

    var gStatus = p.geolock_status || 'MISSING_GPS';
    var gCls = geolockPillClass(gStatus);
    var distLabel = p.distance_km != null ? (' (' + Number(p.distance_km).toFixed(1) + ' km)') : '';
    var matchTxt = p.region_match ? 'Match: Yes' : 'Match: No';
    var photoCell = '<span class="geolock-pill ' + gCls + '" title="' + escHtml(matchTxt) + '">' +
      escHtml(gStatus) + escHtml(distLabel) + '</span>' +
      (p.photo_url
        ? '<img class="audit-photo-thumb" data-auth-photo-url="' + escHtml(p.photo_url) +
            '" data-view-photo="' + escHtml(p.plot_id) +
            '" alt="Field photo for ' + escHtml(p.farmer_name) + '" />' +
          (p.photo_sha256 ? '<div class="audit-photo-hash">SHA: ' + escHtml(p.photo_sha256.slice(0, 12)) + '…</div>' : '') +
          '<button type="button" class="btn-secondary regional-row-btn" style="margin-top:3px;" data-view-photo="' +
            escHtml(p.plot_id) + '">📷 View Photo</button>'
        : '');

    var auditStatus = p.audit_status || 'PENDING';
    var auditCls = auditStatus === 'APPROVED' ? 'approved' : (auditStatus === 'DISAPPROVED' ? 'disapproved' : 'pending');
    var entrySrc = p.entry_source || 'Live Farmer Entry';
    var isSeeded = entrySrc.toLowerCase().indexOf('seed') !== -1;
    var dossierBtn = p.pdf_download_url
      ? '<a href="' + escHtml(p.pdf_download_url) + '" download class="btn-secondary regional-row-btn" data-pdf-dl="1" style="text-decoration:none;">⬇ Audit PDF</a>'
      : '<button type="button" class="btn-secondary regional-row-btn" data-generate-plot="' +
          escHtml(p.plot_id) + '">📄 Audit PDF</button>';
    var deleteBtn = auditStatus === 'DISAPPROVED'
      ? '<button type="button" class="btn-audit-delete" data-audit-delete="' + escHtml(p.plot_id) + '">🗑 Delete</button>'
      : '';
    var actionsCell = '<div class="regional-actions-stack">' +
      '<span class="audit-status-pill ' + auditCls + '">' + escHtml(auditStatus) + '</span>' +
      (p.officer_remark ? '<div class="audit-remark-text">' + escHtml(p.officer_remark) + '</div>' : '') +
      '<div class="audit-decision-actions">' +
        '<button type="button" class="btn-audit-approve" data-audit-decision="APPROVED" data-plot-id="' + escHtml(p.plot_id) + '">✅ Approve</button>' +
        '<button type="button" class="btn-audit-disapprove" data-audit-decision="DISAPPROVED" data-plot-id="' + escHtml(p.plot_id) + '">❌ Disapprove</button>' +
        deleteBtn +
      '</div>' +
      dossierBtn +
    '</div>';

    var rowCls = 'regional-row' + (isSel ? ' selected' : '') + (auditStatus === 'DISAPPROVED' ? ' disapproved' : '');
    return '<tr class="' + rowCls + '" data-plot-id="' + escHtml(p.plot_id) + '">' +
      '<td><strong>' + escHtml(p.farmer_name) + '</strong><br/>' +
        '<span class="plot-row-meta">' + escHtml(p.phone_number || new Date(p.created_at).toLocaleDateString('en-IN')) + '</span><br/>' +
        '<span class="entry-source-pill' + (isSeeded ? ' seeded' : '') + '">' + escHtml(entrySrc) + '</span></td>' +
      '<td>' + escHtml(p.taluk) + '<br/><span class="plot-row-meta">' + escHtml(p.district || 'Tumakuru') + '</span></td>' +
      '<td>' + surveyTxt + '</td>' +
      '<td>' + escHtml(p.crop_type) + ' · ' + Number(p.area_acres).toFixed(1) + ' ac</td>' +
      '<td>' + photoCell + '</td>' +
      '<td><span class="drought-badge ' + cls + '" style="font-size:12px;padding:3px 10px;">' +
        escHtml(stageText) + '</span></td>' +
      '<td>' + vsurvTxt + '</td>' +
      '<td>' + actionsCell + '</td>' +
    '</tr>';
  }).join('');

  $tbody.querySelectorAll('.regional-row').forEach(function(row) {
    row.addEventListener('click', function(e) {
      if (e.target && (e.target.closest('[data-generate-plot]') || e.target.closest('[data-view-photo]') || e.target.closest('[data-pdf-dl]') || e.target.closest('[data-audit-decision]') || e.target.closest('[data-audit-delete]'))) return;
      selectRegionalPlot(row.dataset.plotId, false);
    });
  });

  $tbody.querySelectorAll('[data-audit-decision]').forEach(function(btn) {
    btn.addEventListener('click', async function(e) {
      e.stopPropagation();
      var plotId = btn.dataset.plotId;
      var decision = btn.dataset.auditDecision;
      var remarkPrompt = decision === 'DISAPPROVED'
        ? 'Optional reason for disapproving this claim:'
        : 'Optional approval remark:';
      var remark = window.prompt(remarkPrompt, '');
      if (remark === null) return;
      try {
        var updated = await authFetchJSON('/api/audit/' + encodeURIComponent(plotId) + '/decision', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ decision: decision, officer_remark: remark.trim() || null })
        });
        var item = regionalPlots.find(function(x) { return x.plot_id === plotId; });
        if (item) {
          item.audit_status = updated.audit_status;
          item.officer_remark = updated.officer_remark;
          item.reviewed_at = updated.reviewed_at;
          item.pdf_download_url = null;
        }
        renderRegionalTable(getFilteredRegionalPlots());
        showToast('✅ ' + updated.message, 'success');
      } catch (err) {
        showToast('❌ ' + err.message, 'error');
      }
    });
  });

  $tbody.querySelectorAll('[data-audit-delete]').forEach(function(btn) {
    btn.addEventListener('click', async function(e) {
      e.stopPropagation();
      var plotId = btn.dataset.auditDelete;
      if (!window.confirm('Delete this disapproved claim record permanently?')) return;
      try {
        await authFetchJSON('/api/audit/' + encodeURIComponent(plotId), { method: 'DELETE' });
        regionalPlots = regionalPlots.filter(function(x) { return x.plot_id !== plotId; });
        if (selectedRegionalPlotId === plotId) selectedRegionalPlotId = null;
        renderRegionalHeatmap(regionalPlots);
        renderRegionalTable(getFilteredRegionalPlots());
        loadRegionalSummary(regionalTalukFilter);
        showToast('🗑 Disapproved record deleted.', 'success');
      } catch (err) {
        showToast('❌ ' + err.message, 'error');
      }
    });
  });

  $tbody.querySelectorAll('[data-view-photo]').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      openOfficerPhotoPreview(btn.dataset.viewPhoto);
    });
  });

  $tbody.querySelectorAll('[data-pdf-dl]').forEach(function(a) {
    a.addEventListener('click', function(e) { e.stopPropagation(); });
  });

  $tbody.querySelectorAll('[data-generate-plot]').forEach(function(btn) {
    btn.addEventListener('click', function(e) {
      e.stopPropagation();
      selectRegionalPlot(btn.dataset.generatePlot, true);
    });
  });

  loadAuthenticatedPhotoThumbs($tbody);
}

async function selectRegionalPlot(plotId, triggerDossier) {
  var item = regionalPlots.find(function(p) { return p.plot_id === plotId; });
  if (!item) return;

  selectedRegionalPlotId = plotId;
  renderRegionalTable(getFilteredRegionalPlots());

  // Draw polygon on Leaflet map
  if (map && drawnItems && item.polygon_coordinates && item.polygon_coordinates.length >= 4) {
    drawnItems.clearLayers();
    drawnPolygon = item.polygon_coordinates;
    var latlngs = item.polygon_coordinates.slice(0, -1).map(function(c) { return [c[1], c[0]]; });
    var polyColor = item.drought_stage === 'severe_drought'
      ? '#B64400'
      : (item.drought_stage === 'healthy' ? '#0066CC' : '#FF791B');
    var poly = L.polygon(latlngs, { color: polyColor, weight: 2.5, fillOpacity: 0.22 });
    drawnItems.addLayer(poly);
    map.fitBounds(poly.getBounds(), { padding: [24, 24] });
    map.invalidateSize();
    updatePolygonStatus(item.polygon_coordinates.length - 1);
  }

  var stage = item.drought_stage || 'healthy';
  var stageLabel = (STAGE_LABELS[stage] || stage) + ' — Regional Audit View';
  var et0 = item.et0_mm_day != null ? item.et0_mm_day : 4.8;
  var precip = item.precipitation_mm != null ? item.precipitation_mm : 10.0;

  currentResult = {
    plot_id: item.plot_id,
    farmer_name: item.farmer_name,
    taluk: item.taluk,
    crop_type: item.crop_type,
    area_acres: item.area_acres,
    pmfby_eligible: item.pmfby_eligible,
    geolock_status: item.geolock_status,
    region_match: item.region_match,
    distance_km: item.distance_km,
    photo_attached: item.photo_attached,
    centroid_lat: item.centroid_lat,
    centroid_lon: item.centroid_lon,
    satellite: {
      ndvi: item.ndvi != null ? item.ndvi : 0.0,
      ndmi: item.ndmi != null ? item.ndmi : 0.0,
      ndre: item.ndre != null ? item.ndre : 0.0,
      scene_date: item.scene_date || '2026-10-30',
      cloud_cover_pct: 4.5,
      data_source: item.data_source || 'database'
    },
    drought: {
      stage: stage,
      stage_label: stageLabel,
      color_token: stage === 'severe_drought' ? 'color-3' : (stage === 'healthy' ? 'color-2' : 'color-5'),
      ndmi_threshold: item.ndmi != null ? item.ndmi : 0.0,
      ndvi_threshold: item.ndvi != null ? item.ndvi : 0.0,
      recommendation_en: 'Regional audit loaded for ' + item.farmer_name + ' (' + item.taluk + ').',
      recommendation_kn: ''
    },
    hydromet: {
      et0_mm_day: et0,
      precipitation_mm: precip,
      soil_moisture_0_7cm_pct: item.soil_moisture_0_7cm_pct != null ? item.soil_moisture_0_7cm_pct : 18.0,
      survival_liters: item.survival_liters != null ? item.survival_liters : 0.0,
      deficit_mm: Math.max(0, et0 - precip / 7.0)
    },
    time_series: item.time_series || {},
    irrigation_guidance: {},
    audio_base64: null,
    audio_source: 'text_only',
    pdf_sha256: item.dossier_hash,
    pdf_download_url: item.pdf_download_url,
    analysed_at: item.created_at
  };

  renderResults(currentResult);
  var $results = document.getElementById('results-section');
  $results.classList.add('visible');

  if (triggerDossier) {
    document.getElementById('btn-generate-dossier').click();
  } else {
    showToast('📍 Loaded ' + item.farmer_name + ' (' + item.taluk + ') on map & audit chart', 'success');
    requestAnimationFrame(function() {
      document.getElementById('officer-view').scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }
}
