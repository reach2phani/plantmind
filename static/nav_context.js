var PlantMindContext = {

  PLANTS: [],
  LINES:  ["Line 1", "Line 2", "Line 3", "Line 4", "Line 7"],

  loadPlants: function() {
    return fetch('/api/plant-sites')
      .then(function(r) { return r.json(); })
      .then(function(data) {
        PlantMindContext.PLANTS = (data.plant_sites || []).map(function(ps) { return ps.name; });
      })
      .catch(function() {});
  },

  get: function() {
    return {
      plant: localStorage.getItem('pm_plant') || '',
      line:  localStorage.getItem('pm_line')  || ''
    };
  },

  set: function(plant, line) {
    localStorage.setItem('pm_plant', plant);
    localStorage.setItem('pm_line',  line);
    PlantMindContext.updateHeader();
  },

  updateHeader: function() {
    var ctx = PlantMindContext.get();
    var el  = document.getElementById('navCtxText');
    var dot = document.getElementById('navDot');
    var banner = document.getElementById('ctxBanner');
    if (banner) banner.style.display = (!ctx.plant) ? 'flex' : 'none';
    if (!el) return;
    if (ctx.plant && ctx.line) {
      el.textContent = ctx.plant + ' \u00b7 ' + ctx.line;
      if (dot) dot.style.background = '#16a34a';
    } else if (ctx.plant) {
      el.textContent = ctx.plant + ' \u00b7 All lines';
      if (dot) dot.style.background = '#16a34a';
    } else {
      el.textContent = 'Set your context';
      if (dot) dot.style.background = '#94a3b8';
    }
  },

  syncToSelects: function(plantId, lineId) {
    var ctx = PlantMindContext.get();
    var pEl = document.getElementById(plantId);
    var lEl = document.getElementById(lineId);
    if (pEl && ctx.plant) pEl.value = ctx.plant;
    if (lEl && ctx.line)  lEl.value = ctx.line;
  },

  bindSelects: function(plantId, lineId) {
    var pEl = document.getElementById(plantId);
    var lEl = document.getElementById(lineId);
    if (pEl) pEl.addEventListener('change', function() {
      PlantMindContext.set(pEl.value, lEl ? lEl.value : '');
    });
    if (lEl) lEl.addEventListener('change', function() {
      PlantMindContext.set(pEl ? pEl.value : '', lEl.value);
    });
  },

  buildDropdown: function() {
    var existing = document.getElementById('ctxDropdown');
    if (existing) { existing.remove(); return; }
    PlantMindContext.loadPlants().then(function() {
      PlantMindContext._renderDropdown();
    });
  },

  _renderDropdown: function() {
    var ctx = PlantMindContext.get();

    var dd = document.createElement('div');
    dd.id = 'ctxDropdown';
    dd.style.cssText = [
      'position:absolute','top:58px','right:16px','background:#1e293b',
      'border:1px solid #334155','border-radius:10px','padding:14px',
      'z-index:9999','min-width:220px','box-shadow:0 8px 24px rgba(0,0,0,.4)'
    ].join(';');

    dd.innerHTML =
      '<div style="font-size:11px;font-weight:700;color:#64748b;text-transform:uppercase;letter-spacing:.05em;margin-bottom:8px">Your context</div>' +

      '<div style="font-size:11px;color:#94a3b8;margin-bottom:4px">Plant site</div>' +
      '<select id="ctxPlantSel" style="width:100%;padding:7px 10px;background:#0f172a;border:1px solid #334155;border-radius:6px;font-size:13px;color:#e2e8f0;margin-bottom:6px;outline:none">' +
        '<option value="">-- select --</option>' +
        PlantMindContext.PLANTS.map(function(p) {
          return '<option value="' + p + '"' + (ctx.plant === p ? ' selected' : '') + '>' + p + '</option>';
        }).join('') +
        '<option value="__add__">+ Add new plant site</option>' +
      '</select>' +
      '<div id="ctxAddSiteRow" style="display:none;margin-bottom:10px;flex-direction:column;gap:4px">' +
        '<input id="ctxNewSiteName" type="text" placeholder="New plant site name" style="width:100%;padding:7px 10px;background:#0f172a;border:1px solid #334155;border-radius:6px;font-size:13px;color:#e2e8f0;outline:none;box-sizing:border-box">' +
        '<div style="display:flex;gap:4px">' +
          '<button onclick="PlantMindContext.saveNewSiteFromDropdown()" style="flex:1;padding:6px;background:#4f46e5;color:#fff;border:none;border-radius:6px;font-size:12px;cursor:pointer">Add</button>' +
          '<button onclick="PlantMindContext.cancelAddSite()" style="flex:1;padding:6px;background:#1e293b;color:#94a3b8;border:1px solid #334155;border-radius:6px;font-size:12px;cursor:pointer">Cancel</button>' +
        '</div>' +
      '</div>' +

      '<div style="font-size:11px;color:#94a3b8;margin-bottom:4px">Production line</div>' +
      '<select id="ctxLineSel" style="width:100%;padding:7px 10px;background:#0f172a;border:1px solid #334155;border-radius:6px;font-size:13px;color:#e2e8f0;margin-bottom:12px;outline:none">' +
        '<option value="">All lines</option>' +
        PlantMindContext.LINES.map(function(l) {
          return '<option value="' + l + '"' + (ctx.line === l ? ' selected' : '') + '>' + l + '</option>';
        }).join('') +
      '</select>' +

      '<button onclick="PlantMindContext.saveFromDropdown()" style="width:100%;padding:8px;background:#4f46e5;color:#fff;border:none;border-radius:6px;font-size:13px;font-weight:600;cursor:pointer">Save context</button>' +
      '<button onclick="PlantMindContext.clearContext()" style="width:100%;padding:6px;background:transparent;color:#64748b;border:none;font-size:12px;cursor:pointer;margin-top:4px">Clear context</button>';

    document.body.appendChild(dd);

    document.getElementById('ctxPlantSel').addEventListener('change', function() {
      if (this.value === '__add__') {
        this.value = '';
        document.getElementById('ctxAddSiteRow').style.display = 'flex';
        document.getElementById('ctxNewSiteName').focus();
      }
    });

    setTimeout(function() {
      document.addEventListener('click', function handler(e) {
        var pill = document.getElementById('navCtx');
        var drop = document.getElementById('ctxDropdown');
        if (drop && !drop.contains(e.target) && pill && !pill.contains(e.target)) {
          drop.remove();
          document.removeEventListener('click', handler);
        }
      });
    }, 100);
  },

  saveNewSiteFromDropdown: function() {
    var name = (document.getElementById('ctxNewSiteName').value || '').trim();
    if (!name) return;
    fetch('/api/plant-sites', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({name: name})
    })
    .then(function(r) { return r.json(); })
    .then(function(data) {
      if (data.error) { alert(data.error); return; }
      PlantMindContext.loadPlants().then(function() {
        var dd = document.getElementById('ctxDropdown');
        if (dd) dd.remove();
        PlantMindContext._renderDropdown();
        setTimeout(function() {
          var sel = document.getElementById('ctxPlantSel');
          if (sel) sel.value = name;
        }, 50);
      });
    })
    .catch(function() { alert('Failed to save plant site'); });
  },

  cancelAddSite: function() {
    document.getElementById('ctxAddSiteRow').style.display = 'none';
    document.getElementById('ctxNewSiteName').value = '';
  },

  saveFromDropdown: function() {
    var p = document.getElementById('ctxPlantSel');
    var l = document.getElementById('ctxLineSel');
    if (p && l) {
      PlantMindContext.set(p.value, l.value);
      var pf = document.getElementById('plantFilter');
      var lf = document.getElementById('lineFilter');
      if (pf) pf.value = p.value;
      if (lf) lf.value = l.value;
    }
    var dd = document.getElementById('ctxDropdown');
    if (dd) dd.remove();
  },

  clearContext: function() {
    localStorage.removeItem('pm_plant');
    localStorage.removeItem('pm_line');
    PlantMindContext.updateHeader();
    var pf = document.getElementById('plantFilter');
    var lf = document.getElementById('lineFilter');
    if (pf) pf.value = '';
    if (lf) lf.value = '';
    var dd = document.getElementById('ctxDropdown');
    if (dd) dd.remove();
  }
};

document.addEventListener('DOMContentLoaded', function() {
  PlantMindContext.updateHeader();
  var pill = document.getElementById('navCtx');
  if (pill) {
    pill.style.cursor = 'pointer';
    pill.addEventListener('click', function(e) {
      e.stopPropagation();
      PlantMindContext.buildDropdown();
    });
  }
});
