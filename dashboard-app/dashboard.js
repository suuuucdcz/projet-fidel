const API_BASE_URL = 'https://projet-fidel.onrender.com';

document.addEventListener('DOMContentLoaded', fetchAgencyData);

async function fetchAgencyData() {
    try {
        const res = await fetch(`${API_BASE_URL}/dashboard/admin/merchants`);
        const merchants = await res.json();
        
        const container = document.getElementById('merchants-list');
        container.innerHTML = '';
        
        if (merchants.length === 0) {
            container.innerHTML = '<p>Aucun commerçant trouvé.</p>';
            return;
        }

        for (const m of merchants) {
            // Fetch customers for this merchant
            const custRes = await fetch(`${API_BASE_URL}/dashboard/customers/${m.id}`);
            const customers = await custRes.json();
            
            // Fetch logs for this merchant
            const logsRes = await fetch(`${API_BASE_URL}/dashboard/admin/logs/${m.id}`);
            const logs = await logsRes.json();
            
            const card = document.createElement('div');
            card.className = 'merchant-card';
            
            // Build customers table rows
            let rows = '';
            if (customers.length === 0) {
                rows = '<tr><td colspan="4" style="text-align:center; color:gray;">Aucun client</td></tr>';
            } else {
                customers.forEach(c => {
                    const name = c.customers ? `${c.customers.first_name || ''} ${c.customers.last_name || ''}` : 'Inconnu';
                    rows += `
                        <tr>
                            <td><strong>${name}</strong></td>
                            <td><span class="badge">${c.points} pts</span></td>
                            <td style="color:gray; font-size:12px;">${new Date(c.created_at).toLocaleDateString()}</td>
                            <td><button onclick="deleteCustomer('${m.id}', '${c.customer_id}')" style="background:transparent; color:#ff4444; border:1px solid #ff4444; border-radius:4px; padding:4px 8px; cursor:pointer; font-size:11px; font-weight:bold; transition:0.2s;" onmouseover="this.style.background='#ff4444'; this.style.color='white';" onmouseout="this.style.background='transparent'; this.style.color='#ff4444';">Retirer</button></td>
                        </tr>
                    `;
                });
            }

            let logsRows = '';
            if (logs.length === 0) {
                logsRows = '<tr><td colspan="4" style="text-align:center; color:gray;">Aucun historique</td></tr>';
            } else {
                logs.forEach(l => {
                    const clientName = l.customers ? `${l.customers.first_name || ''} ${l.customers.last_name || ''}` : 'Inconnu';
                    let actionText = '';
                    let actionColor = 'gray';
                    if (l.action_type === 'SCAN') { actionText = '+1 Point'; actionColor = 'var(--primary)'; }
                    if (l.action_type === 'REWARD') { actionText = 'Récompense !'; actionColor = 'var(--success)'; }
                    if (l.action_type === 'PUSH_CAMPAIGN') { actionText = 'Push Marketing'; actionColor = 'var(--accent)'; }
                    
                    logsRows += `
                        <tr>
                            <td>${new Date(l.created_at).toLocaleString()}</td>
                            <td><span style="color: ${actionColor}; font-weight: bold;">${actionText}</span></td>
                            <td>${clientName}</td>
                        </tr>
                    `;
                });
            }

            card.innerHTML = `
                <div class="merchant-header">
                    <div>
                        <div class="merchant-title">${m.name}</div>
                        <div style="color:gray; font-size:14px;">${customers.length} clients</div>
                    </div>
                    <div style="display:flex; gap:10px; align-items:center;">
                        <a href="https://api.qrserver.com/v1/create-qr-code/?size=500x500&data=${encodeURIComponent('https://suuuucdcz.github.io/projet-fidel/public/signup.html?merchant_id=' + m.id)}" target="_blank" style="background:transparent; color: var(--primary); border: 1px solid var(--primary); padding:4px 8px; border-radius:4px; cursor:pointer; font-size:11px; font-weight:bold; text-decoration:none; transition: 0.2s; white-space: nowrap;" onmouseover="this.style.background='var(--primary)'; this.style.color='black';" onmouseout="this.style.background='transparent'; this.style.color='var(--primary)';">QR Code Inscription</a>
                        <button onclick="deleteMerchant('${m.id}')" style="background:transparent; color: #ff4444; border: 1px solid #ff4444; padding:4px 8px; border-radius:4px; cursor:pointer; font-size:11px; font-weight:bold; transition: 0.2s; white-space: nowrap; width: max-content;" onmouseover="this.style.background='#ff4444'; this.style.color='white';" onmouseout="this.style.background='transparent'; this.style.color='#ff4444';">Supprimer</button>
                    </div>
                </div>
                
                <form class="offer-form" onsubmit="updateOffer(event, '${m.id}')">
                    <div style="flex:1;">
                        <label style="font-size:12px; color:gray;">Seuil (Points)</label>
                        <input type="number" id="thresh_${m.id}" value="${m.reward_threshold}" required>
                    </div>
                    <div style="flex:2;">
                        <label style="font-size:12px; color:gray;">Récompense</label>
                        <input type="text" id="desc_${m.id}" value="${m.reward_description}" required>
                    </div>
                    <div style="display:flex; align-items:flex-end;">
                        <button type="submit" class="btn-accent">Sauvegarder l'offre</button>
                    </div>
                </form>

                <div style="display:flex; gap: 20px; margin-top: 15px;">
                    <div style="flex: 1; background: rgba(0,0,0,0.2); border-radius: 8px; overflow:hidden;">
                        <div style="padding: 10px; background: rgba(0,0,0,0.3); font-weight: bold; font-size: 14px;">Clients (${customers.length})</div>
                        <table>
                            <thead>
                                <tr><th>Client</th><th>Points</th><th>Inscrit le</th><th>Action</th></tr>
                            </thead>
                            <tbody>${rows}</tbody>
                        </table>
                    </div>
                    
                    <div style="flex: 1; background: rgba(0,0,0,0.2); border-radius: 8px; overflow:hidden; max-height: 300px; overflow-y: auto;">
                        <div style="padding: 10px; background: rgba(0,0,0,0.3); font-weight: bold; font-size: 14px;">Historique Récent</div>
                        <table>
                            <thead>
                                <tr><th>Date</th><th>Action</th><th>Client</th></tr>
                            </thead>
                            <tbody>${logsRows}</tbody>
                        </table>
                    </div>
                </div>
            `;
            container.appendChild(card);
        }
    } catch (e) {
        console.error(e);
        document.getElementById('merchants-list').innerHTML = '<p style="color:red;">Erreur de chargement</p>';
    }
}

