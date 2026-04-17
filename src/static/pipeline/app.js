/* Meditation Video Pipeline — Vanilla JS, no framework */
'use strict';

// ---------------------------------------------------------------------------
// State
// ---------------------------------------------------------------------------
let currentRunId = null;
let sseAbortController = null;

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------

function apiKey() {
  return localStorage.getItem('api_key') || '';
}

async function apiCall(method, path, body = null) {
  const opts = {
    method,
    headers: { 'X-API-Key': apiKey(), 'Content-Type': 'application/json' },
  };
  if (body !== null) opts.body = JSON.stringify(body);
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    let detail = `${method} ${path} → ${resp.status}`;
    try { const d = await resp.json(); detail = d.detail || detail; } catch (_) {}
    throw new Error(detail);
  }
  return resp.json();
}

function showToast(msg, type = '') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `show ${type}`;
  clearTimeout(el._timer);
  el._timer = setTimeout(() => { el.className = ''; }, 3500);
}

function hideAllPanels() {
  ['script-panel', 'audio-panel', 'image-prompt-panel', 'image-panel', 'video-panel', 'error-panel'].forEach(id => {
    document.getElementById(id).style.display = 'none';
  });
}

// ---------------------------------------------------------------------------
// fetchEventSource — custom SSE with auth header (task 11.14)
// ---------------------------------------------------------------------------
async function* fetchEventSource(url, headers) {
  const resp = await fetch(url, { headers });
  if (!resp.ok) throw new Error(`SSE connect failed: ${resp.status}`);
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buf = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true });
    const lines = buf.split('\n');
    buf = lines.pop(); // keep incomplete line
    let eventData = null;
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        eventData = line.slice(6).trim();
      } else if (line.trim() === '' && eventData) {
        try { yield JSON.parse(eventData); } catch (_) {}
        eventData = null;
      }
    }
  }
}

// ---------------------------------------------------------------------------
// Settings panel (task 11.5)
// ---------------------------------------------------------------------------
function openSettings() {
  const overlay = document.getElementById('settings-overlay');
  document.getElementById('api-key-input').value = apiKey();
  overlay.classList.add('visible');
}

function closeSettings() {
  document.getElementById('settings-overlay').classList.remove('visible');
}

document.getElementById('settings-btn').addEventListener('click', openSettings);
document.getElementById('cancel-settings-btn').addEventListener('click', closeSettings);
document.getElementById('save-settings-btn').addEventListener('click', () => {
  const key = document.getElementById('api-key-input').value.trim();
  localStorage.setItem('api_key', key);
  closeSettings();
  showToast('API key saved', 'success');
});

// Show settings on first load if no key
if (!apiKey()) openSettings();

// ---------------------------------------------------------------------------
// Populate form dropdowns from registries (task 11.6)
// ---------------------------------------------------------------------------
async function loadRegistries() {
  try {
    const [styles, durations] = await Promise.all([
      apiCall('GET', '/pipeline/styles'),
      apiCall('GET', '/pipeline/durations'),
    ]);

    const styleSelect = document.getElementById('style-select');
    styleSelect.innerHTML = '';
    styles.forEach(s => {
      const opt = document.createElement('option');
      opt.value = s.key;
      opt.textContent = s.label;
      opt.title = s.description || '';
      styleSelect.appendChild(opt);
    });

    const durSelect = document.getElementById('duration-select');
    durSelect.innerHTML = '';
    durations.forEach(d => {
      const opt = document.createElement('option');
      opt.value = d.key;
      opt.textContent = d.label;
      durSelect.appendChild(opt);
    });
    // Default to 10min if available
    const tenMin = durSelect.querySelector('option[value="shorts"]');
    if (tenMin) tenMin.selected = true;
  } catch (err) {
    showToast(`Failed to load registries: ${err.message}`, 'error');
  }
}

loadRegistries();

