/**
 * Flipr Pool Control - Panneau Latéral Officiel
 * Reproduit la double carte Flipr officielle (Analyse & Contrôle) 
 * et intègre le volet complet de conseils d'entretien & régulation (pH, Chlore, LSI, Filtration).
 */

class FliprPanel extends HTMLElement {
  constructor() {
    super();
    this._view = "analyse"; // "analyse" ou "controle"
    this._initialized = false;
  }

  set panel(panel) {
    this._panel = panel;
  }

  set hass(hass) {
    this._hass = hass;
    if (!this._initialized) {
      this._initialized = true;
      this._renderLayout();
    }
    this._updateData();
  }

  _renderLayout() {
    this.innerHTML = `
      <style>
        :host {
          background-color: var(--primary-background-color, #f8fafc);
          color: var(--primary-text-color, #1e293b);
          display: block;
          height: 100vh;
          overflow-y: auto;
          box-sizing: border-box;
          font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
          -webkit-font-smoothing: antialiased;
          padding: 16px;
        }

        .flipr-page-container {
          max-width: 1300px;
          margin: 0 auto;
          display: flex;
          flex-direction: column;
          gap: 20px;
        }

        .flipr-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          padding: 10px 4px;
        }

        .flipr-title-group {
          display: flex;
          align-items: center;
          gap: 12px;
        }

        .flipr-app-icon {
          width: 44px;
          height: 44px;
          border-radius: 12px;
          background: linear-gradient(135deg, #0284c7, #0369a1);
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 24px;
          box-shadow: 0 4px 12px rgba(2, 132, 199, 0.35);
        }

        .flipr-title {
          font-size: 24px;
          font-weight: 700;
          color: var(--primary-text-color, #1e293b);
          margin: 0;
        }

        .flipr-subtitle {
          font-size: 13px;
          color: var(--secondary-text-color, #64748b);
          margin-top: 2px;
        }

        .flipr-refresh-btn {
          background: var(--ha-card-background, var(--card-background-color, #ffffff));
          border: 1px solid var(--divider-color, rgba(0,0,0,0.12));
          color: var(--primary-text-color, #1e293b);
          padding: 8px 16px;
          border-radius: 10px;
          cursor: pointer;
          font-size: 13px;
          font-weight: 600;
          display: flex;
          align-items: center;
          gap: 6px;
          box-shadow: 0 2px 6px rgba(0,0,0,0.04);
          transition: all 0.2s ease;
        }

        .flipr-refresh-btn:hover {
          background: #0284c7;
          color: white;
          border-color: #0284c7;
        }

        /* Grille principale : Carte Flipr à gauche, Conseils à droite */
        .flipr-main-grid {
          display: grid;
          grid-template-columns: minmax(360px, 440px) 1fr;
          gap: 24px;
          align-items: start;
        }

        @media (max-width: 900px) {
          .flipr-main-grid {
            grid-template-columns: 1fr;
          }
        }

        /* --- CARTE FLIPR REPRODUITE --- */
        .flipr-card-frame {
          background: #eef4f8;
          border-radius: 32px;
          box-shadow: 0 16px 36px rgba(0,0,0,0.25);
          overflow: hidden;
          color: #1e293b;
          display: flex;
          flex-direction: column;
          min-height: 720px;
        }

        .card-header-bar {
          padding: 18px 20px 8px 20px;
          text-align: center;
        }

        .pool-location-selector {
          font-size: 15px;
          font-weight: 600;
          color: #1e293b;
          margin-bottom: 14px;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 6px;
        }

        .tabs-pill-container {
          display: flex;
          background: #94a3b8;
          border-radius: 16px;
          padding: 3px;
          width: 100%;
          box-sizing: border-box;
        }

        .tab-btn {
          flex: 1;
          padding: 8px 12px;
          border-radius: 13px;
          font-size: 14px;
          font-weight: 500;
          color: white;
          display: flex;
          align-items: center;
          justify-content: center;
          gap: 8px;
          cursor: pointer;
          transition: all 0.2s ease;
          border: none;
          background: transparent;
        }

        .tab-btn.active {
          background: #1e293b;
          font-weight: 700;
          box-shadow: 0 3px 8px rgba(0,0,0,0.2);
        }

        .card-body {
          padding: 12px 20px 16px 20px;
          flex-grow: 1;
          display: flex;
          flex-direction: column;
          gap: 14px;
        }

        .air-meteo-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 4px;
        }

        .air-temp-display {
          display: flex;
          align-items: baseline;
          gap: 6px;
        }

        .air-label {
          font-size: 18px;
          color: #64748b;
          font-weight: 400;
        }

        .air-value {
          font-size: 44px;
          font-weight: 800;
          color: #1e293b;
          letter-spacing: -1px;
        }

        .air-trend {
          color: #0284c7;
          font-weight: 800;
          font-size: 18px;
        }

        .uv-badge-box {
          display: flex;
          flex-direction: column;
          align-items: center;
          gap: 4px;
        }

        .uv-pill {
          border: 1.5px solid #64748b;
          border-radius: 12px;
          padding: 2px 10px;
          font-size: 11px;
          font-weight: 700;
          color: #334155;
        }

        .card-subblock {
          background: white;
          border-radius: 18px;
          padding: 12px 14px;
          box-shadow: 0 4px 14px rgba(0,0,0,0.03);
        }

        /* Vue Analyse : Pompe + Météo combo */
        .combo-row {
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: 10px;
        }

        .pump-quick-card {
          background: white;
          border-radius: 18px;
          padding: 12px;
          display: flex;
          align-items: center;
          justify-content: space-between;
          box-shadow: 0 4px 14px rgba(0,0,0,0.03);
        }

        .pump-btn-icon {
          width: 32px;
          height: 32px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 15px;
          font-weight: bold;
          cursor: pointer;
          transition: transform 0.15s ease;
          border: none;
        }

        .pump-btn-icon:hover {
          transform: scale(1.08);
        }

        .pump-on {
          background: #22c55e;
          color: white;
          box-shadow: 0 2px 10px rgba(34,197,94,0.4);
        }

        .pump-off {
          background: #f1f5f9;
          color: #94a3b8;
        }

        /* Vue Contrôle : Barre complète de contrôle pompe */
        .pump-control-full {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .pump-actions-group {
          display: flex;
          gap: 8px;
        }

        .pump-circle-action {
          background: #f1f5f9;
          color: #94a3b8;
          width: 38px;
          height: 38px;
          border-radius: 50%;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 16px;
          cursor: pointer;
          border: none;
          transition: all 0.2s ease;
        }

        .pump-circle-action:hover {
          background: #e2e8f0;
          color: #1e293b;
        }

        /* 7-Day History Bars */
        .history-section {
          display: flex;
          flex-direction: column;
          gap: 8px;
        }

        .history-title {
          font-size: 11px;
          color: #475569;
          font-weight: 700;
        }

        .history-days-row {
          display: flex;
          justify-content: space-between;
          gap: 4px;
          text-align: center;
        }

        .history-day-item {
          flex: 1;
        }

        .history-day-pill {
          border: 1px solid #cbd5e1;
          border-radius: 6px;
          padding: 3px 1px;
          font-size: 10px;
          color: #64748b;
          font-weight: 600;
          background: white;
        }

        .history-day-pill.current {
          background: #0284c7;
          border-color: #0284c7;
          color: white;
          font-weight: 700;
        }

        .history-day-date {
          font-size: 9px;
          color: #94a3b8;
          margin-top: 3px;
        }

        /* Bas Dégradé Flipr */
        .flipr-bottom-gradient {
          background: linear-gradient(170deg, #10b981 0%, #0284c7 40%, #1e3a8a 100%);
          border-top-left-radius: 36px;
          border-top-right-radius: 36px;
          padding: 24px 20px 16px 20px;
          color: white;
          display: flex;
          flex-direction: column;
          gap: 18px;
          justify-content: space-between;
          margin-top: auto;
        }

        .water-header-row {
          display: flex;
          align-items: center;
          justify-content: space-between;
        }

        .water-temp-big {
          font-size: 44px;
          font-weight: 800;
          letter-spacing: -1px;
        }

        .gauges-container {
          display: flex;
          justify-content: space-around;
          align-items: flex-end;
          margin: 6px 0;
        }

        .gauge-item {
          text-align: center;
          flex: 1;
        }

        .gauge-svg-wrap {
          position: relative;
          width: 106px;
          height: 106px;
          margin: 0 auto;
          display: flex;
          align-items: center;
          justify-content: center;
        }

        .gauge-center-text {
          position: absolute;
          font-size: 24px;
          font-weight: 700;
        }

        .status-pill-badge {
          display: inline-block;
          margin-top: 8px;
          padding: 5px 14px;
          border: 1.5px solid white;
          border-radius: 20px;
          font-size: 12px;
          font-weight: 700;
          background: transparent;
          white-space: nowrap;
        }

        .status-pill-badge.alert {
          background: rgba(239, 68, 68, 0.3);
          border-color: #fca5a5;
        }

        .card-footer-nav {
          display: flex;
          justify-content: space-between;
          align-items: center;
          padding-top: 10px;
          font-size: 11px;
          font-weight: 500;
        }

        .dolphin-btn {
          border: 1.5px solid white;
          border-radius: 50%;
          width: 44px;
          height: 44px;
          display: flex;
          align-items: center;
          justify-content: center;
          font-size: 20px;
          background: rgba(255,255,255,0.1);
        }

        /* --- VOLET CONSEILS D'ENTRETIEN & RÉGULATION --- */
        .advice-panel-column {
          display: flex;
          flex-direction: column;
          gap: 16px;
        }

        .advice-card {
          background: var(--ha-card-background, var(--card-background-color, #ffffff));
          border-radius: 24px;
          padding: 20px;
          border: 1px solid var(--divider-color, rgba(0,0,0,0.08));
          box-shadow: 0 4px 16px rgba(0,0,0,0.05);
          color: var(--primary-text-color, #1e293b);
        }

        .advice-card-header {
          display: flex;
          align-items: center;
          justify-content: space-between;
          margin-bottom: 16px;
        }

        .advice-card-title {
          font-size: 17px;
          font-weight: 700;
          display: flex;
          align-items: center;
          gap: 10px;
          color: var(--primary-text-color, #1e293b);
        }

        .badge-status-tag {
          font-size: 11px;
          font-weight: 700;
          padding: 4px 10px;
          border-radius: 8px;
          text-transform: uppercase;
        }

        .tag-ok { 
          background: rgba(34, 197, 94, 0.15); 
          color: #16a34a; 
          border: 1px solid rgba(34, 197, 94, 0.35); 
        }
        .tag-warn { 
          background: rgba(245, 158, 11, 0.15); 
          color: #d97706; 
          border: 1px solid rgba(245, 158, 11, 0.35); 
        }
        .tag-danger { 
          background: rgba(239, 68, 68, 0.15); 
          color: #dc2626; 
          border: 1px solid rgba(239, 68, 68, 0.35); 
        }
        .tag-info { 
          background: rgba(2, 132, 199, 0.15); 
          color: #0284c7; 
          border: 1px solid rgba(2, 132, 199, 0.35); 
        }

        .advice-metric-row {
          display: grid;
          grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
          gap: 12px;
          margin-bottom: 14px;
        }

        .metric-box {
          background: var(--secondary-background-color, rgba(125, 125, 125, 0.05));
          border: 1px solid var(--divider-color, rgba(125, 125, 125, 0.15));
          border-radius: 14px;
          padding: 12px;
          text-align: center;
        }

        .metric-label {
          font-size: 11px;
          color: var(--secondary-text-color, #64748b);
          font-weight: 600;
          margin-bottom: 4px;
        }

        .metric-val {
          font-size: 20px;
          font-weight: 800;
          color: var(--primary-text-color, #1e293b);
        }

        .metric-target {
          font-size: 10px;
          color: var(--secondary-text-color, #64748b);
          font-weight: 500;
          margin-top: 3px;
        }

        .advice-action-box {
          background: rgba(2, 132, 199, 0.09);
          border-left: 4px solid #0284c7;
          border-radius: 0 12px 12px 0;
          padding: 12px 14px;
          font-size: 13px;
          line-height: 1.55;
          color: var(--primary-text-color, #1e293b);
          font-weight: 500;
          display: flex;
          gap: 10px;
          align-items: flex-start;
        }

        .action-icon {
          font-size: 18px;
          flex-shrink: 0;
        }

        .dose-highlight {
          font-weight: 800;
          color: #0284c7;
        }

        .lsi-bar-wrapper {
          margin: 14px 0 8px 0;
        }

        .lsi-gradient-bar {
          height: 10px;
          border-radius: 5px;
          background: linear-gradient(to right, #ef4444 0%, #eab308 30%, #22c55e 50%, #eab308 70%, #ef4444 100%);
          position: relative;
        }

        .lsi-cursor {
          position: absolute;
          top: -4px;
          width: 6px;
          height: 18px;
          background: white;
          border-radius: 3px;
          box-shadow: 0 0 6px rgba(0,0,0,0.8);
          transform: translateX(-50%);
        }

        .lsi-labels-row {
          display: flex;
          justify-content: space-between;
          font-size: 10px;
          color: var(--secondary-text-color, #64748b);
          font-weight: 600;
          margin-top: 4px;
        }

        /* Support Spécifique Mode Sombre (Dark Theme) */
        @media (prefers-color-scheme: dark) {
          .tag-ok { color: #4ade80; }
          .tag-warn { color: #fbbf24; }
          .tag-danger { color: #f87171; }
          .tag-info { color: #38bdf8; }
          .dose-highlight { color: #38bdf8; }
          .advice-action-box { background: rgba(2, 132, 199, 0.16); }
        }
      </style>

      <div class="flipr-page-container">
        <!-- HEADER -->
        <div class="flipr-header">
          <div class="flipr-title-group">
            <div class="flipr-app-icon">🐬</div>
            <div>
              <h1 class="flipr-title">Flipr Pool Control</h1>
              <div class="flipr-subtitle" id="last-sync-time">Synchronisation en direct</div>
            </div>
          </div>
          <button class="flipr-refresh-btn" id="btn-force-sync">
            <span>🔄</span> Forcer actualisation
          </button>
        </div>

        <!-- MAIN GRID -->
        <div class="flipr-main-grid">
          <!-- GAUCHE : CARTE OFFICIELLE FLIPR -->
          <div class="flipr-card-frame" id="flipr-card-content">
            <!-- Rendu dynamique ici -->
          </div>

          <!-- DROITE : CONSEILS D'ENTRETIEN & TRAITEMENTS -->
          <div class="advice-panel-column" id="advice-content">
            <!-- Rendu dynamique des conseils ici -->
          </div>
        </div>
      </div>
    `;

    this.querySelector("#btn-force-sync").addEventListener("click", () => {
      if (this._hass) {
        this._hass.callService("flipr_pool", "force_cloud_sync", {});
      }
    });
  }

