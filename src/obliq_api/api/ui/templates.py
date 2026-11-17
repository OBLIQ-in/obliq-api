"""HTML templates for the built-in developer dashboard and client documentation."""

NAVBAR_HTML = """
<nav class="border-b border-slate-800 bg-slate-900/80 backdrop-blur sticky top-0 z-40">
  <div class="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
    <div class="flex items-center justify-between h-16">
      <div class="flex items-center space-x-8">
        <a href="/dashboard/keys" class="flex items-center space-x-3">
          <div class="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center font-bold text-white shadow-lg shadow-indigo-500/30">O</div>
          <span class="font-semibold text-lg tracking-tight text-white">Obliq <span class="text-xs px-2 py-0.5 rounded bg-indigo-900/50 text-indigo-400 border border-indigo-700/50 ml-1">Portal</span></span>
        </a>
        <div class="hidden md:flex space-x-1">
          <a href="/dashboard/keys" id="nav-keys" class="px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition">API Keys</a>
          <a href="/dashboard/usage" id="nav-usage" class="px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition">Usage & Analytics</a>
          <a href="/dashboard/docs" id="nav-docs" class="px-3 py-2 rounded-md text-sm font-medium text-slate-300 hover:text-white hover:bg-slate-800 transition">Client Docs & SDK</a>
          <a href="/docs" target="_blank" class="px-3 py-2 rounded-md text-sm font-medium text-slate-400 hover:text-indigo-400 transition flex items-center">OpenAPI <svg class="w-3.5 h-3.5 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"></path></svg></a>
        </div>
      </div>
      <div class="flex items-center space-x-3">
        <button onclick="promptAuthToken()" id="auth-btn" class="text-xs px-3 py-1.5 rounded-md border border-slate-700 bg-slate-800 text-slate-300 hover:bg-slate-700 transition flex items-center">
          <span class="h-2 w-2 rounded-full bg-emerald-500 mr-2" id="auth-indicator"></span>
          <span id="auth-label">API Key / Token</span>
        </button>
      </div>
    </div>
  </div>
</nav>

<div id="offline-banner" class="hidden bg-amber-500/10 border-b border-amber-500/20 px-4 py-2 text-center text-sm text-amber-400 flex items-center justify-center">
  <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
  <span>You are offline. Key creation, rotation, and live metrics require an active network connection.</span>
</div>
"""

BASE_HEAD = """
<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - Obliq Developer Portal</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap" rel="stylesheet">
  <script src="https://cdn.tailwindcss.com"></script>
  <script>
    tailwind.config = {
      darkMode: 'class',
      theme: {
        extend: {
          fontFamily: {
            sans: ['Inter', 'sans-serif'],
            mono: ['JetBrains Mono', 'monospace'],
          }
        }
      }
    }
  </script>
  <style>
    body { font-family: 'Inter', sans-serif; }
    code, pre { font-family: 'JetBrains Mono', monospace; }
  </style>
</head>
<body class="bg-slate-950 text-slate-100 min-h-screen flex flex-col antialiased">
"""

COMMON_SCRIPTS = """
<script>
  // Auth Token Management
  function getAuthToken() {
    return localStorage.getItem('obliq_auth_token') || '';
  }

  function setAuthToken(token) {
    if (token) {
      localStorage.setItem('obliq_auth_token', token.trim());
    } else {
      localStorage.removeItem('obliq_auth_token');
    }
    updateAuthUI();
  }

  function promptAuthToken() {
    const current = getAuthToken();
    const token = prompt('Enter Bearer Token (Dashboard JWT or Admin API Key):', current);
    if (token !== null) {
      setAuthToken(token);
      location.reload();
    }
  }

  function updateAuthUI() {
    const token = getAuthToken();
    const indicator = document.getElementById('auth-indicator');
    const label = document.getElementById('auth-label');
    if (indicator && label) {
      if (token) {
        indicator.className = 'h-2 w-2 rounded-full bg-emerald-500 mr-2';
        label.innerText = 'Authenticated (' + token.slice(0, 10) + '...)';
      } else {
        indicator.className = 'h-2 w-2 rounded-full bg-amber-500 mr-2';
        label.innerText = 'Set Auth Token';
      }
    }
  }

  // Offline detection
  function checkOnlineStatus() {
    const banner = document.getElementById('offline-banner');
    if (banner) {
      if (navigator.onLine) {
        banner.classList.add('hidden');
      } else {
        banner.classList.remove('hidden');
      }
    }
  }

  window.addEventListener('online', checkOnlineStatus);
  window.addEventListener('offline', checkOnlineStatus);
  document.addEventListener('DOMContentLoaded', () => {
    checkOnlineStatus();
    updateAuthUI();
  });

  // Generic API Caller
  async function apiFetch(endpoint, options = {}) {
    const token = getAuthToken();
    const headers = {
      ...(options.headers || {})
    };
    if (token && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${token}`;
    }
    const resp = await fetch(endpoint, { ...options, headers });
    if (!resp.ok) {
      const err = await resp.json().catch(() => ({}));
      throw new Error(err.error?.message || err.detail || `Request failed (${resp.status})`);
    }
    return resp;
  }
</script>
"""

