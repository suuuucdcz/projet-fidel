const API_BASE_URL = 'https://projet-fidel.onrender.com';
let currentMerchantId = localStorage.getItem('merchant_id');
let sessionToken = localStorage.getItem('access_token');
let html5QrCode = null;
let merchantLoyaltyType = 'points';   // loaded after login; drives the scan flow
let currentCustomerId = null;         // customer of the card currently on screen (cashback)

// ==========================================
// DOM Elements
// ==========================================
const loginSection = document.getElementById('login-section');
const scannerSection = document.getElementById('scanner-section');
const pushSection = document.getElementById('push-section');
const settingsSection = document.getElementById('settings-section');
const bottomNav = document.getElementById('bottom-nav');
const readerDiv = document.getElementById('reader');
const resultCard = document.getElementById('scan-result');
const pointsStatus = document.getElementById('points-status');
const cashbackPanel = document.getElementById('cashback-panel');

// ==========================================
// Authenticated requests (merchant session token)
// ==========================================
// Sends the session JWT as a Bearer header. On 401 (missing/expired token) the
// merchant is logged out and sent back to the login screen.
async function authFetch(url, options = {}) {
    const headers = { ...(options.headers || {}), 'Authorization': `Bearer ${sessionToken || ''}` };
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
        forceLogout();
        throw new Error('Session expirée. Veuillez vous reconnecter.');
    }
    return res;
}

function forceLogout() {
    localStorage.removeItem('merchant_id');
    localStorage.removeItem('access_token');
    currentMerchantId = null;
    sessionToken = null;
    stopScanner();
    scannerSection.classList.add('hidden');
    pushSection.classList.add('hidden');
    if (settingsSection) settingsSection.classList.add('hidden');
    bottomNav.classList.add('hidden');
    loginSection.classList.remove('hidden');
}

// ==========================================
// Initialization & Navigation
// ==========================================
document.addEventListener('DOMContentLoaded', () => {
    if (currentMerchantId && sessionToken) {
        showScanner();
    } else {
        loginSection.classList.remove('hidden');
    }
});

function switchTab(activeTabId, activeSection) {
    // Reset tabs
    ['nav-scanner', 'nav-push', 'nav-settings'].forEach(id => document.getElementById(id).classList.remove('active'));
    ['scanner-section', 'push-section', 'settings-section'].forEach(id => document.getElementById(id).classList.add('hidden'));
    
    // Set active
    document.getElementById(activeTabId).classList.add('active');
    activeSection.classList.remove('hidden');
    
    // Manage scanner state
    if (activeTabId === 'nav-scanner') {
        startScanner();
    } else {
        stopScanner();
    }
}

document.getElementById('nav-scanner').addEventListener('click', () => switchTab('nav-scanner', scannerSection));
document.getElementById('nav-push').addEventListener('click', () => switchTab('nav-push', pushSection));
document.getElementById('nav-settings').addEventListener('click', () => {
    switchTab('nav-settings', settingsSection);
    loadSettings();
});

// ==========================================
// Authentication
// ==========================================
document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const email = document.getElementById('email').value;
    const password = document.getElementById('password').value;
    const errorDiv = document.getElementById('login-error');
    const btn = e.target.querySelector('button');
    
    errorDiv.classList.add('hidden');
    const originalText = btn.innerText;
    btn.innerText = 'Connexion...';
    btn.disabled = true;

    try {
        const response = await fetch(`${API_BASE_URL}/merchants/login`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ email, password })
        });

        if (!response.ok) throw new Error('Identifiants incorrects');
        
        const data = await response.json();
        currentMerchantId = data.merchant_id;
        sessionToken = data.access_token;
        localStorage.setItem('merchant_id', currentMerchantId);
        localStorage.setItem('access_token', sessionToken);

        showScanner();
    } catch (error) {
        errorDiv.innerText = error.message;
        errorDiv.classList.remove('hidden');
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
});

document.getElementById('logout-btn').addEventListener('click', forceLogout);

// ==========================================
// Scanner Logic
// ==========================================
function showScanner() {
    loginSection.classList.add('hidden');
    scannerSection.classList.remove('hidden');
    pushSection.classList.add('hidden');
    if (settingsSection) settingsSection.classList.add('hidden');
    bottomNav.classList.remove('hidden');
    loadMerchantType();
    startScanner();
}