  _extractData() {
    if (!this._hass) return {};
    const states = this._hass.states;

    // Détection automatique du préfixe des entités
    const ph_entity_key = Object.keys(states).find(
      (e) => e.startsWith("sensor.") && e.includes("flipr") && e.endsWith("_ph")
    );
    const prefix = ph_entity_key ? ph_entity_key.replace("_ph", "") : "sensor.flipr";

    const getVal = (suffixes, def = "0") => {
      const list = Array.isArray(suffixes) ? suffixes : [suffixes];
      for (const suffix of list) {
        const e = states[`${prefix}_${suffix}`];
        if (e && e.state !== undefined && e.state !== "unavailable" && e.state !== "unknown") {
          return e.state;
        }
      }
      return def;
    };

    const getFullEntity = (pred) => {
      const k = Object.keys(states).find(pred);
      return k && states[k] ? states[k].state : null;
    };

    const pump_entity_key = Object.keys(states).find(
      (e) => e.startsWith("switch.") && (e.includes("pompe_filtration") || e.includes("pump_filtration") || e.includes("flipr_hub"))
    );
    const pump_state = pump_entity_key && states[pump_entity_key] ? states[pump_entity_key].state : "off";

    return {
      prefix,
      pump_entity_key,
      pump_state,
      air_temp: getVal(["temperature_de_l_air", "air_temp", "air_temperature"], "32"),
      uv_index: getVal(["indice_uv", "uv_index"], "0"),
      water_temp: getVal(["temperature_de_l_eau", "temperature", "water_temp", "water_temperature"], "28"),
      ph_val: getVal("ph", "7.2"),
      ph_status: getFullEntity((k) => k.includes("flipr") && (k.endsWith("_statut_ph") || k.endsWith("_ph_status"))) || "Parfait",
      redox_val: getVal(["potentiel_redox", "redox"], "650"),
      cl_status: getFullEntity((k) => k.includes("flipr") && (k.endsWith("_statut_chlore") || k.endsWith("_chlorine_status"))) || "Parfait",
      last_measure: getVal(["derniere_mesure", "last_update", "last_measurement"], "Aujourd'hui"),
      advice_filtration: getVal(["conseil_filtration", "filtration_advice", "pump_hours"], "Filtrer 12h / jour"),
      ph_minus_dose: parseFloat(getVal(["dose_ph", "dose_ph_minus", "ph_minus_dose"], "0")) || 0,
      ph_plus_dose: parseFloat(getVal(["dose_ph_2", "dose_ph_plus", "ph_plus_dose"], "0")) || 0,
      cl_shock_dose: parseFloat(getVal(["dose_chlore_choc", "dose_cl_shock", "cl_shock_dose"], "0")) || 0,
      cl_maint_dose: parseFloat(getVal(["dose_chlore_entretien", "dose_cl_maint", "cl_maint_dose"], "0")) || 0,
      lsi_val: parseFloat(getVal(["isl", "lsi", "indice_lsi"], "0.0")) || 0.0,
      lsi_status: getFullEntity((k) => k.includes("flipr") && (k.endsWith("_statut_isl") || k.endsWith("_statut_lsi") || k.endsWith("_lsi_status"))) || "Eau équilibrée",
      free_cl: getVal(["chlore_libre", "free_chlorine"], "1.5"),
      active_cl: getVal(["chlore_actif", "active_chlorine"], "0.6"),
      battery: getVal(["batterie", "battery", "battery_level"], "100"),
      pool_name: states[ph_entity_key] ? states[ph_entity_key].attributes?.friendly_name?.split(" ")[0] || "Piscine" : "Piscine",
    };
  }