# ── Keys Page Template ───────────────────────────────────────────────────────

KEYS_PAGE_HTML = (
    BASE_HEAD.replace("{title}", "API Key Management")
    + NAVBAR_HTML
    + """
<main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-slate-800 gap-4">
    <div>
      <h1 class="text-2xl font-bold tracking-tight text-white">API Keys</h1>
      <p class="text-slate-400 text-sm mt-1">Manage API credentials, configure fine-grained scopes, and rotate production secrets.</p>
    </div>
    <div>
      <button onclick="openCreateModal()" class="inline-flex items-center px-4 py-2 border border-transparent rounded-lg shadow-sm text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-500 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500 transition shadow-indigo-600/30">
        <svg class="w-4 h-4 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"></path></svg>
        Generate New Key
      </button>
    </div>
  </div>

  <!-- Key Metrics Summary -->
  <div class="grid grid-cols-1 sm:grid-cols-3 gap-4 my-6">
    <div class="p-5 rounded-xl bg-slate-900 border border-slate-800">
      <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Active Keys</div>
      <div id="stat-active" class="text-2xl font-bold text-white mt-1">--</div>
    </div>
    <div class="p-5 rounded-xl bg-slate-900 border border-slate-800">
      <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Expiring / Grace Period</div>
      <div id="stat-expiring" class="text-2xl font-bold text-amber-400 mt-1">--</div>
    </div>
    <div class="p-5 rounded-xl bg-slate-900 border border-slate-800">
      <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Total Generated</div>
      <div id="stat-total" class="text-2xl font-bold text-slate-300 mt-1">--</div>
    </div>
  </div>

  <!-- Keys Table -->
  <div class="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-xl">
    <div class="px-6 py-4 border-b border-slate-800 flex items-center justify-between">
      <h3 class="font-semibold text-white text-sm">Configured API Keys</h3>
      <button onclick="loadKeys()" class="text-xs text-indigo-400 hover:text-indigo-300 font-medium flex items-center">
        <svg class="w-3.5 h-3.5 mr-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"></path></svg>
        Refresh
      </button>
    </div>
    <div class="overflow-x-auto">
      <table class="w-full text-left text-sm text-slate-300">
        <thead class="bg-slate-950/50 text-slate-400 text-xs uppercase font-medium border-b border-slate-800">
          <tr>
            <th class="px-6 py-3.5">Name</th>
            <th class="px-6 py-3.5">Key Prefix</th>
            <th class="px-6 py-3.5">Scopes</th>
            <th class="px-6 py-3.5">Status</th>
            <th class="px-6 py-3.5">Expires</th>
            <th class="px-6 py-3.5">Last Used</th>
            <th class="px-6 py-3.5 text-right">Actions</th>
          </tr>
        </thead>
        <tbody id="keys-tbody" class="divide-y divide-slate-800/60 font-mono text-xs">
          <tr>
            <td colspan="7" class="px-6 py-12 text-center text-slate-500 font-sans">Loading keys...</td>
          </tr>
        </tbody>
      </table>
    </div>
  </div>
</main>

<!-- Create Key Modal -->
<div id="modal-create" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
  <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl">
    <h3 class="text-lg font-bold text-white">Generate API Key</h3>
    <p class="text-slate-400 text-xs mt-1">Specify an identifier, permissions, and optional expiration.</p>

    <div class="mt-4 space-y-4 font-sans text-sm">
      <div>
        <label class="block text-xs font-medium text-slate-300 mb-1">Key Name / Description</label>
        <input type="text" id="input-key-name" placeholder="e.g. Production Next.js Client" class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-indigo-500 text-sm">
      </div>

      <div>
        <label class="block text-xs font-medium text-slate-300 mb-1.5">Scopes & Permissions</label>
        <div class="space-y-2">
          <label class="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer">
            <input type="checkbox" id="scope-ocr-write" checked class="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-indigo-500">
            <span><code>ocr:write</code> - Enqueue & upload documents for OCR</span>
          </label>
          <label class="flex items-center space-x-2 text-xs text-slate-300 cursor-pointer">
            <input type="checkbox" id="scope-ocr-read" checked class="rounded border-slate-700 bg-slate-950 text-indigo-600 focus:ring-indigo-500">
            <span><code>ocr:read</code> - Poll job status and fetch extracted text</span>
          </label>
        </div>
      </div>

      <div>
        <label class="block text-xs font-medium text-slate-300 mb-1">Expiration Presets</label>
        <select id="select-expiry" class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white focus:outline-none focus:border-indigo-500 text-sm">
          <option value="90">90 Days (Recommended)</option>
          <option value="30">30 Days</option>
          <option value="365">1 Year</option>
          <option value="">Never Expires</option>
        </select>
      </div>
    </div>

    <div class="mt-6 flex justify-end space-x-3">
      <button onclick="closeModal('modal-create')" class="px-4 py-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 text-sm">Cancel</button>
      <button onclick="submitCreateKey()" id="btn-submit-create" class="px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm">Create Key</button>
    </div>
  </div>
</div>

<!-- Reveal Secret Key Modal (Copy-Once) -->
<div id="modal-reveal" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
  <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-lg w-full p-6 shadow-2xl">
    <div class="flex items-center space-x-3 text-emerald-400">
      <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z"></path></svg>
      <h3 class="text-lg font-bold text-white">API Key Generated</h3>
    </div>
    <p class="text-slate-400 text-xs mt-2">Make sure to copy your key secret now. <strong>You will not be able to see it again!</strong></p>

    <div class="mt-4 p-3 bg-slate-950 border border-slate-800 rounded-xl relative group">
      <div id="reveal-key-text" class="font-mono text-sm text-indigo-300 break-all select-all pr-12"></div>
      <button onclick="copyRevealedKey()" class="absolute right-2 top-2 p-2 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-xs flex items-center transition" title="Copy to Clipboard">
        <svg id="copy-icon" class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 5H6a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2v-1M8 5a2 2 0 002 2h2a2 2 0 002-2M8 5a2 2 0 012-2h2a2 2 0 012 2m0 0h2a2 2 0 012 2v3m2 4H10m0 0l3-3m-3 3l3 3"></path></svg>
        <span id="copy-label" class="ml-1 text-xs">Copy</span>
      </button>
    </div>

    <div class="mt-4 p-3 bg-amber-500/10 border border-amber-500/20 rounded-lg text-xs text-amber-300 flex items-start space-x-2">
      <svg class="w-4 h-4 mt-0.5 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"></path></svg>
      <span>Store this secret securely in environment variables (e.g. <code>OBLIQ_API_KEY</code>). Never check raw API keys into Git repositories.</span>
    </div>

    <div class="mt-6 flex justify-end">
      <button onclick="closeModal('modal-reveal'); loadKeys();" class="px-5 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white font-medium text-sm">Done, I Saved It</button>
    </div>
  </div>
</div>

<!-- Rotate Modal -->
<div id="modal-rotate" class="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
  <div class="bg-slate-900 border border-slate-800 rounded-2xl max-w-md w-full p-6 shadow-2xl">
    <h3 class="text-lg font-bold text-white">Rotate API Key</h3>
    <p class="text-slate-400 text-xs mt-1">Generate a replacement key while providing a sunset window for the existing key.</p>
    <input type="hidden" id="rotate-key-id">

    <div class="mt-4 space-y-3 font-sans text-sm">
      <label class="block text-xs font-medium text-slate-300">Grace Period (Overlap Window)</label>
      <select id="select-grace" class="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500">
        <option value="24">24 Hours (Recommended for Zero Downtime)</option>
        <option value="48">48 Hours</option>
        <option value="1">1 Hour (Quick Switch)</option>
        <option value="0">Immediate Revocation (0h)</option>
      </select>
      <p class="text-xs text-slate-400">The retiring key will accept requests until the grace period expires.</p>
    </div>

    <div class="mt-6 flex justify-end space-x-3">
      <button onclick="closeModal('modal-rotate')" class="px-4 py-2 rounded-lg border border-slate-700 text-slate-300 hover:bg-slate-800 text-sm">Cancel</button>
      <button onclick="submitRotateKey()" class="px-4 py-2 rounded-lg bg-amber-600 hover:bg-amber-500 text-white font-medium text-sm">Confirm Rotation</button>
    </div>
  </div>
</div>

"""
    + COMMON_SCRIPTS
    + """
<script>
  let currentKeys = [];

  function closeModal(id) {
    document.getElementById(id).classList.add('hidden');
  }

  function openCreateModal() {
    document.getElementById('input-key-name').value = '';
    document.getElementById('modal-create').classList.remove('hidden');
  }

  function openRotateModal(keyId) {
    document.getElementById('rotate-key-id').value = keyId;
    document.getElementById('modal-rotate').classList.remove('hidden');
  }

  function copyRevealedKey() {
    const text = document.getElementById('reveal-key-text').innerText;
    navigator.clipboard.writeText(text).then(() => {
      document.getElementById('copy-label').innerText = 'Copied!';
      setTimeout(() => {
        document.getElementById('copy-label').innerText = 'Copy';
      }, 2000);
    });
  }

  async function loadKeys() {
    const tbody = document.getElementById('keys-tbody');
    try {
      const resp = await apiFetch('/v1/keys');
      const data = await resp.json();
      currentKeys = data.keys || [];
      renderKeysTable();
    } catch (err) {
      tbody.innerHTML = `<tr><td colspan="7" class="px-6 py-8 text-center text-rose-400 font-sans">${err.message}<br><button onclick="promptAuthToken()" class="mt-2 text-xs text-indigo-400 underline">Set or update Auth Bearer token</button></td></tr>`;
    }
  }

  function renderKeysTable() {
    const tbody = document.getElementById('keys-tbody');
    let active = 0, expiring = 0, total = currentKeys.length;

    if (total === 0) {
      tbody.innerHTML = `<tr><td colspan="7" class="px-6 py-12 text-center text-slate-500 font-sans">No API keys found. Click "Generate New Key" to create your first key.</td></tr>`;
      document.getElementById('stat-active').innerText = '0';
      document.getElementById('stat-expiring').innerText = '0';
      document.getElementById('stat-total').innerText = '0';
      return;
    }

    tbody.innerHTML = currentKeys.map(k => {
      if (k.status === 'active') active++;
      if (k.status === 'expiring') expiring++;

      const statusBadge = k.status === 'active' 
        ? '<span class="px-2 py-0.5 rounded text-xs bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">Active</span>'
        : k.status === 'expiring'
        ? '<span class="px-2 py-0.5 rounded text-xs bg-amber-500/10 text-amber-400 border border-amber-500/20">Expiring</span>'
        : '<span class="px-2 py-0.5 rounded text-xs bg-slate-800 text-slate-400 border border-slate-700">Revoked</span>';

      const scopesHtml = (k.scopes || []).map(s => `<span class="px-1.5 py-0.5 rounded bg-slate-800 text-slate-300 border border-slate-700 mr-1">${s}</span>`).join('');
      const expiresFormatted = k.expires_at ? new Date(k.expires_at).toLocaleDateString() : 'Never';
      const lastUsedFormatted = k.last_used_at ? new Date(k.last_used_at).toLocaleDateString() : 'Never';

      const actions = k.status !== 'revoked' ? `
        <button onclick="openRotateModal('${k.id}')" class="text-xs px-2 py-1 rounded bg-slate-800 hover:bg-slate-700 text-indigo-400 mr-1">Rotate</button>
        <button onclick="revokeKey('${k.id}')" class="text-xs px-2 py-1 rounded bg-rose-950/40 hover:bg-rose-900/60 text-rose-400 border border-rose-800/50">Revoke</button>
      ` : '<span class="text-slate-600 text-xs">None</span>';

      return `
        <tr class="hover:bg-slate-950/40 transition">
          <td class="px-6 py-3.5 font-sans font-medium text-white">${k.name}</td>
          <td class="px-6 py-3.5 text-indigo-400 font-mono">${k.key_prefix}...</td>
          <td class="px-6 py-3.5">${scopesHtml || '<span class="text-slate-500">None</span>'}</td>
          <td class="px-6 py-3.5">${statusBadge}</td>
          <td class="px-6 py-3.5 text-slate-400 font-sans">${expiresFormatted}</td>
          <td class="px-6 py-3.5 text-slate-400 font-sans">${lastUsedFormatted}</td>
          <td class="px-6 py-3.5 text-right font-sans">${actions}</td>
        </tr>
      `;
    }).join('');

    document.getElementById('stat-active').innerText = active;
    document.getElementById('stat-expiring').innerText = expiring;
    document.getElementById('stat-total').innerText = total;
  }

  async function submitCreateKey() {
    const name = document.getElementById('input-key-name').value.trim();
    if (!name) { alert('Please enter a key name.'); return; }

    const scopes = [];
    if (document.getElementById('scope-ocr-write').checked) scopes.push('ocr:write');
    if (document.getElementById('scope-ocr-read').checked) scopes.push('ocr:read');

    const expiryVal = document.getElementById('select-expiry').value;
    const expiresInDays = expiryVal ? parseInt(expiryVal, 10) : null;

    try {
      const resp = await apiFetch('/v1/keys', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, scopes, expires_in_days: expiresInDays })
      });
      const data = await resp.json();
      closeModal('modal-create');
      document.getElementById('reveal-key-text').innerText = data.key;
      document.getElementById('modal-reveal').classList.remove('hidden');
    } catch (err) {
      alert('Error creating key: ' + err.message);
    }
  }

  async function submitRotateKey() {
    const keyId = document.getElementById('rotate-key-id').value;
    const grace = parseInt(document.getElementById('select-grace').value, 10);

    try {
      const resp = await apiFetch(`/v1/keys/${keyId}/rotate`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ grace_period_hours: grace })
      });
      const data = await resp.json();
      closeModal('modal-rotate');
      document.getElementById('reveal-key-text').innerText = data.key;
      document.getElementById('modal-reveal').classList.remove('hidden');
    } catch (err) {
      alert('Error rotating key: ' + err.message);
    }
  }

  async function revokeKey(keyId) {
    if (!confirm('Are you sure you want to permanently revoke this API key? Applications using it will immediately stop working.')) return;
    try {
      await apiFetch(`/v1/keys/${keyId}/revoke`, { method: 'POST' });
      loadKeys();
    } catch (err) {
      alert('Error revoking key: ' + err.message);
    }
  }

  document.addEventListener('DOMContentLoaded', loadKeys);
</script>
</body>
</html>
"""
)

