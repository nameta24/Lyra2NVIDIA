/**
 * EventPulse — HUD Overlay
 * Injected into #hud-root on the viewer screen.
 */

let _onPhase = null;
let _demoMode = false;

export function initHUD({ demoMode, onPhase }) {
  _onPhase  = onPhase;
  _demoMode = demoMode;

  const root = document.getElementById('hud-root');
  root.innerHTML = `
    <!-- Brand top-left -->
    <div id="hud-brand" class="hud-panel">
      <div class="hud-logo-text">EVENT<span class="accent">PULSE</span></div>
      <div class="hud-live">LIVE</div>
    </div>

    <!-- Telemetry top-right -->
    <div id="hud-telemetry" class="hud-panel">
      <div class="tel-row">
        <span class="tel-label">ALT</span>
        <span class="tel-value green" id="tel-alt">—</span>
      </div>
      <div class="tel-row">
        <span class="tel-label">MODE</span>
        <span class="tel-value" id="tel-mode">—</span>
      </div>
      <div class="tel-row">
        <span class="tel-label">PHASE</span>
        <span class="tel-value" id="tel-phase">—</span>
      </div>
    </div>

    <!-- Demo mode badge -->
    <div id="hud-demo-badge" class="${demoMode ? 'visible' : ''}">⚠ DEMO MODE — Synthetic Scene</div>

    <!-- Venue name bottom-left -->
    <div id="hud-venue" class="hud-panel">
      <div id="hud-venue-name">Venue Intelligence</div>
      <div id="hud-venue-sub">EVENTPULSE AI PLATFORM · 2026</div>
    </div>

    <!-- Mode label bottom-right -->
    <div id="hud-mode" class="hud-panel">
      <div id="hud-mode-label">AERIAL</div>
      <div id="hud-mode-sub">CAMERA MODE</div>
    </div>

    <!-- Phase nav buttons (bottom centre) -->
    <div id="hud-nav">
      <button class="nav-btn active" id="btn-dropin"      onclick="window.__hudPhase('dropin')">↓ Drop In</button>
      <button class="nav-btn"        id="btn-flyover"     onclick="window.__hudPhase('flyover')">⇢ Flyover</button>
      <button class="nav-btn"        id="btn-walkthrough" onclick="window.__hudPhase('walkthrough')">⊙ Walkthrough</button>
    </div>

    <!-- Controls hint (walkthrough) -->
    <div id="hud-controls" class="hud-panel">
      <div class="ctrl-row">
        <span class="ctrl-key">W A S D</span>
        <span class="ctrl-desc">Move</span>
      </div>
      <div class="ctrl-row">
        <span class="ctrl-key">Mouse</span>
        <span class="ctrl-desc">Look</span>
      </div>
      <div class="ctrl-row">
        <span class="ctrl-key">Click</span>
        <span class="ctrl-desc">Lock cursor</span>
      </div>
      <div class="ctrl-row">
        <span class="ctrl-key">ESC</span>
        <span class="ctrl-desc">Release</span>
      </div>
    </div>

    <!-- Crosshair -->
    <div id="hud-crosshair"></div>

    <!-- Pointer-lock prompt -->
    <div id="pointer-lock-overlay">
      <p>WALKTHROUGH MODE</p>
      <span>CLICK TO CAPTURE CURSOR · ESC TO RELEASE</span>
    </div>
  `;

  // Expose phase switcher to inline onclick
  window.__hudPhase = (p) => {
    if (_onPhase) _onPhase(p);
    setActiveNav(p);
  };
}

const MODE_LABELS = {
  dropin:      ['AERIAL',   'SATELLITE DROP-IN'],
  flyover:     ['FLYOVER',  'CINEMATIC SWEEP'],
  walkthrough: ['GROUND',   'FIRST-PERSON WALK'],
};

export function updateHUD({ phase, altitude, t }) {
  const altEl   = document.getElementById('tel-alt');
  const modeEl  = document.getElementById('tel-mode');
  const phaseEl = document.getElementById('tel-phase');
  const labelEl = document.getElementById('hud-mode-label');
  const subEl   = document.getElementById('hud-mode-sub');
  const ctrlEl  = document.getElementById('hud-controls');
  const plEl    = document.getElementById('pointer-lock-overlay');

  if (!altEl) return;

  // Altitude in "feet" (cosmetic — multiply scene units × 3.28 for realism)
  const altFt = (altitude * 3.28).toFixed(0);
  altEl.textContent   = altFt + ' ft';
  modeEl.textContent  = phase.toUpperCase();
  phaseEl.textContent = Math.floor(t) + 's';

  const [ml, ms] = MODE_LABELS[phase] || ['—', '—'];
  labelEl.textContent = ml;
  subEl.textContent   = ms;

  // Show/hide walkthrough HUD elements
  const inWalk = phase === 'walkthrough';
  ctrlEl?.classList.toggle('visible', inWalk);
  if (plEl && inWalk && !document.pointerLockElement) {
    plEl.classList.add('visible');
  }
  if (!inWalk && plEl) plEl.classList.remove('visible');

  setActiveNav(phase);
}

function setActiveNav(phase) {
  ['dropin','flyover','walkthrough'].forEach(p => {
    const btn = document.getElementById(`btn-${p}`);
    if (btn) btn.classList.toggle('active', p === phase);
  });
}