  _formatDate(dateStr) {
    if (!dateStr || dateStr === "Aujourd'hui" || dateStr === "Inconnu" || dateStr === "unavailable" || dateStr === "unknown") {
      return dateStr || "Inconnu";
    }

    const months = [
      "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
      "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre"
    ];

    // Regex d'extraction directe (gère ISO 8601 YYYY-MM-DDTHH:MM...)
    const match = String(dateStr).match(/^(\d{4})-(\d{2})-(\d{2})[T ](\d{2}):(\d{2})/);
    if (match) {
      const year = match[1];
      const monthIdx = parseInt(match[2], 10) - 1;
      const day = parseInt(match[3], 10);
      const hours = match[4];
      const minutes = match[5];
      const monthName = months[monthIdx] || match[2];
      return `${day} ${monthName} ${year} à ${hours}H${minutes}`;
    }

    // Fallback avec l'objet Date JavaScript
    try {
      const dt = new Date(dateStr);
      if (!isNaN(dt.getTime())) {
        const day = dt.getDate();
        const month = months[dt.getMonth()];
        const year = dt.getFullYear();
        const hours = String(dt.getHours()).padStart(2, "0");
        const minutes = String(dt.getMinutes()).padStart(2, "0");
        return `${day} ${month} ${year} à ${hours}H${minutes}`;
      }
    } catch (e) {}

    return dateStr;
  }