# ── Usage & Analytics Page Template ──────────────────────────────────────────

USAGE_PAGE_HTML = (
    BASE_HEAD.replace("{title}", "Usage & Analytics")
    + NAVBAR_HTML
    + """
<main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8">
  <div class="flex flex-col sm:flex-row sm:items-center justify-between pb-6 border-b border-slate-800 gap-4">
    <div>
      <h1 class="text-2xl font-bold tracking-tight text-white">Usage & Observability</h1>
      <p class="text-slate-400 text-sm mt-1">Live telemetry, request volume, error distributions, and latency percentiles.</p>
    </div>
    <div class="flex items-center space-x-3">
      <select id="select-range" onchange="loadUsage()" class="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-white text-sm focus:outline-none focus:border-indigo-500">
        <option value="7">Last 7 Days</option>
        <option value="30" selected>Last 30 Days</option>
        <option value="90">Last 90 Days</option>
      </select>
    </div>
  </div>

  <!-- KPI Overview -->
  <div class="grid grid-cols-1 sm:grid-cols-4 gap-4 my-6">
    <div class="p-5 rounded-xl bg-slate-900 border border-slate-800">
      <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Total OCR Jobs (30d)</div>
      <div id="kpi-jobs" class="text-2xl font-bold text-white mt-1">--</div>
    </div>
    <div class="p-5 rounded-xl bg-slate-900 border border-slate-800">
      <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Pages Processed</div>
      <div id="kpi-pages" class="text-2xl font-bold text-indigo-400 mt-1">--</div>
    </div>
    <div class="p-5 rounded-xl bg-slate-900 border border-slate-800">
      <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Credits Charged</div>
      <div id="kpi-credits" class="text-2xl font-bold text-slate-300 mt-1">--</div>
    </div>
    <div class="p-5 rounded-xl bg-slate-900 border border-slate-800">
      <div class="text-xs font-medium text-slate-400 uppercase tracking-wider">Failed Jobs</div>
      <div id="kpi-failed" class="text-2xl font-bold text-rose-400 mt-1">--</div>
    </div>
  </div>

  <!-- Charts -->
  <div class="grid grid-cols-1 lg:grid-cols-2 gap-6 my-6">
    <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl">
      <h3 class="text-sm font-semibold text-white mb-4">Daily Request Volume & Pages</h3>
      <div class="h-64 relative">
        <canvas id="chart-requests"></canvas>
      </div>
    </div>
    <div class="bg-slate-900 border border-slate-800 rounded-xl p-5 shadow-xl">
      <h3 class="text-sm font-semibold text-white mb-4">Hourly Traffic Trend (Recent 24h)</h3>
      <div class="h-64 relative">
        <canvas id="chart-hourly"></canvas>
      </div>
    </div>
  </div>
</main>

<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.2/dist/chart.umd.min.js"></script>
"""
    + COMMON_SCRIPTS
    + """
<script>
  let reqChart = null;
  let hourlyChart = null;

  async function loadUsage() {
    const days = document.getElementById('select-range').value;
    try {
      // 1. Summary
      const sumResp = await apiFetch('/v1/dashboard/summary');
      const sum = await sumResp.json();
      document.getElementById('kpi-jobs').innerText = sum.usage_last_30_days.jobs.toLocaleString();
      document.getElementById('kpi-pages').innerText = sum.usage_last_30_days.pages_processed.toLocaleString();
      document.getElementById('kpi-credits').innerText = sum.usage_last_30_days.credits_charged.toLocaleString();
      document.getElementById('kpi-failed').innerText = sum.usage_last_30_days.failed_jobs.toLocaleString();

      // 2. Daily Time-Series
      const dailyResp = await apiFetch(`/v1/dashboard/usage/daily?days=${days}`);
      const daily = await dailyResp.json();
      renderDailyChart(daily.days || []);

      // 3. Hourly Time-Series
      const hourlyResp = await apiFetch('/v1/dashboard/usage/hourly?hours=24');
      const hourly = await hourlyResp.json();
      renderHourlyChart(hourly.hours || []);
    } catch (err) {
      console.error('Failed to load telemetry:', err);
    }
  }

  function renderDailyChart(days) {
    const ctx = document.getElementById('chart-requests').getContext('2d');
    if (reqChart) reqChart.destroy();

    const labels = days.map(d => d.date);
    const jobs = days.map(d => d.jobs);
    const pages = days.map(d => d.pages_processed);

    reqChart = new Chart(ctx, {
      type: 'bar',
      data: {
        labels,
        datasets: [
          {
            label: 'Jobs Submitted',
            data: jobs,
            backgroundColor: 'rgba(99, 102, 241, 0.7)',
            borderColor: '#6366f1',
            borderRadius: 4
          },
          {
            label: 'Pages Extracted',
            data: pages,
            backgroundColor: 'rgba(16, 185, 129, 0.7)',
            borderColor: '#10b981',
            borderRadius: 4
          }
        ]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8' } } },
        scales: {
          x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(51, 65, 85, 0.2)' } },
          y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(51, 65, 85, 0.2)' } }
        }
      }
    });
  }

  function renderHourlyChart(hours) {
    const ctx = document.getElementById('chart-hourly').getContext('2d');
    if (hourlyChart) hourlyChart.destroy();

    const labels = hours.map(h => h.hour.slice(-5));
    const jobs = hours.map(h => h.jobs);

    hourlyChart = new Chart(ctx, {
      type: 'line',
      data: {
        labels,
        datasets: [{
          label: 'Requests / Hour',
          data: jobs,
          fill: true,
          backgroundColor: 'rgba(99, 102, 241, 0.15)',
          borderColor: '#6366f1',
          tension: 0.3,
          borderWidth: 2
        }]
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: { legend: { labels: { color: '#94a3b8' } } },
        scales: {
          x: { ticks: { color: '#64748b' }, grid: { color: 'rgba(51, 65, 85, 0.2)' } },
          y: { ticks: { color: '#64748b' }, grid: { color: 'rgba(51, 65, 85, 0.2)' } }
        }
      }
    });
  }

  document.addEventListener('DOMContentLoaded', loadUsage);
</script>
</body>
</html>
"""
)

