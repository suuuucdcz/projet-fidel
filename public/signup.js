const API_BASE_URL = 'http://localhost:8000'; // Change in prod

// Parse merchant_id from URL: signup.html?merchant_id=xxx
const urlParams = new URLSearchParams(window.location.search);
let merchantId = urlParams.get('merchant_id');

// For local testing, fallback to the dummy merchant ID if missing
if (!merchantId) {
    merchantId = '9d3a9145-e190-4cae-b278-006bb54dd602'; // Change this to your real test ID
    console.log("No merchant_id in URL, using fallback test ID:", merchantId);
}

document.getElementById('signup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const firstName = document.getElementById('first-name').value;
    const lastName = document.getElementById('last-name').value;
    const btn = document.getElementById('submit-btn');
    
    btn.disabled = true;
    btn.innerText = "Création en cours...";

    try {
        const response = await fetch(`${API_BASE_URL}/cards/generate/${merchantId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ first_name: firstName, last_name: lastName })
        });

        if (!response.ok) throw new Error('Erreur lors de la création');
        
        const data = await response.json();
        
        // Hide form, show link
        document.getElementById('signup-form').classList.add('hidden');
        const successArea = document.getElementById('success-area');
        successArea.classList.remove('hidden');
        
        // Update link
        document.getElementById('wallet-link').href = data.wallet_link;
        
    } catch (error) {
        alert("Erreur: " + error.message);
        btn.disabled = false;
        btn.innerText = "Générer ma carte";
    }
});