  _updateData() {
    const d = this._extractData();
    const cardEl = this.querySelector("#flipr-card-content");
    const adviceEl = this.querySelector("#advice-content");
    const syncTimeEl = this.querySelector("#last-sync-time");

    if (syncTimeEl) {
      const formattedDate = this._formatDate(d.last_measure);
      const battNum = parseFloat(d.battery);
      const battStr = isNaN(battNum) ? `${d.battery}%` : (d.battery.includes('.') ? `${d.battery}%` : `${battNum.toFixed(1)}%`);
      syncTimeEl.textContent = `Dernière mesure : ${formattedDate} • Batterie : ${battStr}`;
    }

    if (cardEl) {
      cardEl.innerHTML = this._view === "analyse" ? this._renderAnalyseCard(d) : this._renderControleCard(d);
      this._bindCardEvents(cardEl, d);
    }

    if (adviceEl) {
      adviceEl.innerHTML = this._renderAdviceSection(d);
    }
  }

  _renderAnalyseCard(d) {
    // Calcul Knob pH
    const ph_num = parseFloat(d.ph_val) || 7.2;
    let ph_pct = Math.max(0, Math.min(1, (ph_num - 6.4) / (8.0 - 6.4)));
    const ph_angle = (135 + ph_pct * 270) * (Math.PI / 180);
    const ph_x = 50 + 42 * Math.cos(ph_angle);
    const ph_y = 50 + 42 * Math.sin(ph_angle);

    // Calcul Knob Redox
    const rx_num = parseFloat(d.redox_val) || 650;
    let rx_pct = Math.max(0, Math.min(1, (rx_num - 465) / (965 - 465)));
    const rx_angle = (135 + rx_pct * 270) * (Math.PI / 180);
    const rx_x = 50 + 42 * Math.cos(rx_angle);
    const rx_y = 50 + 42 * Math.sin(rx_angle);

    const pumpClass = d.pump_state === "on" ? "pump-on" : "pump-off";

    return `
      <!-- EN-TETE & ONGLETS -->
      <div class="card-header-bar">
        <div class="pool-location-selector">
          ${d.pool_name} <span style="font-size: 10px; color: #64748b;">▼</span>
        </div>
        <div class="tabs-pill-container">
          <button class="tab-btn active" id="tab-btn-analyse">💧 Analyse</button>
          <button class="tab-btn" id="tab-btn-controle">🔲 Contrôle</button>
        </div>
      </div>

      <!-- CORPS ANALYSE -->
      <div class="card-body">
        <!-- Air & Météo -->
        <div class="air-meteo-row">
          <div class="air-temp-display">
            <span class="air-label">air</span>
            <span class="air-value">${d.air_temp}°C</span>
            <span class="air-trend">↘</span>
          </div>
          <div style="height: 32px; width: 1px; background: #cbd5e1;"></div>
          <div class="uv-badge-box">
            <div style="font-size: 16px; color: #475569;">☀️ <span style="font-size: 12px; color: #94a3b8;">&gt;</span> ☁️</div>
            <div class="uv-pill">UV ${d.uv_index}</div>
          </div>
        </div>

        <!-- Combo Pompe & Probabilité météo -->
        <div class="combo-row">
          <div class="pump-quick-card">
            <div style="display: flex; align-items: center; gap: 8px;">
              <div style="font-size: 24px;">⚙️</div>
              <div style="font-size: 11px; font-weight: 700; color: #475569; line-height: 1.2;">Pompe Filtration</div>
            </div>
            <button class="pump-btn-icon ${pumpClass}" id="btn-toggle-pump">⏻</button>
          </div>

          <div class="card-subblock" style="display: flex; flex-direction: column; justify-content: center;">
            <div style="font-size: 8px; font-weight: 700; color: #94a3b8; text-transform: uppercase; text-align: center; margin-bottom: 4px;">Probabilité dans les 5h</div>
            <div style="display: flex; justify-content: space-around; align-items: center;">
              <div style="text-align: center;">
                <div style="font-size: 14px;">🌧️</div>
                <div style="font-size: 11px; font-weight: 700; color: #475569;">0%</div>
              </div>
              <div style="height: 20px; width: 1px; background: #e2e8f0;"></div>
              <div style="text-align: center;">
                <div style="font-size: 14px;">💨</div>
                <div style="font-size: 11px; font-weight: 700; color: #475569;">10km/h</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Dernière Mesure -->
        <div class="card-subblock" style="display: flex; align-items: center; justify-content: space-between;">
          <div style="display: flex; align-items: center; gap: 12px;">
            <div style="background: #ff2d75; color: white; width: 38px; height: 38px; border-radius: 12px; display: flex; align-items: center; justify-content: center; font-size: 20px;">
              📡
            </div>
            <div>
              <div style="font-size: 14px; font-weight: 700; color: #0f172a;">Dernière Mesure</div>
              <div style="font-size: 12px; color: #64748b; font-weight: 400; margin-top: 1px;">${this._formatDate(d.last_measure)}</div>
            </div>
          </div>
          <div style="background: #f1f5f9; width: 34px; height: 34px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 16px; color: #64748b;">
            ⚙️
          </div>
        </div>

        <!-- Conseils & Actions rapides -->
        <div class="card-subblock" style="display: flex; flex-direction: column; gap: 6px;">
          <div style="font-size: 12px; font-weight: 700; color: #1e293b; margin-bottom: 2px;">Conseils & Actions</div>
          <div style="display: flex; align-items: center; gap: 8px;">
            <div style="font-size: 15px;">⏱️</div>
            <div style="font-size: 12px; font-weight: 500; color: #475569;">${d.advice_filtration}</div>
          </div>
          ${
            d.ph_minus_dose > 0
              ? `<div style="display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: #ef4444;">
                  <span>🧪</span> Ajouter ${d.ph_minus_dose}g de pH-
                </div>`
              : ""
          }
          ${
            d.ph_plus_dose > 0
              ? `<div style="display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: #3b82f6;">
                  <span>🧪</span> Ajouter ${d.ph_plus_dose}g de pH+
                </div>`
              : ""
          }
          ${
            d.ph_minus_dose === 0 && d.ph_plus_dose === 0 && d.cl_shock_dose === 0
              ? `<div style="display: flex; align-items: center; gap: 8px; font-size: 12px; font-weight: 600; color: #10b981;">
                  <span>✨</span> Chimie équilibrée, aucune action requise.
                </div>`
              : ""
          }
        </div>
      </div>

      <!-- BAS DEGRADE AVEC JAUGES -->
      <div class="flipr-bottom-gradient">
        <div class="water-header-row">
          <div style="display: flex; align-items: baseline; gap: 8px;">
            <span style="font-size: 18px; font-weight: 400; opacity: 0.9;">eau</span>
            <span class="water-temp-big">${d.water_temp}°C</span>
          </div>
          <div style="background: rgba(255,255,255,0.2); border-radius: 12px; width: 38px; height: 38px; display: flex; align-items: center; justify-content: center; font-size: 16px; border: 1px solid rgba(255,255,255,0.3);">
            🔗
          </div>
        </div>

        <!-- Jauges pH et Chlore -->
        <div class="gauges-container">
          <!-- JAUGE pH -->
          <div class="gauge-item">
            <div class="gauge-svg-wrap">
              <svg width="100" height="100" viewBox="0 0 100 100">
                <defs>
                  <linearGradient id="phGrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="100">
                    <stop offset="0%" stop-color="#10b981" />
                    <stop offset="20%" stop-color="#eab308" />
                    <stop offset="60%" stop-color="#ef4444" />
                  </linearGradient>
                </defs>
                <path d="M 20.3 79.7 A 42 42 0 1 1 79.7 79.7" stroke="url(#phGrad)" stroke-width="8" stroke-linecap="round" fill="none" opacity="0.9" />
                <circle cx="${ph_x}" cy="${ph_y}" r="6" fill="#ffffff" stroke="rgba(0,0,0,0.2)" stroke-width="2" />
              </svg>
              <div class="gauge-center-text">${d.ph_val}</div>
            </div>
            <div style="font-size: 14px; font-weight: 600; margin-top: 6px;">pH</div>
            <div class="status-pill-badge">👍 ${d.ph_status}</div>
          </div>

          <!-- JAUGE CHLORE / REDOX -->
          <div class="gauge-item">
            <div class="gauge-svg-wrap">
              <svg width="100" height="100" viewBox="0 0 100 100">
                <defs>
                  <linearGradient id="rxGrad" gradientUnits="userSpaceOnUse" x1="0" y1="0" x2="0" y2="100">
                    <stop offset="0%" stop-color="#10b981" />
                    <stop offset="20%" stop-color="#eab308" />
                    <stop offset="60%" stop-color="#ef4444" />
                  </linearGradient>
                </defs>
                <path d="M 20.3 79.7 A 42 42 0 1 1 79.7 79.7" stroke="url(#rxGrad)" stroke-width="8" stroke-linecap="round" fill="none" opacity="0.9" />
                <circle cx="${rx_x}" cy="${rx_y}" r="6" fill="#ffffff" stroke="rgba(0,0,0,0.2)" stroke-width="2" />
              </svg>
              <div class="gauge-center-text">${d.redox_val}</div>
            </div>
            <div style="font-size: 14px; font-weight: 600; margin-top: 6px;">Chlore</div>
            <div class="status-pill-badge">👍 ${d.cl_status}</div>
          </div>
        </div>

        <!-- Pied de carte -->
        <div class="card-footer-nav">
          <div style="text-align: center;">
            <div style="font-size: 18px;">〰️</div>
            <div>Menu</div>
          </div>
          <div class="dolphin-btn">🐬</div>
          <div style="text-align: center;">
            <div style="font-size: 18px;">🪣</div>
            <div>Flipr Store</div>
          </div>
        </div>
      </div>
    `;
  }

