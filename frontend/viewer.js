/**
 * EventPulse Venue Intelligence — Three.js Viewer
 * Handles: PLY loading, drop-in → flyover → walkthrough camera sequence
 */

import * as THREE from 'three';
import { PLYLoader } from 'three/addons/loaders/PLYLoader.js';
import { initHUD, updateHUD } from './hud.js';

const API_BASE = 'http://localhost:8000';

// ── DOM refs ──────────────────────────────────────────────────────────────
const uploadScreen    = document.getElementById('upload-screen');
const processingScreen= document.getElementById('processing-screen');
const viewerScreen    = document.getElementById('viewer-screen');
const dropZone        = document.getElementById('drop-zone');
const fileInput       = document.getElementById('file-input');
const browseBtn       = document.getElementById('browse-btn');
const canvas          = document.getElementById('three-canvas');
const previewImg      = document.getElementById('preview-img');
const procFilename    = document.getElementById('proc-filename');
const progressBar     = document.getElementById('progress-bar');
const progressPct     = document.getElementById('progress-pct');
const progressStage   = document.getElementById('progress-stage');

// ── State ─────────────────────────────────────────────────────────────────
let jobId       = null;
let pollTimer   = null;
let demoMode    = false;
let sceneReady  = false;

// Camera phases: 'dropin' | 'flyover' | 'walkthrough'
let phase          = 'dropin';
let phaseStartTime = 0;
let phaseT         = 0;

// Walkthrough state
let keys         = { w:false, a:false, s:false, d:false };
let yaw          = 0;   // radians
let pitch        = 0;
const EYE_HEIGHT = 1.7;
const WALK_SPEED = 8;

// Three.js
let renderer, scene, camera, clock;
let pointCloud = null;
let sceneCenter= new THREE.Vector3();
let sceneBounds= { min: new THREE.Vector3(), max: new THREE.Vector3() };

// ── Upload / drag-drop ────────────────────────────────────────────────────
browseBtn.addEventListener('click', () => fileInput.click());
dropZone .addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', e => handleFile(e.target.files[0]));

dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault();
  dropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) handleFile(f);
});

async function handleFile(file) {
  if (!file || !file.type.startsWith('image/')) return;

  // Show preview
  const url = URL.createObjectURL(file);
  previewImg.src = url;
  procFilename.textContent = file.name;

  switchScreen(uploadScreen, processingScreen);

  const fd = new FormData();
  fd.append('file', file);

  try {
    const res = await fetch(`${API_BASE}/api/process-venue`, { method: 'POST', body: fd });
    if (!res.ok) throw new Error(await res.text());
    const { job_id } = await res.json();
    jobId = job_id;
    startPolling();
  } catch (err) {
    console.error('Upload failed:', err);
    activateFallback();
  }
}

// ── Polling ───────────────────────────────────────────────────────────────
const STAGES = [
  [0,  20,  'Initialising A100 GPU…'],
  [20, 40,  'Loading Lyra 2.0 weights…'],
  [40, 60,  'Estimating depth map…'],
  [60, 80,  'Reconstructing point cloud…'],
  [80, 95,  'Normalising scene geometry…'],
  [95, 100, 'Streaming to browser…'],
];
const STEPS = ['step-0','step-1','step-2','step-3','step-4'];

function updateProgressUI(pct) {
  progressBar.style.width = pct + '%';
  progressPct.textContent  = pct + '%';

  for (const [start, end, label] of STAGES) {
    if (pct >= start && pct < end) { progressStage.textContent = label; break; }
  }

  STEPS.forEach((id, i) => {
    const el = document.getElementById(id);
    const threshold = (i + 1) * 20;
    el.classList.toggle('done',   pct > threshold);
    el.classList.toggle('active', pct >= threshold - 20 && pct <= threshold);
  });
}

function startPolling() {
  pollTimer = setInterval(async () => {
    try {
      const res  = await fetch(`${API_BASE}/api/job/${jobId}`);
      const data = await res.json();

      updateProgressUI(data.progress || 0);

      if (data.status === 'done') {
        clearInterval(pollTimer);
        demoMode = data.demo_mode;
        await loadScene();
      }
    } catch (err) {
      console.warn('Poll error:', err);
    }
  }, 2000);
}

async function activateFallback() {
  demoMode = true;
  // Load the static fallback PLY directly
  switchScreen(processingScreen, viewerScreen);
  initThree();
  loadPLYFromUrl('/sample_scenes/concession_fallback.ply');
}

async function loadScene() {
  switchScreen(processingScreen, viewerScreen);
  initThree();
  loadPLYFromUrl(`${API_BASE}/api/scene/${jobId}/scene.ply`);
}