// Load the merchant's loyalty type so the scan flow can branch (cashback vs points).
// Uses the public settings endpoint (no token needed) — read-only display info.
async function loadMerchantType() {
    try {
        const res = await fetch(`${API_BASE_URL}/merchants/settings/${currentMerchantId}`);
        if (res.ok) {
            const data = await res.json();
            merchantLoyaltyType = data.loyalty_type || 'points';
        }
    } catch (e) {
        console.error('Failed to load merchant type', e);
    }
}

// Guards against overlapping start/stop transitions, which otherwise leave the
// html5-qrcode instance in a broken state (frozen / black preview).
let scannerBusy = false;

async function startScanner() {
    readerDiv.classList.remove('hidden');
    resultCard.classList.add('hidden');
    if (cashbackPanel) cashbackPanel.classList.add('hidden');

    if (!html5QrCode) {
        html5QrCode = new Html5Qrcode("reader");
    }

    if (scannerBusy || html5QrCode.isScanning) return;

    scannerBusy = true;
    try {
        await html5QrCode.start(
            { facingMode: "environment" }, // Prefer back camera
            { fps: 10, qrbox: { width: 250, height: 250 }, aspectRatio: 1.0 },
            onScanSuccess,
            onScanFailure
        );
    } catch (err) {
        console.error("Camera start failed, trying fallback: ", err);
        // Fallback for laptops with no back camera
        try {
            await html5QrCode.start(
                0,
                { fps: 10, qrbox: { width: 250, height: 250 } },
                onScanSuccess,
                () => {} // ignore fallback scan errors
            );
        } catch (e) {
            console.error("Total camera failure:", e);
        }
    } finally {
        scannerBusy = false;
    }
}

async function stopScanner() {
    if (!html5QrCode || scannerBusy || !html5QrCode.isScanning) return;
    scannerBusy = true;
    try {
        await html5QrCode.stop();
    } catch (err) {
        console.error("Error stopping scanner:", err);
    } finally {
        scannerBusy = false;
    }
}

// Recovery: when a tablet sleeps or the app is backgrounded, the OS kills the camera
// track but html5-qrcode still reports isScanning === true, so the preview stays
// black forever. On returning to the foreground (on the scanner screen), force a
// clean stop + restart so the camera comes back.
async function restartScanner() {
    if (scannerBusy) return;
    if (html5QrCode && html5QrCode.isScanning) {
        scannerBusy = true;
        try {
            await html5QrCode.stop();
        } catch (e) {
            // Track may already be dead — ignore and start fresh.
        } finally {
            scannerBusy = false;
        }
    }
    startScanner();
}

document.addEventListener('visibilitychange', () => {
    if (document.visibilityState !== 'visible') return;
    // Only act when the scanner screen is actually showing.
    if (!scannerSection || scannerSection.classList.contains('hidden')) return;
    restartScanner();
});

async function onScanSuccess(decodedText, decodedResult) {
    await stopScanner();
    readerDiv.classList.add('hidden');

    if (merchantLoyaltyType === 'cashback') {
        await showCashbackPanel(decodedText);
    } else {
        await doPointScan(decodedText);
    }
}