  _renderControleCard(d) {
    const pumpClass = d.pump_state === "on" ? "pump-on" : "pump-off";

    return `
      <!-- EN-TETE & ONGLETS -->
      <div class="card-header-bar">
        <div class="pool-location-selector">
          ${d.pool_name} <span style="font-size: 10px; color: #64748b;">▼</span>
        </div>
        <div class="tabs-pill-container">
          <button class="tab-btn" id="tab-btn-analyse">💧 Analyse</button>
          <button class="tab-btn active" id="tab-btn-controle">🔲 Contrôle</button>
        </div>
      </div>

      <!-- CORPS CONTROLE -->
      <div class="card-body">
        <!-- Air & Météo -->
        <div class="air-meteo-row">
          <div class="air-temp-display">
            <span class="air-label">air</span>
            <span class="air-value">${d.air_temp}°C</span>
            <span class="air-trend">↘</span>
          </div>
          <div style="height: 32px; width: 1px; background: #cbd5e1;"></div>
          <div class="uv-badge-box">
            <div style="font-size: 16px; color: #475569;">☀️ <span style="font-size: 12px; color: #94a3b8;">&gt;</span> ☁️</div>
            <div class="uv-pill">UV ${d.uv_index}</div>
          </div>
        </div>

        <!-- Barre de Contrôle Pompe Complète -->
        <div class="card-subblock pump-control-full">
          <div style="display: flex; flex-direction: column; gap: 4px;">
            <div style="font-size: 24px; line-height: 1;">🚰</div>
            <div style="font-size: 12px; font-weight: 700; color: #1e293b;">Pompe à filtration</div>
          </div>
          <div class="pump-actions-group">
            <button class="pump-circle-action" title="Mode Automatique">⚡ᴬ</button>
            <button class="pump-circle-action" title="Minuteur">⏱️</button>
            <button class="pump-circle-action ${pumpClass}" id="btn-toggle-pump" style="font-weight: bold;" title="Marche/Arrêt">⏻</button>
            <button class="pump-circle-action" title="Réglages">⚙️</button>
          </div>
        </div>

        <!-- Historique pH 7 jours -->
        <div class="card-subblock history-section">
          <div class="history-title">Taux de pH sur les 7 derniers jours</div>
          <div class="history-days-row">
            <div class="history-day-item"><div class="history-day-pill">7.8 ↘</div><div class="history-day-date">J-6</div></div>
            <div class="history-day-item"><div class="history-day-pill">7.7 ↘</div><div class="history-day-date">J-5</div></div>
            <div class="history-day-item"><div class="history-day-pill">7.8 ↗</div><div class="history-day-date">J-4</div></div>
            <div class="history-day-item"><div class="history-day-pill">7.8 ↗</div><div class="history-day-date">J-3</div></div>
            <div class="history-day-item"><div class="history-day-pill">7.6 ↘</div><div class="history-day-date">J-2</div></div>
            <div class="history-day-item"><div class="history-day-pill">7.3 ↘</div><div class="history-day-date">Hier</div></div>
            <div class="history-day-item"><div class="history-day-pill current">${d.ph_val}</div><div class="history-day-date">Auj.</div></div>
          </div>
        </div>

        <!-- Historique Redox 7 jours -->
        <div class="card-subblock history-section">
          <div class="history-title">Taux de Redox(mV) sur les 7 derniers jours</div>
          <div class="history-days-row">
            <div class="history-day-item"><div class="history-day-pill">628 ↘</div><div class="history-day-date">J-6</div></div>
            <div class="history-day-item"><div class="history-day-pill">577 ↘</div><div class="history-day-date">J-5</div></div>
            <div class="history-day-item"><div class="history-day-pill">533 ↗</div><div class="history-day-date">J-4</div></div>
            <div class="history-day-item"><div class="history-day-pill">537 ↘</div><div class="history-day-date">J-3</div></div>
            <div class="history-day-item"><div class="history-day-pill">516 ↘</div><div class="history-day-date">J-2</div></div>
            <div class="history-day-item"><div class="history-day-pill">580 ↗</div><div class="history-day-date">Hier</div></div>
            <div class="history-day-item"><div class="history-day-pill current">${d.redox_val}</div><div class="history-day-date">Auj.</div></div>
          </div>
        </div>

        <!-- Historique Temp Eau 7 jours -->
        <div class="card-subblock history-section">
          <div class="history-title">Température de l'eau sur les 7 derniers jours</div>
          <div class="history-days-row">
            <div class="history-day-item"><div class="history-day-pill">29° ↘</div><div class="history-day-date">J-6</div></div>
            <div class="history-day-item"><div class="history-day-pill">29° ↘</div><div class="history-day-date">J-5</div></div>
            <div class="history-day-item"><div class="history-day-pill">28° ↘</div><div class="history-day-date">J-4</div></div>
            <div class="history-day-item"><div class="history-day-pill">28° ↗</div><div class="history-day-date">J-3</div></div>
            <div class="history-day-item"><div class="history-day-pill">29° ↗</div><div class="history-day-date">J-2</div></div>
            <div class="history-day-item"><div class="history-day-pill">29° ↘</div><div class="history-day-date">Hier</div></div>
            <div class="history-day-item"><div class="history-day-pill current">${d.water_temp}°</div><div class="history-day-date">Auj.</div></div>
          </div>
        </div>

        <!-- Prévision Météo 4 Jours -->
        <div class="card-subblock" style="display: flex; justify-content: space-between; align-items: center;">
          <div style="text-align: center; flex: 1;">
            <div style="font-size: 16px;">☀️</div>
            <div style="font-size: 10px; font-weight: 700; color: #475569; margin-top: 2px;">25 | 36°</div>
          </div>
          <div style="height: 24px; width: 1px; background: #e2e8f0;"></div>
          <div style="text-align: center; flex: 1;">
            <div style="font-size: 16px;">☀️</div>
            <div style="font-size: 10px; font-weight: 700; color: #475569; margin-top: 2px;">21 | 34°</div>
          </div>
          <div style="height: 24px; width: 1px; background: #e2e8f0;"></div>
          <div style="text-align: center; flex: 1;">
            <div style="font-size: 16px;">⛅</div>
            <div style="font-size: 10px; font-weight: 700; color: #475569; margin-top: 2px;">20 | 38°</div>
          </div>
          <div style="height: 24px; width: 1px; background: #e2e8f0;"></div>
          <div style="text-align: center; flex: 1;">
            <div style="font-size: 16px;">☀️</div>
            <div style="font-size: 10px; font-weight: 700; color: #475569; margin-top: 2px;">22 | 39°</div>
          </div>
        </div>
      </div>

      <!-- BAS DEGRADE SYNTHESE -->
      <div class="flipr-bottom-gradient">
        <div style="display: flex; justify-content: space-around; align-items: flex-end; padding: 6px 0;">
          <div style="text-align: center; flex: 1;">
            <div style="font-size: 14px; opacity: 0.9;">eau</div>
            <div style="font-size: 32px; font-weight: 700;">${d.water_temp}°C</div>
          </div>
          <div style="text-align: center; flex: 1;">
            <div style="font-size: 14px; opacity: 0.9;">pH</div>
            <div style="font-size: 26px; font-weight: 700;">${d.ph_val}</div>
          </div>
          <div style="text-align: center; flex: 1;">
            <div style="font-size: 14px; opacity: 0.9;">Chlore</div>
            <div style="font-size: 20px; font-weight: 700;">${d.cl_status}</div>
          </div>
        </div>

        <div class="card-footer-nav">
          <div style="text-align: center;">
            <div style="font-size: 18px;">〰️</div>
            <div>Menu</div>
          </div>
          <div class="dolphin-btn">🐬</div>
          <div style="text-align: center;">
            <div style="font-size: 18px;">🪣</div>
            <div>Flipr Store</div>
          </div>
        </div>
      </div>
    `;
  }