// ── Three.js init ─────────────────────────────────────────────────────────
function initThree() {
  renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
  renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
  renderer.setSize(innerWidth, innerHeight);
  renderer.setClearColor(0x000000);

  scene = new THREE.Scene();
  scene.fog = new THREE.FogExp2(0x000000, 0.008);

  camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.1, 2000);
  clock  = new THREE.Clock();

  // Ambient light so points aren't pure black if we add meshes later
  scene.add(new THREE.AmbientLight(0xffffff, 0.2));

  initHUD({ demoMode, onPhase: jumpToPhase });
  setupInput();

  window.addEventListener('resize', () => {
    renderer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
  });

  renderer.setAnimationLoop(animate);
}

// ── PLY loading ───────────────────────────────────────────────────────────
function loadPLYFromUrl(url) {
  const loader = new PLYLoader();
  loader.load(
    url,
    geo => onPLYLoaded(geo),
    xhr => console.log(`PLY: ${(xhr.loaded / xhr.total * 100).toFixed(0)}%`),
    err => { console.error('PLY load error', err); onPLYLoaded(buildFallbackGeo()); }
  );
}

function onPLYLoaded(geo) {
  geo.computeBoundingBox();
  const box = geo.boundingBox;

  // Centre the geometry at origin
  box.getCenter(sceneCenter);
  geo.translate(-sceneCenter.x, -sceneCenter.y, -sceneCenter.z);
  geo.computeBoundingBox();

  sceneBounds.min.copy(geo.boundingBox.min);
  sceneBounds.max.copy(geo.boundingBox.max);

  // Auto-scale to fit in a ~200-unit cube
  const size = new THREE.Vector3();
  geo.boundingBox.getSize(size);
  const maxDim = Math.max(size.x, size.y, size.z);
  const scaleFactor = 200 / maxDim;
  geo.scale(scaleFactor, scaleFactor, scaleFactor);
  geo.computeBoundingBox();
  sceneBounds.min.copy(geo.boundingBox.min);
  sceneBounds.max.copy(geo.boundingBox.max);

  const mat = new THREE.PointsMaterial({
    size: 0.35,
    vertexColors: geo.hasAttribute('color'),
    color: geo.hasAttribute('color') ? 0xffffff : 0x4ade80,
    sizeAttenuation: true,
  });

  pointCloud = new THREE.Points(geo, mat);
  scene.add(pointCloud);

  sceneReady  = true;
  phaseStartTime = clock.getElapsedTime();
  phase = 'dropin';
}

