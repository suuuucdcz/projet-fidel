const API_BASE_URL = 'https://projet-fidel.onrender.com'; // Change in prod

// Parse merchant_id from URL: signup.html?merchant_id=xxx
const urlParams = new URLSearchParams(window.location.search);
let merchantId = urlParams.get('merchant_id');

// For local testing, fallback to the dummy merchant ID if missing
if (!merchantId) {
    merchantId = '9d3a9145-e190-4cae-b278-006bb54dd602';
}

let mode = 'signup';

function switchTab(newMode) {
    mode = newMode;
    document.getElementById('tab-signup').classList.remove('active');
    document.getElementById('tab-login').classList.remove('active');
    document.getElementById(`tab-${mode}`).classList.add('active');
    
    document.getElementById('error-message').style.display = 'none';
    
    if (mode === 'signup') {
        document.getElementById('pin-label').innerText = "Choisissez un Code PIN (4 chiffres)";
        document.getElementById('submit-btn').innerText = "Créer ma carte";
    } else {
        document.getElementById('pin-label').innerText = "Votre Code PIN Secret";
        document.getElementById('submit-btn').innerText = "Retrouver ma carte";
    }
}
window.switchTab = switchTab;
switchTab('signup'); // init

document.getElementById('signup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const firstName = document.getElementById('first-name').value;
    const lastName = document.getElementById('last-name').value;
    const pinCode = document.getElementById('pin-code').value;
    const btn = document.getElementById('submit-btn');
    const errorMsg = document.getElementById('error-message');
    
    btn.disabled = true;
    btn.innerText = "Patientez...";
    errorMsg.style.display = 'none';

    try {
        const response = await fetch(`${API_BASE_URL}/cards/generate/${merchantId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                first_name: firstName, 
                last_name: lastName, 
                pin_code: pinCode,
                action: mode 
            })
        });

        if (!response.ok) {
            const data = await response.json();
            throw new Error(data.detail || 'Erreur lors de la création');
        }
        
        const data = await response.json();
        
        // Hide form, show link
        document.getElementById('signup-form').classList.add('hidden');
        document.querySelector('.tabs').classList.add('hidden');
        document.querySelector('h1').innerText = "Félicitations !";
        
        const successArea = document.getElementById('success-area');
        successArea.classList.remove('hidden');
        
        // Update link
        document.getElementById('wallet-link').href = data.wallet_link;
        
    } catch (error) {
        errorMsg.innerText = error.message;
        errorMsg.style.display = 'block';
        btn.disabled = false;
        btn.innerText = mode === 'signup' ? "Créer ma carte" : "Retrouver ma carte";
    }
});