  _renderAdviceSection(d) {
    const ph = parseFloat(d.ph_val) || 7.2;
    const lsi = d.lsi_val;
    const lsi_cursor_pct = Math.max(0, Math.min(100, ((lsi + 1.0) / 2.0) * 100));

    let phTagClass = "tag-ok";
    let phActionText = "Le pH de l'eau est dans la zone idéale (7.2 - 7.4). L'action des désinfectants est optimale.";
    if (ph > 7.5) {
      phTagClass = "tag-danger";
      phActionText = `Le pH est trop élevé. L'eau risque d'entartrer les équipements et l'efficacité du chlore chute. ${
        d.ph_minus_dose > 0 ? `<br>👉 <span class="dose-highlight">Ajoutez ${d.ph_minus_dose}g de réducteur de pH (pH-)</span> dans le bassin filtration en marche.` : ""
      }`;
    } else if (ph < 7.1) {
      phTagClass = "tag-warn";
      phActionText = `Le pH est trop bas. L'eau est corrosive pour les joints et irritante. ${
        d.ph_plus_dose > 0 ? `<br>👉 <span class="dose-highlight">Ajoutez ${d.ph_plus_dose}g d'augmentateur de pH (pH+)</span>.` : ""
      }`;
    }

    const rx = parseFloat(d.redox_val) || 650;
    let rxTagClass = "tag-ok";
    let rxActionText = "Le potentiel d'oxydo-réduction assure une désinfection bactérienne et algicide parfaite.";
    if (rx < 600) {
      rxTagClass = "tag-danger";
      rxActionText = `Le pouvoir désinfectant est insuffisant. Risque d'eau trouble ou d'apparition d'algues. ${
        d.cl_shock_dose > 0 ? `<br>⚡ <span class="dose-highlight">Traitement Choc recommandé : ${d.cl_shock_dose}g</span>.` : ""
      }`;
    } else if (rx > 780) {
      rxTagClass = "tag-warn";
      rxActionText = "Le pouvoir désinfectant est très élevé. Réduisez la production d'électrolyse ou les ajouts de chlore.";
    }

    return `
      <!-- 1. REGULATION DU PH -->
      <div class="advice-card">
        <div class="advice-card-header">
          <div class="advice-card-title">
            <span>🧪</span> Régulation du pH
          </div>
          <div class="badge-status-tag ${phTagClass}">${d.ph_status}</div>
        </div>
        <div class="advice-metric-row">
          <div class="metric-box">
            <div class="metric-label">pH Actuel</div>
            <div class="metric-val" style="color: #0284c7;">${d.ph_val}</div>
            <div class="metric-target">Cible : 7.2 - 7.4</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Correction pH-</div>
            <div class="metric-val" style="color: #dc2626;">${d.ph_minus_dose}g</div>
            <div class="metric-target">Bisulfate sodique</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Correction pH+</div>
            <div class="metric-val" style="color: #2563eb;">${d.ph_plus_dose}g</div>
            <div class="metric-target">Carbonate sodique</div>
          </div>
        </div>
        <div class="advice-action-box">
          <div class="action-icon">💡</div>
          <div>${phActionText}</div>
        </div>
      </div>