// ── Fallback procedural geometry ──────────────────────────────────────────
function buildFallbackGeo() {
  const N = 30_000;
  const pos = new Float32Array(N * 3);
  const col = new Float32Array(N * 3);
  for (let i = 0; i < N; i++) {
    const x = (Math.random() - 0.5) * 200;
    const z = (Math.random() - 0.5) * 200;
    const y = Math.sin(x * 0.05) * 5 + Math.cos(z * 0.05) * 4 + Math.random() * 0.5;
    pos[i*3]=x; pos[i*3+1]=y; pos[i*3+2]=z;
    col[i*3]= 0.15 + Math.random()*0.1;
    col[i*3+1]= 0.45 + Math.random()*0.2;
    col[i*3+2]= 0.08 + Math.random()*0.1;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  geo.setAttribute('color',    new THREE.BufferAttribute(col, 3));
  geo.computeBoundingBox();
  return geo;
}

// ── Camera phases ─────────────────────────────────────────────────────────
const DROP_DUR   = 8;   // seconds
const FLYOVER_DUR= 12;
const EASE_CUBIC = t => t < 0.5 ? 4*t*t*t : 1 - Math.pow(-2*t+2,3)/2;

function animate() {
  if (!sceneReady) return;
  const dt = clock.getDelta();
  const t  = clock.getElapsedTime();
  phaseT = t - phaseStartTime;

  if (phase === 'dropin')     doDropIn(phaseT, dt);
  else if (phase === 'flyover')  doFlyover(phaseT, dt);
  else if (phase === 'walkthrough') doWalkthrough(dt);

  updateHUD({ phase, altitude: camera.position.y, t: phaseT });
  renderer.render(scene, camera);
}

function doDropIn(pt, dt) {
  const minY  = sceneBounds.min.y;
  const startY= 450;
  const endY  = minY + 25;
  const alpha  = Math.min(pt / DROP_DUR, 1);
  const eased  = EASE_CUBIC(alpha);

  const radius = 80 * (1 - eased * 0.6);
  const angle  = pt * 0.5;

  camera.position.set(
    Math.cos(angle) * radius,
    startY + (endY - startY) * eased,
    Math.sin(angle) * radius,
  );
  camera.lookAt(0, minY + 5, 0);

  if (alpha >= 1) { phase = 'flyover'; phaseStartTime = clock.getElapsedTime(); }
}

function doFlyover(pt, dt) {
  const minY = sceneBounds.min.y;
  const alpha = Math.min(pt / FLYOVER_DUR, 1);

  const x = -100 + alpha * 200;
  const y = minY + 22;
  const z = -30 + Math.sin(alpha * Math.PI) * 20;

  camera.position.set(x, y, z);
  camera.lookAt(x + 10, minY + 2, z - 20);

  if (alpha >= 1) {
    // Init walkthrough camera at ground level, centre of scene
    camera.position.set(0, sceneBounds.min.y + EYE_HEIGHT, 20);
    yaw = Math.PI; pitch = 0;
    phase = 'walkthrough';
    phaseStartTime = clock.getElapsedTime();
  }
}

function doWalkthrough(dt) {
  const minY = sceneBounds.min.y + EYE_HEIGHT;
  const maxY = minY; // locked to ground

  // Movement
  const dir = new THREE.Vector3();
  const right = new THREE.Vector3();
  const forward = new THREE.Vector3(
    Math.sin(yaw), 0, Math.cos(yaw)
  );
  right.crossVectors(forward, new THREE.Vector3(0,1,0)).normalize();

  if (keys.w) dir.addScaledVector(forward, -1);
  if (keys.s) dir.addScaledVector(forward,  1);
  if (keys.a) dir.addScaledVector(right,   -1);
  if (keys.d) dir.addScaledVector(right,    1);

  if (dir.lengthSq() > 0) dir.normalize();
  camera.position.addScaledVector(dir, WALK_SPEED * dt);
  camera.position.y = minY;

  // Bounds clamp
  const B = 120;
  camera.position.x = THREE.MathUtils.clamp(camera.position.x, -B, B);
  camera.position.z = THREE.MathUtils.clamp(camera.position.z, -B, B);

  // Look direction
  const qYaw   = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0), yaw);
  const qPitch = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(1,0,0), pitch);
  camera.quaternion.copy(qYaw).multiply(qPitch);
}

// ── Manual phase jump ─────────────────────────────────────────────────────
function jumpToPhase(p) {
  phase = p;
  phaseStartTime = clock.getElapsedTime();
  if (p === 'walkthrough') {
    camera.position.set(0, sceneBounds.min.y + EYE_HEIGHT, 20);
    yaw = Math.PI; pitch = 0;
  }
}

// ── Input ─────────────────────────────────────────────────────────────────
function setupInput() {
  document.addEventListener('keydown', e => {
    const k = e.key.toLowerCase();
    if (k === 'w') keys.w = true;
    if (k === 'a') keys.a = true;
    if (k === 's') keys.s = true;
    if (k === 'd') keys.d = true;
  });
  document.addEventListener('keyup', e => {
    const k = e.key.toLowerCase();
    if (k === 'w') keys.w = false;
    if (k === 'a') keys.a = false;
    if (k === 's') keys.s = false;
    if (k === 'd') keys.d = false;
  });

  document.addEventListener('mousemove', e => {
    if (phase !== 'walkthrough') return;
    if (!document.pointerLockElement) return;
    const sensitivity = 0.002;
    yaw   -= e.movementX * sensitivity;
    pitch -= e.movementY * sensitivity;
    pitch  = THREE.MathUtils.clamp(pitch, -Math.PI / 3, Math.PI / 3);
  });

  document.addEventListener('pointerlockchange', () => {
    const locked = !!document.pointerLockElement;
    document.getElementById('pointer-lock-overlay')?.classList.toggle('visible', !locked && phase === 'walkthrough');
    document.getElementById('hud-crosshair')?.classList.toggle('visible', locked);
  });

  // Click on viewer to request pointer lock in walkthrough mode
  canvas.addEventListener('click', () => {
    if (phase === 'walkthrough' && !document.pointerLockElement) {
      canvas.requestPointerLock();
    }
  });
}

// ── Screen transitions ────────────────────────────────────────────────────
function switchScreen(from, to) {
  from.style.opacity = '0';
  setTimeout(() => {
    from.classList.remove('active');
    to.classList.add('active');
    to.style.opacity = '0';
    requestAnimationFrame(() => { to.style.opacity = '1'; });
  }, 600);
}