// ---------------------------------------------------------------------------
// Create run (task 11.6)
// ---------------------------------------------------------------------------
document.getElementById('create-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const btn = document.getElementById('create-btn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Starting…';

  const title = document.getElementById('title-input').value.trim() || 'Meditation';
  const voiceId = document.getElementById('voice-id-input').value.trim() || null;
  const imageBackend = document.getElementById('image-backend-select').value || null;
  const imageQuality = document.getElementById('image-quality-select').value || null;
  const produceShorts = document.getElementById('produce-shorts-checkbox').checked;
  const enableKaraoke = document.getElementById('enable-karaoke-checkbox').checked;
  const styleKey = document.getElementById('style-select').value;
  const durationKey = document.getElementById('duration-select').value;

  const body = {
    items: [{ title, custom_instructions: null, notion_record_id: null }],
    voice_id: voiceId,
    style_key: styleKey,
    duration_key: durationKey,
    video_format: document.getElementById('video-format-select').value || 'long_form',
    image_backend: imageBackend,
    image_quality: imageQuality,
    produce_shorts: produceShorts,
    enable_karaoke: enableKaraoke,
  };

  try {
    const data = await apiCall('POST', '/pipeline/runs', body);
    currentRunId = data.run_id;
    startRunView(currentRunId);
  } catch (err) {
    showToast(`Failed to start run: ${err.message}`, 'error');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Start Pipeline';
  }
});

// ---------------------------------------------------------------------------
// Run view
// ---------------------------------------------------------------------------
function startRunView(runId) {
  document.getElementById('create-section').style.display = 'none';
  document.getElementById('run-section').style.display = '';
  document.getElementById('run-id-display').textContent = `Run: ${runId.slice(0, 8)}\u2026`;
  document.getElementById('new-run-btn').style.display = 'none';
  hideAllPanels();
  resetTimeline();
  // Sync URL so the run survives a page refresh
  const url = new URL(window.location.href);
  url.searchParams.set('run_id', runId);
  history.pushState({ runId }, '', url);
  startSSE(runId);
}

document.getElementById('new-run-btn').addEventListener('click', () => {
  if (sseAbortController) sseAbortController.abort();
  currentRunId = null;
  document.getElementById('run-section').style.display = 'none';
  document.getElementById('create-section').style.display = '';
  document.getElementById('title-input').value = '';
  // Clear run_id from URL
  const url = new URL(window.location.href);
  url.searchParams.delete('run_id');
  history.pushState({}, '', url);
});

// ---------------------------------------------------------------------------
// Stage timeline (task 11.8)
// ---------------------------------------------------------------------------
const STAGE_TO_DOT = {
  script: 'script',
  awaiting_script_approval: 'script',
  audio: 'audio',
  awaiting_audio_approval: 'audio',
  image_prompt: 'image',
  awaiting_image_prompt_approval: 'image',
  image: 'image',
  awaiting_image_approval: 'image',
  video: 'video',
  complete: 'video',
  failed: null,
};

function resetTimeline() {
  document.querySelectorAll('#stage-timeline .stage').forEach(el => {
    el.classList.remove('running', 'awaiting', 'complete', 'failed');
  });
}

function updateTimeline(stage, status) {
  const stageKey = STAGE_TO_DOT[stage];
  if (!stageKey) return;
  const el = document.querySelector(`#stage-timeline .stage[data-stage="${stageKey}"]`);
  if (!el) return;

  el.classList.remove('running', 'awaiting', 'complete', 'failed');
  if (status === 'running') el.classList.add('running');
  else if (status === 'awaiting_approval') el.classList.add('awaiting');
  else if (status === 'complete') el.classList.add('complete');
  else if (status === 'failed') el.classList.add('failed');
}

// ---------------------------------------------------------------------------
// SSE listener (task 11.14)
// ---------------------------------------------------------------------------
function startSSE(runId) {
  if (sseAbortController) sseAbortController.abort();
  sseAbortController = new AbortController();

  (async () => {
    try {
      const url = `/pipeline/runs/${runId}/events`;
      const headers = { 'X-API-Key': apiKey() };
      for await (const event of fetchEventSource(url, headers)) {
        await handleStageEvent(event);
        if (event.status === 'complete' || event.status === 'failed') break;
      }
    } catch (err) {
      if (!sseAbortController.signal.aborted) {
        showToast(`SSE disconnected: ${err.message}`, 'error');
      }
    }
  })();
}

// ---------------------------------------------------------------------------
// Stage panel rendering (tasks 11.9–11.13)
// ---------------------------------------------------------------------------
async function handleStageEvent(event) {
  const { stage, status } = event;
  updateTimeline(stage, status);
  await renderStagePanel(stage, status, event.message);
}

