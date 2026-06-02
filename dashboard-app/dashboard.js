const API_BASE_URL = 'http://localhost:8000';

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
            
            const card = document.createElement('div');
            card.className = 'merchant-card';
            
            // Build customers table rows
            let rows = '';
            if (customers.length === 0) {
                rows = '<tr><td colspan="3" style="text-align:center; color:gray;">Aucun client</td></tr>';
            } else {
                customers.forEach(c => {
                    const name = c.customers ? `${c.customers.first_name || ''} ${c.customers.last_name || ''}` : 'Inconnu';
                    rows += `
                        <tr>
                            <td><strong>${name}</strong></td>
                            <td><span class="badge">${c.points} pts</span></td>
                            <td style="color:gray; font-size:12px;">${new Date(c.created_at).toLocaleDateString()}</td>
                        </tr>
                    `;
                });
            }

            card.innerHTML = `
                <div class="merchant-header">
                    <div class="merchant-title">${m.name}</div>
                    <div style="color:gray; font-size:14px;">${customers.length} clients</div>
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

                <div style="margin-top: 15px; background: rgba(0,0,0,0.2); border-radius: 8px; overflow:hidden;">
                    <table>
                        <thead>
                            <tr><th>Client</th><th>Points Actuels</th><th>Inscrit le</th></tr>
                        </thead>
                        <tbody>${rows}</tbody>
                    </table>
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
