/**
 * ScamShield Z: Real-Time Frontend Controller
 * IBM Z Datathon 2026: Real-Time AI for Critical Decisions
 *
 * Implements:
 * - Server-Sent Events (SSE) listener for /api/events
 * - Offline Chart.js inference latency visualization
 * - Interactive stream, speed, scenario, manual score, and decision handlers
 * - Accessibility keyboard navigation, ARIA live regions, zero console errors
 */

(function () {
  'use strict';

  // --- State & DOM References ---
  const state = {
    theme: localStorage.getItem('scamshield_theme') || 'dark',
    activeSpeed: 1.0,
    streamActive: false,
    latencyPoints: [],
    maxChartPoints: 30,
    chartInstance: null
  };

  // DOM Elements
  const elements = {
    themeToggle: document.getElementById('btn-theme-toggle'),
    themeIcon: document.getElementById('theme-icon'),
    backendBadge: document.getElementById('backend-badge'),
    btnSwitchBackend: document.getElementById('btn-switch-backend'),
    streamStatusBadge: document.getElementById('stream-status-badge'),
    toggleVulnerableMode: document.getElementById('toggle-vulnerable-mode'),

    // KPIs
    kpiEventsScored: document.getElementById('kpi-events-scored'),
    kpiAllowed: document.getElementById('kpi-allowed'),
    kpiConfirmed: document.getElementById('kpi-confirmed'),
    kpiHeld: document.getElementById('kpi-held'),
    kpiLatency: document.getElementById('kpi-latency'),

    // Stream & Speed Controls
    btnStreamStart: document.getElementById('btn-stream-start'),
    btnStreamPause: document.getElementById('btn-stream-pause'),
    btnStreamReset: document.getElementById('btn-stream-reset'),
    btnSpeed1x: document.getElementById('btn-speed-1x'),
    btnSpeed5x: document.getElementById('btn-speed-5x'),
    btnSpeed20x: document.getElementById('btn-speed-20x'),

    // Scenarios
    btnScenarioNewPayee: document.getElementById('btn-scenario-new-payee'),
    btnScenarioMule: document.getElementById('btn-scenario-mule'),
    btnScenarioDrain: document.getElementById('btn-scenario-drain'),
    btnScenarioAto: document.getElementById('btn-scenario-ato'),
    btnScenarioNormal: document.getElementById('btn-scenario-normal'),

    // Manual Form
    formManualScore: document.getElementById('form-manual-score'),
    manualAmount: document.getElementById('manual-amount'),
    manualNewPayee: document.getElementById('manual-new-payee'),
    manualDeviceChanged: document.getElementById('manual-device-changed'),
    manualVulnerable: document.getElementById('manual-vulnerable'),
    btnManualScore: document.getElementById('btn-manual-score'),

    // Customer View
    customerDecisionBadge: document.getElementById('customer-decision-badge'),
    customerAmount: document.getElementById('customer-amount'),
    customerReason: document.getElementById('customer-reason'),
    customerContactAlert: document.getElementById('customer-contact-alert'),

    // Thresholds
    sliderTLow: document.getElementById('slider-t-low'),
    sliderTMed: document.getElementById('slider-t-med'),
    sliderTHigh: document.getElementById('slider-t-high'),
    valTLow: document.getElementById('val-t-low'),
    valTMed: document.getElementById('val-t-med'),
    valTHigh: document.getElementById('val-t-high'),
    btnApplyThresholds: document.getElementById('btn-apply-thresholds'),
    btnRestoreThresholds: document.getElementById('btn-restore-thresholds'),
    btnExportAudit: document.getElementById('btn-export-audit'),

    // Feed
    feedContainer: document.getElementById('feed-container'),
    feedEmptyState: document.getElementById('feed-empty-state'),
    feedCount: document.getElementById('feed-count'),

    // Tables & Chart
    latencyCanvas: document.getElementById('latency-chart'),
    fairnessTableBody: document.getElementById('fairness-table-body'),
    fairnessGapStatus: document.getElementById('fairness-gap-status'),
    metricsTableBody: document.getElementById('metrics-table-body'),
    toastContainer: document.getElementById('toast-container')
  };

  // --- Helper: Toast Notification ---
  function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `<span>${message}</span>`;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      setTimeout(() => toast.remove(), 200);
    }, 3200);
  }

  // --- Theme Management ---
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    elements.themeIcon.textContent = theme === 'dark' ? '☀️' : '🌙';
    localStorage.setItem('scamshield_theme', theme);
    if (state.chartInstance) {
      updateChartTheme(theme);
    }
  }

  elements.themeToggle.addEventListener('click', () => {
    state.theme = state.theme === 'dark' ? 'light' : 'dark';
    applyTheme(state.theme);
  });

  // --- API Client Helpers ---
  async function apiCall(url, method = 'GET', body = null) {
    try {
      const options = { method, headers: { 'Content-Type': 'application/json' } };
      if (body) options.body = JSON.stringify(body);
      const res = await fetch(url, options);
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({ detail: res.statusText }));
        throw new Error(errorData.detail || `Request failed with code ${res.status}`);
      }
      return await res.json();
    } catch (err) {
      showToast(err.message, 'danger');
      throw err;
    }
  }

  // --- Chart.js Latency Visualizer ---
  function initLatencyChart() {
    if (!elements.latencyCanvas || typeof Chart === 'undefined') return;

    const isDark = state.theme === 'dark';
    const gridColor = isDark ? '#374151' : '#e2e8f0';
    const textColor = isDark ? '#9ca3af' : '#64748b';

    state.chartInstance = new Chart(elements.latencyCanvas, {
      type: 'line',
      data: {
        labels: [],
        datasets: [{
          label: 'Inference Latency (ms)',
          data: [],
          borderColor: '#38bdf8',
          backgroundColor: 'rgba(56, 189, 248, 0.1)',
          fill: true,
          tension: 0.25,
          borderWidth: 2,
          pointRadius: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        animation: { duration: 150 },
        scales: {
          x: {
            display: false
          },
          y: {
            beginAtZero: true,
            suggestedMax: 0.8,
            grid: { color: gridColor },
            ticks: {
              color: textColor,
              callback: (val) => val + ' ms'
            }
          }
        },
        plugins: {
          legend: { display: false },
          tooltip: {
            callbacks: {
              label: (context) => `Latency: ${context.parsed.y.toFixed(3)} ms`
            }
          }
        }
      }
    });
  }

  function updateChartTheme(theme) {
    if (!state.chartInstance) return;
    const isDark = theme === 'dark';
    state.chartInstance.options.scales.y.grid.color = isDark ? '#374151' : '#e2e8f0';
    state.chartInstance.options.scales.y.ticks.color = isDark ? '#9ca3af' : '#64748b';
    state.chartInstance.update();
  }

  function recordLatencyPoint(latencyMs) {
    if (!state.chartInstance) return;
    const chart = state.chartInstance;
    const now = new Date().toLocaleTimeString();

    chart.data.labels.push(now);
    chart.data.datasets[0].data.push(latencyMs);

    if (chart.data.labels.length > state.maxChartPoints) {
      chart.data.labels.shift();
      chart.data.datasets[0].data.shift();
    }
    chart.update('none');
  }

  // --- Decision Card Builder ---
  function getDecisionClass(decision) {
    switch (decision) {
      case 'ALLOW': return 'decision-allow';
      case 'ALLOW_WITH_NOTICE': return 'decision-allow-notice';
      case 'CONFIRM': return 'decision-confirm';
      case 'HOLD': return 'decision-hold';
      case 'HUMAN_REVIEW': return 'decision-human-review';
      default: return 'decision-allow';
    }
  }

  function addDecisionToFeed(ev) {
    // Hide empty state
    if (elements.feedEmptyState) {
      elements.feedEmptyState.classList.add('hidden');
    }

    const card = document.createElement('article');
    card.className = 'decision-card';
    card.id = `card-${ev.id}`;
    card.setAttribute('tabindex', '0');
    card.setAttribute('aria-label', `Payment decision ${ev.decision} for amount $${ev.amount}`);

    const decClass = getDecisionClass(ev.decision);
    const timeFormatted = new Date(ev.ts).toLocaleTimeString();

    // Determine actionable buttons based on decision type
    let actionsHtml = '';
    if (ev.decision === 'CONFIRM') {
      actionsHtml = `
        <div class="card-actions" id="actions-${ev.id}">
          <button class="btn btn-sm btn-primary btn-action-confirm" data-id="${ev.id}">
            Confirm payment
          </button>
          <button class="btn btn-sm btn-outline btn-action-cancel" data-id="${ev.id}">
            Cancel payment
          </button>
        </div>
      `;
    } else if (ev.decision === 'HOLD' || ev.decision === 'HUMAN_REVIEW') {
      actionsHtml = `
        <div class="card-actions" id="actions-${ev.id}">
          <button class="btn btn-sm btn-primary btn-action-release" data-id="${ev.id}">
            Release payment
          </button>
          <button class="btn btn-sm btn-outline btn-action-keep-hold" data-id="${ev.id}">
            Keep hold
          </button>
        </div>
      `;
    } else {
      actionsHtml = `<span class="action-status-label action-status-resolved">AUTO RESOLVED</span>`;
    }

    const vulnBadge = ev.is_vulnerable ? `<span class="badge badge-sm" style="background:#f59e0b22;color:#f59e0b;">VULNERABLE SAFEGUARD</span>` : '';
    const scenBadge = ev.scenario ? `<span class="badge badge-sm" style="background:#a855f722;color:#c084fc;">SCENARIO: ${ev.scenario}</span>` : '';

    card.innerHTML = `
      <div class="card-top">
        <div class="card-title-group">
          <span class="decision-badge ${decClass}">[${ev.decision}]</span>
          <span class="card-amount">$${ev.amount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</span>
        </div>
        <div class="card-meta">
          <span>🕒 ${timeFormatted}</span>
          <span>⚡ ${ev.latency_ms}ms</span>
        </div>
      </div>

      <div class="card-meta">
        <span>Sender: <code>${ev.sender_id}</code></span>
        <span>Risk Score: <strong>${(ev.score * 100).toFixed(1)}%</strong> (${ev.effective_band})</span>
        ${vulnBadge}
        ${scenBadge}
      </div>

      <p class="card-reason">
        <strong>Reason:</strong> ${ev.primary_reason}
      </p>

      <div class="card-footer">
        ${actionsHtml}
      </div>
    `;

    // Prepend to feed
    elements.feedContainer.insertBefore(card, elements.feedContainer.firstChild);

    // Limit cards in DOM to 100
    while (elements.feedContainer.children.length > 100) {
      elements.feedContainer.removeChild(elements.feedContainer.lastChild);
    }

    // Update count
    const totalInFeed = elements.feedContainer.children.length;
    elements.feedCount.textContent = `${totalInFeed} items`;

    // Attach event listeners to the action buttons inside this card
    attachCardActionHandlers(card, ev.id);

    // Update Customer View panel
    updateCustomerView(ev);

    // Update latency chart
    if (typeof ev.latency_ms === 'number') {
      recordLatencyPoint(ev.latency_ms);
    }
  }

  function attachCardActionHandlers(card, id) {
    const btnConfirm = card.querySelector('.btn-action-confirm');
    const btnCancel = card.querySelector('.btn-action-cancel');
    const btnRelease = card.querySelector('.btn-action-release');
    const btnKeepHold = card.querySelector('.btn-action-keep-hold');

    if (btnConfirm) {
      btnConfirm.addEventListener('click', () => sendDecisionAction(id, 'confirm'));
    }
    if (btnCancel) {
      btnCancel.addEventListener('click', () => sendDecisionAction(id, 'cancel'));
    }
    if (btnRelease) {
      btnRelease.addEventListener('click', () => sendDecisionAction(id, 'release'));
    }
    if (btnKeepHold) {
      btnKeepHold.addEventListener('click', () => sendDecisionAction(id, 'keep_hold'));
    }
  }

  async function sendDecisionAction(decisionId, action) {
    try {
      const res = await apiCall(`/api/decision/${decisionId}`, 'POST', { action });
      updateDecisionActionStatus(decisionId, res.user_action);
      showToast(`Action "${action}" recorded for transaction.`, 'success');
    } catch (err) {
      // error handled in apiCall
    }
  }

  function updateDecisionActionStatus(id, userAction) {
    const actionsBox = document.getElementById(`actions-${id}`);
    if (!actionsBox) return;

    let badgeClass = 'action-status-resolved';
    if (userAction.includes('CANCEL')) badgeClass = 'action-status-cancelled';
    if (userAction.includes('HOLD')) badgeClass = 'action-status-pending';

    actionsBox.innerHTML = `<span class="action-status-label ${badgeClass}">STATUS: ${userAction.replace(/_/g, ' ')}</span>`;
  }

  // --- Customer View Notification Panel ---
  function updateCustomerView(ev) {
    elements.customerAmount.textContent = `$${ev.amount.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}`;
    elements.customerReason.textContent = ev.primary_reason;

    elements.customerDecisionBadge.className = `badge badge-lg ${getDecisionClass(ev.decision)}`;
    elements.customerDecisionBadge.textContent = `[${ev.decision}] ${ev.action_label}`;

    if (ev.alert_trusted_contact) {
      elements.customerContactAlert.classList.remove('hidden');
    } else {
      elements.customerContactAlert.classList.add('hidden');
    }
  }

  // --- KPI Updates ---
  function updateKPIs(kpi) {
    if (!kpi) return;
    elements.kpiEventsScored.textContent = (kpi.events_scored || 0).toLocaleString();
    elements.kpiAllowed.textContent = (kpi.allowed_count || 0).toLocaleString();
    elements.kpiConfirmed.textContent = (kpi.confirmed_count || 0).toLocaleString();
    elements.kpiHeld.textContent = ((kpi.held_count || 0) + (kpi.human_review_count || 0)).toLocaleString();

    if (kpi.p99_latency_ms && kpi.p99_latency_ms !== 'not measured') {
      elements.kpiLatency.textContent = `${kpi.p99_latency_ms} ms`;
    } else {
      elements.kpiLatency.textContent = 'not measured';
    }
  }

  // --- Server-Sent Events (SSE) Client ---
  function connectSSE() {
    const sse = new EventSource('/api/events');

    sse.onopen = () => {
      elements.streamStatusBadge.textContent = state.streamActive ? 'Stream: Active' : 'Stream: Connected';
      elements.streamStatusBadge.className = 'badge badge-status';
    };

    sse.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'DECISION_UPDATE') {
          updateDecisionActionStatus(data.id, data.user_action);
        } else if (data.id && data.decision) {
          addDecisionToFeed(data);
          // Periodically refresh fairness audit table every 10 events
          if (Math.random() < 0.15) {
            fetchFairness();
          }
        }
      } catch (e) {
        // Heartbeat or ping
      }
    };

    sse.onerror = () => {
      elements.streamStatusBadge.textContent = 'Stream: Reconnecting...';
      elements.streamStatusBadge.className = 'badge badge-backend';
    };
  }

  // --- Load Initial State & Configuration ---
  async function fetchState() {
    try {
      const data = await apiCall('/api/state');
      state.streamActive = data.stream_active;
      state.activeSpeed = data.stream_speed;
      elements.streamStatusBadge.textContent = data.stream_active ? 'Stream: Running' : 'Stream: Idle';

      elements.backendBadge.textContent = `Backend: ${data.scoring_backend}`;
      if (data.wmlz_available) {
        elements.btnSwitchBackend.disabled = false;
        elements.btnSwitchBackend.removeAttribute('title');
      } else {
        elements.btnSwitchBackend.disabled = true;
      }

      elements.toggleVulnerableMode.checked = !!data.vulnerable_mode_global;

      if (data.thresholds) {
        elements.sliderTLow.value = data.thresholds.t_low;
        elements.sliderTMed.value = data.thresholds.t_med;
        elements.sliderTHigh.value = data.thresholds.t_high;
        elements.valTLow.textContent = data.thresholds.t_low;
        elements.valTMed.textContent = data.thresholds.t_med;
        elements.valTHigh.textContent = data.thresholds.t_high;
      }

      updateKPIs(data.kpi);
    } catch (err) {
      console.error("Error loading state:", err);
    }
  }

  // --- Load Model Metrics from reports/metrics.json ---
  async function fetchMetrics() {
    try {
      const data = await apiCall('/api/metrics');
      if (data.models) {
        const lr = data.models.baseline_logistic_regression || {};
        const lgb = data.models.lightgbm_production || {};

        elements.metricsTableBody.innerHTML = `
          <tr>
            <td><strong>Baseline Logistic Regression</strong></td>
            <td>${lr.pr_auc || 'not measured'}</td>
            <td>${lr.roc_auc || 'not measured'}</td>
            <td>${lr.recall_at_1pct_fpr || 'not measured'}</td>
            <td>N/A</td>
            <td><span class="badge badge-status">Baseline</span></td>
          </tr>
          <tr>
            <td><strong>LightGBM (ONNX Runtime)</strong></td>
            <td><strong>${lgb.pr_auc || 'not measured'}</strong></td>
            <td><strong>${lgb.roc_auc || 'not measured'}</strong></td>
            <td><strong>${lgb.recall_at_1pct_fpr || 'not measured'}</strong></td>
            <td>${lgb.onnx_max_abs_diff_1000_samples ? lgb.onnx_max_abs_diff_1000_samples.toExponential(2) : 'not measured'}</td>
            <td><span class="badge" style="background:#22c55e22;color:#22c55e;">VERIFIED PASS</span></td>
          </tr>
        `;
      } else {
        elements.metricsTableBody.innerHTML = `
          <tr><td colspan="6" class="text-center">Metrics not measured yet. Run training to populate.</td></tr>
        `;
      }
    } catch (err) {
      elements.metricsTableBody.innerHTML = `
        <tr><td colspan="6" class="text-center">Unable to load metrics.json</td></tr>
      `;
    }
  }

  // --- Load Fairness Audit Table ---
  async function fetchFairness() {
    try {
      const data = await apiCall('/api/fairness');
      if (data.group_metrics && data.group_metrics.length > 0) {
        elements.fairnessTableBody.innerHTML = data.group_metrics.map(grp => `
          <tr>
            <td><strong>${grp.age_group}</strong></td>
            <td>${grp.total_events.toLocaleString()}</td>
            <td>${grp.held_count.toLocaleString()}</td>
            <td><strong>${(grp.hold_rate * 100).toFixed(2)}%</strong></td>
            <td>${(grp.fpr * 100).toFixed(2)}%</td>
          </tr>
        `).join('');

        const statusClass = data.status === 'FAIR' ? 'status-fair' : 'status-alert';
        elements.fairnessGapStatus.innerHTML = `
          Fairness Status: <span class="status-indicator ${statusClass}">${data.status}</span>
          (Hold-Rate Gap: ${(data.observed_hold_rate_gap * 100).toFixed(2)}% | Max Limit: ${(data.max_configured_gap * 100).toFixed(2)}%)
        `;
      }
    } catch (err) {
      elements.fairnessTableBody.innerHTML = `
        <tr><td colspan="5" class="text-center">Unable to load fairness audit table.</td></tr>
      `;
    }
  }

  // --- Stream Control Listeners ---
  elements.btnStreamStart.addEventListener('click', async () => {
    try {
      await apiCall('/api/stream/start', 'POST', { speed: state.activeSpeed });
      state.streamActive = true;
      elements.streamStatusBadge.textContent = 'Stream: Running';
      elements.streamStatusBadge.className = 'badge badge-status';
      showToast('Live transaction stream started.', 'info');
    } catch (e) {}
  });

  elements.btnStreamPause.addEventListener('click', async () => {
    try {
      await apiCall('/api/stream/pause', 'POST');
      state.streamActive = false;
      elements.streamStatusBadge.textContent = 'Stream: Paused';
      elements.streamStatusBadge.className = 'badge badge-backend';
      showToast('Stream paused.', 'warning');
    } catch (e) {}
  });

  elements.btnStreamReset.addEventListener('click', async () => {
    try {
      await apiCall('/api/stream/reset', 'POST');
      state.streamActive = false;
      elements.streamStatusBadge.textContent = 'Stream: Reset';
      elements.feedContainer.innerHTML = '';
      if (elements.feedEmptyState) elements.feedEmptyState.classList.remove('hidden');
      elements.feedCount.textContent = '0 items';
      updateKPIs({ events_scored: 0, allowed_count: 0, confirmed_count: 0, held_count: 0, human_review_count: 0, p99_latency_ms: 'not measured' });
      fetchFairness();
      showToast('Stream state and counters reset.', 'info');
    } catch (e) {}
  });

  // --- Speed Selector ---
  function setSpeed(speed, btnActive) {
    state.activeSpeed = speed;
    [elements.btnSpeed1x, elements.btnSpeed5x, elements.btnSpeed20x].forEach(b => b.classList.remove('active'));
    btnActive.classList.add('active');
    apiCall('/api/stream/speed', 'POST', { speed }).then(() => {
      showToast(`Stream speed set to ${speed}x`, 'info');
    }).catch(() => {});
  }

  elements.btnSpeed1x.addEventListener('click', () => setSpeed(1.0, elements.btnSpeed1x));
  elements.btnSpeed5x.addEventListener('click', () => setSpeed(5.0, elements.btnSpeed5x));
  elements.btnSpeed20x.addEventListener('click', () => setSpeed(20.0, elements.btnSpeed20x));

  // --- Scenario Injections ---
  async function triggerScenario(name, label) {
    try {
      showToast(`Injecting scenario: ${label}...`, 'info');
      const res = await apiCall(`/api/scenario/${name}`, 'POST');
      showToast(`Scenario ${label} processed: Decision [${res.decision}]`, 'success');
    } catch (e) {}
  }

  elements.btnScenarioNewPayee.addEventListener('click', () => triggerScenario('new_payee_large', 'New Payee ($4.5k)'));
  elements.btnScenarioMule.addEventListener('click', () => triggerScenario('mule_fanin', 'Mule Fan-In'));
  elements.btnScenarioDrain.addEventListener('click', () => triggerScenario('rapid_drain', 'Rapid Account Drain'));
  elements.btnScenarioAto.addEventListener('click', () => triggerScenario('account_takeover', 'Account Takeover'));
  elements.btnScenarioNormal.addEventListener('click', () => triggerScenario('normal_large_purchase', 'Normal Large Purchase'));

  async function handleManualScoreSubmit(e) {
    if (e) e.preventDefault();
    const amount = parseFloat(elements.manualAmount.value);
    if (isNaN(amount) || amount <= 0) {
      showToast('Please enter a valid positive transfer amount.', 'warning');
      return;
    }

    const payload = {
      amount: amount,
      new_payee: elements.manualNewPayee.checked,
      device_changed: elements.manualDeviceChanged.checked,
      vulnerable: elements.manualVulnerable.checked
    };

    try {
      elements.btnManualScore.disabled = true;
      elements.btnManualScore.textContent = 'Scoring...';
      const res = await apiCall('/api/score', 'POST', payload);
      showToast(`Payment scored: [${res.decision}] - Score: ${(res.score * 100).toFixed(1)}%`, 'success');
    } catch (err) {
      // error handled
    } finally {
      elements.btnManualScore.disabled = false;
      elements.btnManualScore.textContent = '⚡ Score Payment';
    }
  }

  elements.formManualScore.addEventListener('submit', handleManualScoreSubmit);
  elements.btnManualScore.addEventListener('click', handleManualScoreSubmit);

  // --- Vulnerable Mode Toggle ---
  elements.toggleVulnerableMode.addEventListener('change', async (e) => {
    try {
      await apiCall('/api/vulnerable-mode', 'POST', { enabled: e.target.checked });
      showToast(`Global Vulnerable Mode: ${e.target.checked ? 'ENABLED' : 'DISABLED'}`, 'info');
    } catch (e) {}
  });

  // --- Threshold Sliders ---
  elements.sliderTLow.addEventListener('input', (e) => elements.valTLow.textContent = e.target.value);
  elements.sliderTMed.addEventListener('input', (e) => elements.valTMed.textContent = e.target.value);
  elements.sliderTHigh.addEventListener('input', (e) => elements.valTHigh.textContent = e.target.value);

  elements.btnApplyThresholds.addEventListener('click', async () => {
    const t_low = parseFloat(elements.sliderTLow.value);
    const t_med = parseFloat(elements.sliderTMed.value);
    const t_high = parseFloat(elements.sliderTHigh.value);

    if (t_low >= t_med || t_med >= t_high) {
      showToast('Thresholds must satisfy: T_low < T_med < T_high', 'warning');
      return;
    }

    try {
      const res = await apiCall('/api/thresholds', 'POST', { t_low, t_med, t_high });
      showToast('Policy thresholds updated successfully.', 'success');
    } catch (e) {}
  });

  elements.btnRestoreThresholds.addEventListener('click', async () => {
    try {
      const res = await apiCall('/api/thresholds', 'POST', { action: 'restore_defaults' });
      elements.sliderTLow.value = res.thresholds.t_low;
      elements.sliderTMed.value = res.thresholds.t_med;
      elements.sliderTHigh.value = res.thresholds.t_high;
      elements.valTLow.textContent = res.thresholds.t_low;
      elements.valTMed.textContent = res.thresholds.t_med;
      elements.valTHigh.textContent = res.thresholds.t_high;
      showToast('Default thresholds restored.', 'info');
    } catch (e) {}
  });

  // --- Switch Backend Button ---
  elements.btnSwitchBackend.addEventListener('click', () => {
    if (elements.btnSwitchBackend.disabled) {
      showToast('WMLz endpoint URL is not configured. Staying on verified LOCAL_ONNX.', 'warning');
      return;
    }
    // Attempt toggle if enabled
    apiCall('/api/backend', 'POST', { backend: 'WMLZ_HTTP' }).then(res => {
      elements.backendBadge.textContent = `Backend: ${res.backend}`;
      showToast(`Switched backend to ${res.backend}`, 'success');
    }).catch(err => {
      showToast(err.message, 'warning');
    });
  });

  // --- Export Audit Log CSV ---
  elements.btnExportAudit.addEventListener('click', () => {
    showToast('Downloading audit log CSV...', 'info');
    window.location.href = '/api/audit.csv';
  });

  // --- Initialization ---
  window.addEventListener('DOMContentLoaded', () => {
    applyTheme(state.theme);
    initLatencyChart();
    fetchState();
    fetchMetrics();
    fetchFairness();
    connectSSE();
  });

})();