# ── Client Docs Page Template ────────────────────────────────────────────────

DOCS_PAGE_HTML = (
    BASE_HEAD.replace("{title}", "Client SDK Documentation")
    + NAVBAR_HTML
    + """
<main class="flex-1 max-w-7xl w-full mx-auto px-4 sm:px-6 lg:px-8 py-8 font-sans">
  <div class="pb-6 border-b border-slate-800">
    <h1 class="text-2xl font-bold tracking-tight text-white">API Client SDKs & Code Examples</h1>
    <p class="text-slate-400 text-sm mt-1">Official libraries and quickstarts to integrate Obliq OCR into your frontend applications, backends, and serverless jobs.</p>
  </div>

  <!-- Language Switcher Tabs -->
  <div class="flex space-x-2 my-6 border-b border-slate-800 pb-2">
    <button onclick="switchTab('ts')" id="tab-btn-ts" class="px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 text-white transition">TypeScript / Next.js</button>
    <button onclick="switchTab('python')" id="tab-btn-python" class="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition">Python</button>
    <button onclick="switchTab('curl')" id="tab-btn-curl" class="px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition">cURL / CLI</button>
  </div>

  <!-- TypeScript Section -->
  <div id="tab-ts" class="space-y-6">
    <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h3 class="text-lg font-bold text-white mb-2">1. Installation</h3>
      <p class="text-slate-400 text-sm mb-3">Install the official isomorphic client library:</p>
      <div class="bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-sm text-indigo-300 flex justify-between items-center">
        <span>pnpm add @obliq/client</span>
        <button onclick="navigator.clipboard.writeText('pnpm add @obliq/client')" class="text-xs bg-slate-800 px-2 py-1 rounded text-slate-300 hover:bg-slate-700">Copy</button>
      </div>
    </div>

    <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h3 class="text-lg font-bold text-white mb-2">2. Document OCR in Next.js / Node.js</h3>
      <p class="text-slate-400 text-sm mb-3">Submit document, poll for completion, and extract page text:</p>
      <pre class="bg-slate-950 border border-slate-800 rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto"><code>import { ObliqClient } from "@obliq/client";
import * as fs from "node:fs/promises";

const client = new ObliqClient({
  apiKey: process.env.OBLIQ_API_KEY,
  baseUrl: "https://api.obliq.in",
});

// 1. Submit document (accepts File, Blob, Buffer, or Stream)
const fileBuffer = await fs.readFile("./invoice.pdf");
const job = await client.jobs.create({
  file: fileBuffer,
  fileName: "invoice.pdf",
});

console.log(`Job enqueued: ${job.id}`);

// 2. Poll until completed (with live progress callback)
const result = await client.jobs.poll(job.id, {
  pollIntervalMs: 1000,
  timeoutMs: 60000,
  onProgress: (status) => console.log(`Current status: ${status.status}`),
});

console.log(`Extracted ${result.page_count} pages in ${result.processing_time_ms}ms:`);
for (const page of result.pages) {
  console.log(`Page ${page.page_number}: ${page.text}`);
}</code></pre>
    </div>

    <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h3 class="text-lg font-bold text-white mb-2">3. API Key Management via SDK</h3>
      <pre class="bg-slate-950 border border-slate-800 rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto"><code>// List active workspace keys
const keys = await client.keys.list();

// Generate a new key with specific scopes and 90-day expiry
const newKey = await client.keys.create({
  name: "worker-invoice-service",
  scopes: ["ocr:read", "ocr:write"],
  expiresInDays: 90,
});
console.log(`Save your key: ${newKey.key}`);

// Zero-downtime rotation with 24-hour overlap grace period
const rotated = await client.keys.rotate(newKey.id, { gracePeriodHours: 24 });
console.log(`Rotated key: ${rotated.key}`);</code></pre>
    </div>
  </div>

  <!-- Python Section -->
  <div id="tab-python" class="space-y-6 hidden">
    <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h3 class="text-lg font-bold text-white mb-2">Python Integration (httpx / requests)</h3>
      <pre class="bg-slate-950 border border-slate-800 rounded-lg p-4 font-mono text-xs text-slate-300 overflow-x-auto"><code>import time
import httpx

API_KEY = "obliq_live_..."
BASE_URL = "https://api.obliq.in"

headers = {"Authorization": f"Bearer {API_KEY}"}

with httpx.Client(base_url=BASE_URL, timeout=30.0) as client:
    # 1. Submit Document
    with open("document.pdf", "rb") as f:
        resp = client.post("/v1/jobs", headers=headers, files={"file": ("document.pdf", f, "application/pdf")})
    resp.raise_for_status()
    job_id = resp.json()["id"]

    # 2. Poll for Completion
    while True:
        status_resp = client.get(f"/v1/jobs/{job_id}", headers=headers)
        status = status_resp.json().get("status")
        if status in ("succeeded", "failed"):
            break
        time.sleep(1.0)

    # 3. Retrieve Structured Result
    result_resp = client.get(f"/v1/jobs/{job_id}/result", headers=headers)
    result = result_resp.json()
    print(f"Extracted {result['page_count']} pages in {result.get('processing_time_ms')}ms")</code></pre>
    </div>
  </div>

  <!-- cURL Section -->
  <div id="tab-curl" class="space-y-6 hidden">
    <div class="bg-slate-900 border border-slate-800 rounded-xl p-6">
      <h3 class="text-lg font-bold text-white mb-2">cURL Commands</h3>
      <div class="space-y-4">
        <div>
          <span class="text-xs text-slate-400 font-medium">1. Submit Document:</span>
          <pre class="bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-xs text-indigo-300 mt-1 overflow-x-auto"><code>curl -X POST https://api.obliq.in/v1/jobs \\
  -H "Authorization: Bearer $OBLIQ_API_KEY" \\
  -F "file=@invoice.pdf;type=application/pdf"</code></pre>
        </div>
        <div>
          <span class="text-xs text-slate-400 font-medium">2. Check Status:</span>
          <pre class="bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-xs text-indigo-300 mt-1 overflow-x-auto"><code>curl https://api.obliq.in/v1/jobs/&lt;job_id&gt; \\
  -H "Authorization: Bearer $OBLIQ_API_KEY"</code></pre>
        </div>
        <div>
          <span class="text-xs text-slate-400 font-medium">3. Fetch Extracted Result:</span>
          <pre class="bg-slate-950 border border-slate-800 rounded-lg p-3 font-mono text-xs text-indigo-300 mt-1 overflow-x-auto"><code>curl https://api.obliq.in/v1/jobs/&lt;job_id&gt;/result \\
  -H "Authorization: Bearer $OBLIQ_API_KEY"</code></pre>
        </div>
      </div>
    </div>
  </div>
</main>
"""
    + COMMON_SCRIPTS
    + """
<script>
  function switchTab(lang) {
    ['ts', 'python', 'curl'].forEach(t => {
      document.getElementById('tab-' + t).classList.add('hidden');
      const btn = document.getElementById('tab-btn-' + t);
      btn.className = 'px-4 py-2 rounded-lg text-sm font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition';
    });
    document.getElementById('tab-' + lang).classList.remove('hidden');
    const activeBtn = document.getElementById('tab-btn-' + lang);
    activeBtn.className = 'px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 text-white transition';
  }
</script>
</body>
</html>
"""
)