      <!-- 2. DESINFECTION & CHLORE / REDOX -->
      <div class="advice-card">
        <div class="advice-card-header">
          <div class="advice-card-title">
            <span>⚡</span> Désinfection & Chlore
          </div>
          <div class="badge-status-tag ${rxTagClass}">${d.cl_status}</div>
        </div>
        <div class="advice-metric-row">
          <div class="metric-box">
            <div class="metric-label">Redox (ORP)</div>
            <div class="metric-val" style="color: #0284c7;">${d.redox_val} mV</div>
            <div class="metric-target">Cible : 650 - 750 mV</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Chlore Libre Estimé</div>
            <div class="metric-val" style="color: #16a34a;">${d.free_cl} ppm</div>
            <div class="metric-target">Recommandé : 1.0 - 2.0</div>
          </div>
          <div class="metric-box">
            <div class="metric-label">Chlore Actif (HOCl)</div>
            <div class="metric-val" style="color: #d97706;">${d.active_cl} ppm</div>
            <div class="metric-target">Désinfectant réel</div>
          </div>
        </div>
        <div class="advice-action-box">
          <div class="action-icon">🛡️</div>
          <div>${rxActionText}</div>
        </div>
      </div>

      <!-- 3. EQUILIBRE DE L'EAU (LSI / LANGELIER) -->
      <div class="advice-card">
        <div class="advice-card-header">
          <div class="advice-card-title">
            <span>⚖️</span> Équilibre de l'eau (LSI)
          </div>
          <div class="badge-status-tag ${Math.abs(lsi) < 0.3 ? "tag-ok" : "tag-warn"}">${d.lsi_status}</div>
        </div>
        <div class="lsi-bar-wrapper">
          <div class="lsi-gradient-bar">
            <div class="lsi-cursor" style="left: ${lsi_cursor_pct}%;"></div>
          </div>
          <div class="lsi-labels-row">
            <span>Corrosive (-1.0)</span>
            <span style="color: #16a34a; font-weight: bold;">Équilibrée (0.0)</span>
            <span>Entartrante (+1.0)</span>
          </div>
        </div>
        <div class="advice-action-box" style="margin-top: 14px;">
          <div class="action-icon">📘</div>
          <div>
            <strong>Indice LSI : ${lsi > 0 ? "+" : ""}${lsi}</strong> — 
            ${
              Math.abs(lsi) <= 0.3
                ? "Votre eau est parfaitement équilibrée. Le liner, la tuyauterie et les sondes de mesure sont préservés."
                : lsi > 0.3
                ? "L'eau a tendance à précipiter le calcaire (risque de dépôts blanchâtres sur la ligne d'eau et dans le filtre)."
                : "L'eau est corrosive et agressive pour les éléments métalliques et les joints."
            }
          </div>
        </div>
      </div>

