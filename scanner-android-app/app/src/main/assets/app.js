const API_BASE_URL = 'https://projet-fidel.onrender.com'; // IP pour le test via APK/Téléphone
let currentMerchantId = localStorage.getItem('merchant_id');
let html5QrcodeScanner = null;

// DOM Elements
const loginSection = document.getElementById('login-section');
const scannerSection = document.getElementById('scanner-section');
const pushSection = document.getElementById('push-section');
const bottomNav = document.getElementById('bottom-nav');
const readerDiv = document.getElementById('reader');
const resultCard = document.getElementById('scan-result');
const pointsStatus = document.getElementById('points-status');

// Init
document.addEventListener('DOMContentLoaded', () => {
    if (currentMerchantId) {
        showScanner();
    } else {
        loginSection.classList.remove('hidden');
    }
});

// Navigation
document.getElementById('nav-scanner').addEventListener('click', () => {
    document.getElementById('nav-scanner').classList.add('active');
    document.getElementById('nav-push').classList.remove('active');
    scannerSection.classList.remove('hidden');
    pushSection.classList.add('hidden');
    if (!html5QrcodeScanner) startScanner();
});

document.getElementById('nav-push').addEventListener('click', () => {
    document.getElementById('nav-push').classList.add('active');
    document.getElementById('nav-scanner').classList.remove('active');
    pushSection.classList.remove('hidden');
    scannerSection.classList.add('hidden');
    stopScanner();
});

// Login Form
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
        localStorage.setItem('merchant_id', currentMerchantId);
        
        showScanner();
    } catch (error) {
        errorDiv.innerText = error.message;
        errorDiv.classList.remove('hidden');
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
});

// Logout
document.getElementById('logout-btn').addEventListener('click', () => {
    localStorage.removeItem('merchant_id');
    currentMerchantId = null;
    stopScanner();
    scannerSection.classList.add('hidden');
    bottomNav.classList.add('hidden');
    loginSection.classList.remove('hidden');
});

// Scanner Logic
function showScanner() {
    loginSection.classList.add('hidden');
    scannerSection.classList.remove('hidden');
    bottomNav.classList.remove('hidden');
    startScanner();
}

function startScanner() {
    readerDiv.classList.remove('hidden');
    resultCard.classList.add('hidden');
    
    if (html5QrcodeScanner) return;

    html5QrcodeScanner = new Html5QrcodeScanner(
        "reader", { fps: 10, qrbox: {width: 250, height: 250}, aspectRatio: 1.0 }
    );
    html5QrcodeScanner.render(onScanSuccess, onScanFailure);
}

function stopScanner() {
    if (html5QrcodeScanner) {
        html5QrcodeScanner.clear().then(() => {
            html5QrcodeScanner = null;
        });
    }
}

async function onScanSuccess(decodedText, decodedResult) {
    // Stop scanning once we get a code
    stopScanner();
    readerDiv.classList.add('hidden');
    
    // Call API to validate point
    try {
        const response = await fetch(`${API_BASE_URL}/cards/scan`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                customer_id: decodedText, 
                merchant_id: currentMerchantId 
            })
        });
        
        if (!response.ok) throw new Error('Erreur lors du scan');
        
        const data = await response.json();
        pointsStatus.innerText = `Nouveau solde: ${data.new_points} points`;
        resultCard.classList.remove('hidden');
        
    } catch (error) {
        alert(error.message);
        startScanner();
    }
}

function onScanFailure(error) {
    // handle scan failure, usually better to ignore and keep scanning
}

document.getElementById('next-scan-btn').addEventListener('click', () => {
    startScanner();
});

// Push Marketing Form
document.getElementById('push-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const header = document.getElementById('push-header').value;
    const body = document.getElementById('push-body').value;
    const btn = e.target.querySelector('button');
    
    const originalText = btn.innerText;
    btn.innerText = 'Envoi en cours...';
    btn.disabled = true;

    try {
        const response = await fetch(`${API_BASE_URL}/marketing/push`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ merchant_id: currentMerchantId, header, body })
        });

        if (!response.ok) throw new Error('Erreur lors de l\'envoi');
        
        const data = await response.json();
        alert(`Campagne envoyée avec succès à ${data.sent} clients !`);
        e.target.reset();
    } catch (error) {
        alert(error.message);
    } finally {
        btn.innerText = originalText;
        btn.disabled = false;
    }
});

// PWA Service Worker Registration (Dummy for MVP)
if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
        // navigator.serviceWorker.register('/sw.js');
    });
}