window.updateOffer = async function(e, merchantId) {
    e.preventDefault();
    const threshold = document.getElementById(`thresh_${merchantId}`).value;
    const desc = document.getElementById(`desc_${merchantId}`).value;
    const btn = e.target.querySelector('button');
    
    btn.innerText = "Sauvegarde...";
    try {
        const res = await fetch(`${API_BASE_URL}/dashboard/admin/update_offer`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                merchant_id: merchantId,
                reward_threshold: parseInt(threshold),
                reward_description: desc
            })
        });
        if (!res.ok) throw new Error("Erreur");
        btn.innerText = "Sauvegardé !";
        btn.style.background = "var(--success)";
        setTimeout(() => {
            btn.innerText = "Sauvegarder l'offre";
            btn.style.background = "";
        }, 2000);
    } catch (err) {
        alert("Erreur lors de la mise à jour");
        btn.innerText = "Sauvegarder l'offre";
    }
}

// Handle Merchant Creation
document.getElementById('create-merchant-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const name = document.getElementById('new_merchant_name').value;
    const email = document.getElementById('new_merchant_email').value;
    const password = document.getElementById('new_merchant_password').value;
    
    const btn = e.target.querySelector('button');
    const msg = document.getElementById('create-msg');
    const errorMsg = document.getElementById('create-error');
    
    btn.disabled = true;
    btn.innerText = "Création...";
    msg.style.display = 'none';
    errorMsg.style.display = 'none';
    
    try {
        const res = await fetch(`${API_BASE_URL}/dashboard/admin/merchants/create`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ name, email, password })
        });
        
        const data = await res.json();
        
        if (!res.ok) throw new Error(data.detail || "Erreur de création");
        
        msg.style.display = 'block';
        e.target.reset();
        
        // Reload list
        fetchAgencyData();
        
        setTimeout(() => { msg.style.display = 'none'; }, 3000);
    } catch (err) {
        errorMsg.innerText = err.message;
        errorMsg.style.display = 'block';
    } finally {
        btn.disabled = false;
        btn.innerText = "Créer le compte";
    }
});

// Handle Customer Deletion
window.deleteCustomer = async function(merchantId, customerId) {
    if (!confirm("Voulez-vous vraiment retirer cette carte de fidélité pour ce client ?")) return;
    
    try {
        const res = await fetch(`${API_BASE_URL}/dashboard/admin/customers/${merchantId}/${customerId}`, {
            method: 'DELETE'
        });
        if (!res.ok) throw new Error("Erreur lors de la suppression du client");
        fetchAgencyData(); // Refresh UI
    } catch (err) {
        alert(err.message);
    }
}

// Handle Merchant Deletion
window.deleteMerchant = async function(merchantId) {
    if (!confirm("ATTENTION : Êtes-vous sûr de vouloir supprimer définitivement cette boutique, tous ses historiques, et TOUTES les cartes de fidélité de ses clients ?")) return;
    
    try {
        const res = await fetch(`${API_BASE_URL}/dashboard/admin/merchants/${merchantId}`, {
            method: 'DELETE'
        });
        if (!res.ok) throw new Error("Erreur lors de la suppression de la boutique");
        fetchAgencyData(); // Refresh UI
    } catch (err) {
        alert(err.message);
    }
}