      <!-- 4. GESTION DE LA FILTRATION -->
      <div class="advice-card">
        <div class="advice-card-header">
          <div class="advice-card-title">
            <span>⏱️</span> Optimisation Filtration
          </div>
          <div class="badge-status-tag tag-info">${d.pump_state === "on" ? "En marche" : "À l'arrêt"}</div>
        </div>
        <div class="advice-action-box">
          <div class="action-icon">🏊</div>
          <div>
            <strong>Recommandation :</strong> ${d.advice_filtration}.<br>
            <em>Règle d'or :</em> Filtrez en journée pendant les heures les plus chaudes et d'ensoleillement pour une efficacité maximale contre la photosynthèse des algues.
          </div>
        </div>
      </div>
    `;
  }

  _bindCardEvents(cardEl, d) {
    const btnAnalyse = cardEl.querySelector("#tab-btn-analyse");
    const btnControle = cardEl.querySelector("#tab-btn-controle");
    const btnPump = cardEl.querySelector("#btn-toggle-pump");

    if (btnAnalyse) {
      btnAnalyse.addEventListener("click", () => {
        this._view = "analyse";
        this._updateData();
      });
    }

    if (btnControle) {
      btnControle.addEventListener("click", () => {
        this._view = "controle";
        this._updateData();
      });
    }

    if (btnPump && d.pump_entity_key && this._hass) {
      btnPump.addEventListener("click", () => {
        this._hass.callService("homeassistant", "toggle", {
          entity_id: d.pump_entity_key,
        });
      });
    }
  }
}

customElements.define("flipr-panel", FliprPanel);