async function renderStagePanel(stage, status, message) {
  hideAllPanels();

  if (stage === 'awaiting_script_approval') {
    await showScriptPanel();
  } else if (stage === 'awaiting_audio_approval') {
    await showAudioPanel();
  } else if (stage === 'awaiting_image_prompt_approval') {
    await showImagePromptPanel();
  } else if (stage === 'awaiting_image_approval') {
    await showImagePanel();
  } else if (stage === 'complete') {
    await showVideoPanel();
    document.getElementById('new-run-btn').style.display = '';
  } else if (stage === 'failed') {
    showErrorPanel(message || 'An unknown error occurred.');
    document.getElementById('new-run-btn').style.display = '';
  }
}

// Task 11.9 — Script approval panel
async function showScriptPanel() {
  try {
    const run = await apiCall('GET', `/pipeline/runs/${currentRunId}`);
    const body = run.script?.body || '';
    const scriptEl = document.getElementById('script-body');
    // Highlight [pause X seconds] markers as styled badges
    scriptEl.innerHTML = body.replace(
      /\[pause (\d+) seconds?\]/g,
      '<span class="pause-marker">⏸ $& </span>'
    );
    document.getElementById('script-panel').style.display = '';
  } catch (err) {
    showToast(`Could not load script: ${err.message}`, 'error');
  }
}

// Task 11.10 — Audio approval panel
async function showAudioPanel() {
  const panel = document.getElementById('audio-panel');
  const playerEl = document.getElementById('audio-player');
  const transcriptEl = document.getElementById('audio-transcript');
  // Show panel with loading state first so the user sees progress immediately
  playerEl.innerHTML = '<div class="loading-row"><span class="spinner"></span> Loading audio\u2026</div>';
  transcriptEl.innerHTML = '';
  panel.style.display = 'block';

  const [audioResult, runResult] = await Promise.allSettled([
    fetch(`/pipeline/runs/${currentRunId}/audio`, { headers: { 'X-API-Key': apiKey() } }),
    apiCall('GET', `/pipeline/runs/${currentRunId}`),
  ]);

  if (audioResult.status === 'fulfilled' && audioResult.value.ok) {
    const blob = await audioResult.value.blob();
    const url = URL.createObjectURL(blob);
    playerEl.innerHTML = `<audio controls src="${url}" style="width:100%"></audio>`;
  } else {
    const err = audioResult.reason || audioResult.value;
    playerEl.innerHTML = `<div style="color:var(--color-red);font-size:13px">Could not load audio: ${err?.message || err}</div>`;
  }

  if (runResult.status === 'fulfilled' && runResult.value.script?.body) {
    transcriptEl.innerHTML = runResult.value.script.body.replace(
      /\[pause (\d+) seconds?\]/g,
      '<span class="pause-marker">\u23f8 $& </span>'
    );
  }
}

// Image prompt + YouTube metadata approval panel
async function showImagePromptPanel() {
  const panel = document.getElementById('image-prompt-panel');
  panel.style.display = 'block';
  try {
    const run = await apiCall('GET', `/pipeline/runs/${currentRunId}`);
    document.getElementById('image-prompt-textarea').value = run.image_prompt || '';
    const yt = run.youtube_metadata;
    if (yt) {
      document.getElementById('yt-title-input').value = yt.title || '';
      document.getElementById('yt-description-textarea').value = yt.description || '';
      document.getElementById('yt-tags-input').value = (yt.tags || []).join(', ');
    }
  } catch (err) {
    showToast(`Could not load metadata: ${err.message}`, 'error');
  }
}