async function doPointScan(customerId) {
    try {
        const response = await authFetch(`${API_BASE_URL}/cards/scan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ customer_id: customerId })
        });

        if (!response.ok) throw new Error('Erreur lors du scan (carte introuvable ou erreur serveur)');

        const data = await response.json();

        if (data.reward_triggered) {
            pointsStatus.innerText = `Récompense débloquée ! (${data.reward_desc})`;
            pointsStatus.style.color = "var(--success)";
            pointsStatus.style.fontWeight = "bold";
        } else {
            pointsStatus.innerText = `Nouveau solde: ${data.new_points} points`;
            pointsStatus.style.color = "var(--text-muted)";
            pointsStatus.style.fontWeight = "normal";
        }

        resultCard.classList.remove('hidden');
    } catch (error) {
        alert(error.message);
        startScanner();
    }
}

// ==========================================
// Cashback flow
// ==========================================
const fmtEur = (v) => `${Number(v || 0).toFixed(2).replace('.', ',')} €`;

async function showCashbackPanel(customerId) {
    currentCustomerId = customerId;
    const balanceEl = document.getElementById('cashback-balance');
    const msgEl = document.getElementById('cashback-msg');
    const amountEl = document.getElementById('cashback-amount');
    if (msgEl) msgEl.innerText = '';
    if (amountEl) amountEl.value = '';
    if (balanceEl) balanceEl.innerText = 'Cagnotte : …';

    cashbackPanel.classList.remove('hidden');

    try {
        const res = await authFetch(`${API_BASE_URL}/cards/info/${encodeURIComponent(customerId)}`);
        if (!res.ok) throw new Error('Carte introuvable');
        const data = await res.json();
        if (balanceEl) balanceEl.innerText = `Cagnotte actuelle : ${fmtEur(data.balance)}`;
    } catch (error) {
        if (balanceEl) balanceEl.innerText = 'Cagnotte : (indisponible)';
    }
}

async function sendCashback(operation, amount) {
    const msgEl = document.getElementById('cashback-msg');
    const balanceEl = document.getElementById('cashback-balance');
    try {
        const res = await authFetch(`${API_BASE_URL}/cards/cashback`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ customer_id: currentCustomerId, amount, operation })
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.detail || 'Erreur cashback');

        if (balanceEl) balanceEl.innerText = `Cagnotte actuelle : ${fmtEur(data.balance)}`;
        if (msgEl) {
            msgEl.style.color = 'var(--success)';
            msgEl.innerText = operation === 'earn'
                ? `+${fmtEur(data.earned)} crédités 🎉`
                : `-${fmtEur(data.redeemed)} utilisés ✅`;
        }
        document.getElementById('cashback-amount').value = '';
    } catch (error) {
        if (msgEl) { msgEl.style.color = 'var(--danger, #ff5252)'; msgEl.innerText = error.message; }
    }
}

if (cashbackPanel) {
    document.getElementById('cashback-earn-btn').addEventListener('click', () => {
        const amount = parseFloat(document.getElementById('cashback-amount').value);
        if (!amount || amount <= 0) { alert("Saisis le montant de l'achat."); return; }
        sendCashback('earn', amount);
    });

    document.getElementById('cashback-redeem-btn').addEventListener('click', () => {
        const amount = parseFloat(document.getElementById('cashback-amount').value);
        if (!amount || amount <= 0) { alert('Saisis le montant à utiliser depuis la cagnotte.'); return; }
        sendCashback('redeem', amount);
    });

    document.getElementById('cashback-next-btn').addEventListener('click', () => {
        cashbackPanel.classList.add('hidden');
        startScanner();
    });
}

function onScanFailure(error) {
    // Ignore frame errors to avoid spamming console
}

document.getElementById('next-scan-btn').addEventListener('click', () => {
    startScanner();
});

// ==========================================
// Marketing Push Logic
// ==========================================
document.getElementById('push-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const header = document.getElementById('push-header').value;
    const body = document.getElementById('push-body').value;
    const btn = e.target.querySelector('button');
    
    const originalText = btn.innerText;
    btn.innerText = 'Envoi en cours...';
    btn.disabled = true;

    try {
        const response = await authFetch(`${API_BASE_URL}/marketing/push`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ header, body })
        });

        if (!response.ok) throw new Error('Erreur lors de l\'envoi de la campagne');
        
        const data = await response.json();
        let msg = `Campagne envoyée à ${data.sent} client(s).`;
        if (data.failed) msg += ` ${data.failed} échec(s) (cartes non ajoutées au Wallet ?).`;
        alert(msg);
        e.target.reset();
    } catch (error) {
        alert(error.message);
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
});

// ==========================================
// Settings Logic
// ==========================================
async function loadSettings() {
    try {
        const response = await fetch(`${API_BASE_URL}/merchants/settings/${currentMerchantId}`);
        if (!response.ok) throw new Error('Erreur de chargement des paramètres');
        const data = await response.json();
        document.getElementById('settings-threshold').value = data.reward_threshold;
        document.getElementById('settings-reward').value = data.reward_description;
    } catch (error) {
        console.error("Erreur Settings:", error);
    }
}

document.getElementById('settings-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const threshold = parseInt(document.getElementById('settings-threshold').value);
    const reward = document.getElementById('settings-reward').value;
    const btn = document.getElementById('settings-submit-btn');
    const msg = document.getElementById('settings-msg');
    
    btn.disabled = true;
    btn.innerText = 'Sauvegarde...';
    msg.classList.add('hidden');

    try {
        const response = await authFetch(`${API_BASE_URL}/merchants/settings`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reward_threshold: threshold, reward_description: reward })
        });

        if (!response.ok) throw new Error('Erreur lors de la sauvegarde');
        
        msg.classList.remove('hidden');
        setTimeout(() => msg.classList.add('hidden'), 3000);
    } catch (error) {
        alert(error.message);
    } finally {
        btn.disabled = false;
        btn.innerText = 'Sauvegarder';
    }
});

// PWA Service Worker Registration (relative path so it works on any host/sub-path).
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        navigator.serviceWorker.register('./sw.js').catch((err) => {
            console.error('Service worker registration failed:', err);
        });
    });
}