async function saveAndApproveImagePrompt() {
  const prompt = document.getElementById('image-prompt-textarea').value.trim();
  if (!prompt) { showToast('Image prompt cannot be empty', 'error'); return; }
  try {
    await apiCall('PATCH', `/pipeline/runs/${currentRunId}/image-prompt`, { image_prompt: prompt });
    await approveStage();
  } catch (err) {
    showToast(`Failed: ${err.message}`, 'error');
  }
}
async function showImagePanel() {
  const panel = document.getElementById('image-panel');
  const container = document.getElementById('image-container');
  panel.style.display = '';
  container.innerHTML = '<div class="loading-row"><span class="spinner"></span> Loading image…</div>';

  try {
    const resp = await fetch(`/pipeline/runs/${currentRunId}/image`, {
      headers: { 'X-API-Key': apiKey() },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    container.innerHTML = `<img id="image-preview" src="${url}" alt="Background image">`;
  } catch (err) {
    container.innerHTML = `<div style="color:var(--color-red);font-size:13px">Could not load image: ${err.message}</div>`;
  }
}

// Task 11.12 — Video complete panel
async function showVideoPanel() {
  const panel = document.getElementById('video-panel');
  const container = document.getElementById('video-download-container');
  panel.style.display = '';
  container.innerHTML = '<div class="loading-row"><span class="spinner"></span> Preparing download…</div>';

  // Show file system path so the user knows where to find the files
  const pathEl = document.getElementById('video-file-path');
  if (pathEl) pathEl.textContent = `📁 $HAVACHAT_KNOWLEDGE_PATH/pipeline_runs/${currentRunId}/video.mp4`;

  try {
    const resp = await fetch(`/pipeline/runs/${currentRunId}/video`, {
      headers: { 'X-API-Key': apiKey() },
    });
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `meditation_${currentRunId.slice(0, 8)}.mp4`;
    a.className = 'download-link';
    a.innerHTML = '⬇ Download video.mp4';
    container.innerHTML = '';
    container.appendChild(a);
  } catch (err) {
    container.innerHTML = `<div style="color:var(--color-red);font-size:13px">Could not prepare download: ${err.message}</div>`;
  }
}

// Task 11.13 — Error panel
function showErrorPanel(message) {
  document.getElementById('error-message').textContent = message;
  document.getElementById('error-panel').style.display = '';
  // Retry button: figure out which stage to retry by querying current run
  document.getElementById('retry-btn').onclick = async () => {
    try {
      const run = await apiCall('GET', `/pipeline/runs/${currentRunId}`);
      // Retry the most recent completed stage
      let stage = 'script';
      if (run.image_ready) stage = 'video';
      else if (run.audio_ready) stage = 'image';
      else if (run.script) stage = 'audio';
      await rerunStage(stage);
    } catch (err) {
      showToast(`Retry failed: ${err.message}`, 'error');
    }
  };
}

// ---------------------------------------------------------------------------
// Approve / Rerun helpers
// ---------------------------------------------------------------------------
async function approveStage() {
  try {
    await apiCall('POST', `/pipeline/runs/${currentRunId}/approve`);
    // Panel transitions are driven by SSE events — do not call hideAllPanels() here
    // as it races against showAudioPanel / showImagePanel mid-execution.
  } catch (err) {
    showToast(`Approve failed: ${err.message}`, 'error');
  }
}

async function rerunStage(stage) {
  try {
    await apiCall('POST', `/pipeline/runs/${currentRunId}/rerun/${stage}`);
    hideAllPanels();
    resetTimeline();
    startSSE(currentRunId);
    showToast(`Rerunning ${stage}…`);
  } catch (err) {
    showToast(`Rerun failed: ${err.message}`, 'error');
  }
}

// ---------------------------------------------------------------------------
// Button wiring
// ---------------------------------------------------------------------------
document.getElementById('approve-script-btn').addEventListener('click', approveStage);
document.getElementById('rerun-script-btn').addEventListener('click', () => rerunStage('script'));

document.getElementById('approve-audio-btn').addEventListener('click', approveStage);
document.getElementById('rerun-audio-btn').addEventListener('click', () => rerunStage('audio'));

document.getElementById('approve-image-prompt-btn').addEventListener('click', saveAndApproveImagePrompt);
document.getElementById('rerun-image-prompt-btn').addEventListener('click', () => rerunStage('image_prompt'));

document.getElementById('approve-image-btn').addEventListener('click', approveStage);
document.getElementById('rerun-image-btn').addEventListener('click', () => rerunStage('image'));

document.getElementById('rerun-video-btn').addEventListener('click', () => rerunStage('video'));

// ---------------------------------------------------------------------------
// Resume run
// ---------------------------------------------------------------------------
async function resumeRun(runId) {
  if (!runId) { showToast('Enter a run ID to resume', 'error'); return; }
  try {
    await apiCall('GET', `/pipeline/runs/${runId}`);
    currentRunId = runId;
    startRunView(runId);
  } catch (err) {
    showToast(`Run not found: ${err.message}`, 'error');
  }
}

document.getElementById('resume-btn').addEventListener('click', () => {
  const runId = document.getElementById('resume-run-id-input').value.trim();
  resumeRun(runId);
});

// Restore run from URL on page load (?run_id=...)
(async () => {
  const params = new URLSearchParams(window.location.search);
  const runIdFromUrl = params.get('run_id');
  if (runIdFromUrl) {
    // Pre-fill the resume input in case the API call fails
    document.getElementById('resume-run-id-input').value = runIdFromUrl;
    await resumeRun(runIdFromUrl);
  }
})();
