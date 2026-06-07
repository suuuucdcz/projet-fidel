const API_BASE_URL = 'https://projet-fidel.onrender.com';

document.addEventListener('DOMContentLoaded', fetchAgencyData);

// ==========================================
// Security helper
// ==========================================
// All merchant- and customer-controlled values (names, reward text, image URLs)
// are injected into innerHTML below. Escape them to prevent stored XSS.
function escapeHtml(value) {
    return String(value ?? '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

// Short explanation shown under the loyalty-type selector.
const LOYALTY_DESC = {
    points: 'X passages = 1 récompense, puis remise à zéro.',
    stamps: 'Même mécanique que les points, mais affiché « Tampons » sur la carte (ex : 10 tampons = 1 offert).',
    tiers: 'Plusieurs récompenses à différents paliers ; remise à zéro au dernier palier.',
    cashback: 'X % du montant dépensé est crédité dans une cagnotte en €.'
};

// Pick black or white text for readability over a given background colour.
function contrastText(hex) {
    const h = String(hex || '').replace('#', '');
    if (h.length !== 6) return '#ffffff';
    const r = parseInt(h.slice(0, 2), 16), g = parseInt(h.slice(2, 4), 16), b = parseInt(h.slice(4, 6), 16);
    const lum = (0.299 * r + 0.587 * g + 0.114 * b) / 255;
    return lum > 0.6 ? '#111111' : '#ffffff';
}

// Live card preview: re-read the design inputs and update the mock Wallet card.
window.updateCardPreview = function (merchantId) {
    const card = document.getElementById(`cp-card_${merchantId}`);
    if (!card) return;
    const val = (p) => { const el = document.getElementById(`${p}_${merchantId}`); return el ? el.value.trim() : ''; };
    const setText = (id, t) => { const el = document.getElementById(id); if (el) el.textContent = t; };

    const color = val('color') || '#FF9800';
    card.style.background = color;
    card.style.color = contrastText(color);

    setText(`cp-program_${merchantId}`, val('program') || card.dataset.name || '');
    setText(`cp-header_${merchantId}`, '120 ' + (val('plabel') || 'Points'));

    const logo = document.getElementById(`cp-logo_${merchantId}`);
    const logoUrl = val('logo');
    if (logo) {
        if (logoUrl) { logo.src = logoUrl; logo.style.display = ''; }
        else { logo.removeAttribute('src'); logo.style.display = 'none'; }
    }

    const heroWrap = document.getElementById(`cp-hero-wrap_${merchantId}`);
    const hero = document.getElementById(`cp-hero_${merchantId}`);
    const heroUrl = val('hero');
    if (heroWrap && hero) {
        if (heroUrl) { hero.src = heroUrl; heroWrap.style.display = ''; }
        else { heroWrap.style.display = 'none'; }
    }
};

// Test an image URL the way Google will (it must publicly fetch the file). Shows a
// ✓ / ⚠ status next to the field so a bad link is obvious BEFORE saving.
window.checkImageStatus = function (merchantId, kind) {
    const input = document.getElementById(`${kind}_${merchantId}`);
    const status = document.getElementById(`${kind}-status_${merchantId}`);
    if (!input || !status) return;
    const url = input.value.trim();
    if (!url) { status.textContent = ''; return; }
    if (!/^https:\/\//i.test(url)) {
        status.textContent = '⚠ doit commencer par https://';
        status.style.color = '#ff5252';
        return;
    }
    status.textContent = '⏳ vérification…';
    status.style.color = 'var(--text-muted)';
    const img = new Image();
    img.onload = () => { status.textContent = '✓ image valide'; status.style.color = 'var(--success)'; };
    img.onerror = () => { status.textContent = '⚠ lien invalide ou image inaccessible (Google ne pourra pas la charger)'; status.style.color = '#ff5252'; };
    img.src = url;
};

// ==========================================
// Admin authentication (minimal shared-secret guard)
// ==========================================
// The backend protects /dashboard/admin/* with an X-Admin-Token header that must
// match its ADMIN_TOKEN env var. We ask for it once and keep it in localStorage.
function getAdminToken() {
    let token = localStorage.getItem('admin_token');
    if (!token) {
        token = prompt('Mot de passe administrateur (agence) :') || '';
        if (token) localStorage.setItem('admin_token', token);
    }
    return token;
}

async function adminFetch(url, options = {}) {
    const headers = { ...(options.headers || {}), 'X-Admin-Token': getAdminToken() };
    const res = await fetch(url, { ...options, headers });
    if (res.status === 401) {
        // Wrong/expired secret — forget it so the next call prompts again.
        localStorage.removeItem('admin_token');
        throw new Error('Accès refusé : mot de passe administrateur invalide.');
    }
    return res;
}

// ==========================================
// API Calls
// ==========================================

async function fetchAgencyData() {
    try {
        const res = await adminFetch(`${API_BASE_URL}/dashboard/admin/merchants`);
        const merchants = await res.json();
        
        const container = document.getElementById('merchants-list');
        container.innerHTML = '';
        
        if (merchants.length === 0) {
            container.innerHTML = '<p>Aucun commerçant trouvé.</p>';
            return;
        }

        // Fetch every merchant's customers + logs concurrently instead of
        // sequentially (was an N+1 waterfall that got slow with many merchants).
        const details = await Promise.all(merchants.map(async (m) => {
            const [custRes, logsRes] = await Promise.all([
                fetch(`${API_BASE_URL}/dashboard/customers/${m.id}`),
                adminFetch(`${API_BASE_URL}/dashboard/admin/logs/${m.id}`),
            ]);
            return { m, customers: await custRes.json(), logs: await logsRes.json() };
        }));

        for (const { m, customers, logs } of details) {
            const card = document.createElement('div');
            card.className = 'merchant-card';

            const rows = buildCustomersTableRows(m.id, customers, m.loyalty_type);
            const logsRows = buildLogsTableRows(logs);

            card.innerHTML = buildMerchantCardHTML(m, customers.length, rows, logsRows);
            container.appendChild(card);
            // Check existing image URLs so a broken logo/banner is flagged immediately.
            checkImageStatus(m.id, 'logo');
            checkImageStatus(m.id, 'hero');
        }
    } catch (e) {
        console.error(e);
        document.getElementById('merchants-list').innerHTML = '<p style="color:red;">Erreur de chargement</p>';
    }
}

// ==========================================
// HTML Templates
// ==========================================

function buildCustomersTableRows(merchantId, customers, loyaltyType) {
    if (customers.length === 0) {
        return '<tr><td colspan="4" style="text-align:center; color:gray;">Aucun client</td></tr>';
    }

    return customers.map(c => {
        const rawName = c.customers ? `${c.customers.first_name || ''} ${c.customers.last_name || ''}`.trim() : '';
        const name = escapeHtml(rawName || 'Inconnu');
        // Cashback cards track a euro balance; the others track points.
        const value = loyaltyType === 'cashback'
            ? `${((c.balance_cents || 0) / 100).toFixed(2).replace('.', ',')} €`
            : `${c.points} pts`;
        return `
            <tr>
                <td><strong>${name}</strong></td>
                <td><span class="badge">${value}</span></td>
                <td style="color:gray; font-size:12px;">${new Date(c.created_at).toLocaleDateString()}</td>
                <td>
                    <button onclick="deleteCustomer('${merchantId}', '${c.customer_id}')" class="chip-btn danger-btn">
                        Retirer
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function buildLogsTableRows(logs) {
    if (logs.length === 0) {
        return '<tr><td colspan="4" style="text-align:center; color:gray;">Aucun historique</td></tr>';
    }
    
    return logs.map(l => {
        const rawClientName = l.customers ? `${l.customers.first_name || ''} ${l.customers.last_name || ''}`.trim() : '';
        const clientName = escapeHtml(rawClientName || 'Inconnu');
        let actionText = '';
        let actionColor = 'gray';
        
        if (l.action_type === 'SCAN') { actionText = '+1 Point'; actionColor = 'var(--primary)'; }
        if (l.action_type === 'REWARD') { actionText = 'Récompense !'; actionColor = 'var(--success)'; }
        if (l.action_type === 'PUSH_CAMPAIGN') { actionText = 'Push Marketing'; actionColor = 'var(--accent)'; }
        if (l.action_type === 'CASHBACK_EARN') { actionText = 'Cashback crédité'; actionColor = 'var(--success)'; }
        if (l.action_type === 'CASHBACK_REDEEM') { actionText = 'Cagnotte utilisée'; actionColor = 'var(--text-muted)'; }
        
        return `
            <tr>
                <td>${new Date(l.created_at).toLocaleString()}</td>
                <td><span style="color: ${actionColor}; font-weight: bold;">${actionText}</span></td>
                <td>${clientName}</td>
            </tr>
        `;
    }).join('');
}

function buildMerchantCardHTML(m, customersCount, rowsHTML, logsRowsHTML) {
    const signupUrl = `https://projet-fidel.vercel.app/?merchant_id=${m.id}`;
    const qrCodeUrl = `https://api.qrserver.com/v1/create-qr-code/?size=500x500&data=${encodeURIComponent(signupUrl)}`;

    const name = escapeHtml(m.name);
    const rewardDesc = escapeHtml(m.reward_description ?? '');
    const colorHex = escapeHtml(m.color_hex || '#FF9800');
    const logoUrl = escapeHtml(m.logo_url || '');
    const heroUrl = escapeHtml(m.hero_url || '');
    const programName = escapeHtml(m.program_name || '');
    const pointsLabel = escapeHtml(m.points_label || 'Points');
    const phone = escapeHtml(m.phone || '');
    const website = escapeHtml(m.website || '');
    const loyaltyType = ['stamps', 'tiers', 'cashback'].includes(m.loyalty_type) ? m.loyalty_type : 'points';
    const tiersText = escapeHtml((m.tiers || []).map(t => `${t.threshold} = ${t.reward}`).join('\n'));
    const cashbackRate = escapeHtml(m.cashback_rate != null ? m.cashback_rate : 0);
    const sel = (v) => loyaltyType === v ? ' selected' : '';
    const showThresh = (loyaltyType === 'points' || loyaltyType === 'stamps') ? 'flex' : 'none';
    const showTiers = loyaltyType === 'tiers' ? 'flex' : 'none';
    const showCashback = loyaltyType === 'cashback' ? 'flex' : 'none';
    const previewText = contrastText(m.color_hex || '#FF9800');

    return `
        <div class="merchant-header">
            <div>
                <div class="merchant-title">${name}</div>
                <div style="color:gray; font-size:14px;">${customersCount} clients</div>
            </div>
            <div style="display:flex; gap:10px; align-items:center;">
                <a href="${qrCodeUrl}" target="_blank" class="chip-btn qr-btn">
                    QR Code Inscription
                </a>
                <button onclick="deleteMerchant('${m.id}')" class="chip-btn danger-btn">
                    Supprimer
                </button>
            </div>
        </div>
        
        <div class="offer-row">
        <form class="offer-form" onsubmit="updateOffer(event, '${m.id}')" style="flex:2 1 360px; flex-direction:column; align-items:stretch;">
            <div class="offer-tabs">
                <button type="button" class="offer-tab active" onclick="switchOfferTab(event, '${m.id}', 'offre')">Offre</button>
                <button type="button" class="offer-tab" onclick="switchOfferTab(event, '${m.id}', 'design')">Design</button>
                <button type="button" class="offer-tab" onclick="switchOfferTab(event, '${m.id}', 'contact')">Contact</button>
            </div>

            <!-- Onglet Offre : mécanique de fidélité -->
            <div id="otab-offre_${m.id}" class="offer-pane" style="display:flex;">
                <div style="flex:1; min-width:160px;">
                    <label class="field-label">Type de carte</label>
                    <select id="ltype_${m.id}" onchange="updateOfferFields('${m.id}')" style="width:100%; padding:10px; height:42px;">
                        <option value="points"${sel('points')}>Points à seuil</option>
                        <option value="stamps"${sel('stamps')}>Carte à tampons</option>
                        <option value="tiers"${sel('tiers')}>Paliers</option>
                        <option value="cashback"${sel('cashback')}>Cashback (%)</option>
                    </select>
                </div>
                <div id="ltype-desc_${m.id}" style="flex-basis:100%; font-size:12px; color:var(--text-muted); margin-top:-2px;">${LOYALTY_DESC[loyaltyType]}</div>

                <div id="field-threshold_${m.id}" style="display:${showThresh}; flex:3 1 260px; flex-wrap:wrap; gap:10px;">
                    <div style="flex:1; min-width:100px;">
                        <label id="thresh-label_${m.id}" class="field-label">${loyaltyType === 'stamps' ? 'Nombre de tampons' : 'Seuil'}</label>
                        <input type="number" id="thresh_${m.id}" value="${escapeHtml(m.reward_threshold)}" min="1">
                    </div>
                    <div style="flex:2; min-width:150px;">
                        <label class="field-label">Récompense</label>
                        <input type="text" id="desc_${m.id}" value="${rewardDesc}" oninput="updateCardPreview('${m.id}')">
                    </div>
                </div>

                <div id="field-tiers_${m.id}" style="display:${showTiers}; flex:3 1 240px;">
                    <div style="flex:1; width:100%;">
                        <label class="field-label">Paliers — 1 par ligne : <code>seuil = récompense</code></label>
                        <textarea id="tiers_${m.id}" rows="3" placeholder="5 = Café offert&#10;10 = Viennoiserie&#10;20 = Menu complet" style="width:100%; padding:10px; box-sizing:border-box; font-size:14px;">${tiersText}</textarea>
                    </div>
                </div>

                <div id="field-cashback_${m.id}" style="display:${showCashback}; flex:1 1 160px;">
                    <div style="flex:1; width:100%;">
                        <label class="field-label">Taux cashback (%)</label>
                        <input type="number" id="cashback_${m.id}" value="${cashbackRate}" min="0" max="100" step="0.5">
                    </div>
                </div>
            </div>

            <!-- Onglet Design : apparence de la carte -->
            <div id="otab-design_${m.id}" class="offer-pane" style="display:none;">
                <div style="flex:1; min-width:100px;">
                    <label class="field-label">Couleur (Hex)</label>
                    <input type="color" id="color_${m.id}" value="${colorHex}" style="height:44px; padding:2px;" oninput="updateCardPreview('${m.id}')">
                </div>
                <div style="flex:2; min-width:200px;">
                    <label class="field-label">Nom du programme</label>
                    <input type="text" id="program_${m.id}" value="${programName}" placeholder="${name}" maxlength="100" oninput="updateCardPreview('${m.id}')">
                </div>
                <div style="flex:1; min-width:120px;">
                    <label class="field-label">Libellé des points</label>
                    <input type="text" id="plabel_${m.id}" value="${pointsLabel}" placeholder="Points" maxlength="30" oninput="updateCardPreview('${m.id}')">
                </div>
                <div style="flex:2; min-width:200px;">
                    <label class="field-label">Lien Logo (URL) — carré, ~512px</label>
                    <input type="url" id="logo_${m.id}" value="${logoUrl}" placeholder="https://…/logo.png" oninput="updateCardPreview('${m.id}'); checkImageStatus('${m.id}','logo')">
                    <div class="img-status" id="logo-status_${m.id}"></div>
                </div>
                <div style="flex:2; min-width:200px;">
                    <label class="field-label">Lien Couverture (URL) — large, ~1032×336</label>
                    <input type="url" id="hero_${m.id}" value="${heroUrl}" placeholder="https://…/banniere.jpg" oninput="updateCardPreview('${m.id}'); checkImageStatus('${m.id}','hero')">
                    <div class="img-status" id="hero-status_${m.id}"></div>
                </div>
            </div>

            <!-- Onglet Contact : liens sur la carte -->
            <div id="otab-contact_${m.id}" class="offer-pane" style="display:none;">
                <div style="flex:1; min-width:140px;">
                    <label class="field-label">Téléphone</label>
                    <input type="tel" id="phone_${m.id}" value="${phone}" placeholder="06 12 34 56 78" maxlength="30">
                </div>
                <div style="flex:2; min-width:200px;">
                    <label class="field-label">Site web (URL)</label>
                    <input type="text" id="website_${m.id}" value="${website}" placeholder="https://..." maxlength="300">
                </div>
            </div>

            <div style="margin-top:14px;">
                <button type="submit" class="btn-accent" style="width:auto; padding:10px 20px;">Sauvegarder les paramètres</button>
            </div>
        </form>

        <div class="card-preview">
            <div class="cp-card" id="cp-card_${m.id}" data-name="${name}" style="background:${colorHex}; color:${previewText};">
                <div class="cp-head">
                    <img class="cp-logo" id="cp-logo_${m.id}" src="${logoUrl}" alt="" style="${logoUrl ? '' : 'display:none;'}" onerror="this.style.display='none'">
                    <div class="cp-cardtitle" id="cp-program_${m.id}">${programName || name}</div>
                </div>
                <div class="cp-header" id="cp-header_${m.id}">120 ${pointsLabel}</div>
                <div class="cp-subheader">Jean Dupont</div>
                <div class="cp-hero" id="cp-hero-wrap_${m.id}" style="${heroUrl ? '' : 'display:none;'}">
                    <img id="cp-hero_${m.id}" src="${heroUrl}" alt="" onerror="this.parentElement.style.display='none'">
                </div>
            </div>
            <div class="cp-caption">Aperçu — l'objectif et les infos s'affichent au dos de la carte</div>
        </div>
        </div>

        <div style="display:flex; gap: 20px; margin-top: 15px;">
            <div style="flex: 1; background: rgba(0,0,0,0.2); border-radius: 8px; overflow:hidden;">
                <div style="padding: 10px; background: rgba(0,0,0,0.3); font-weight: bold; font-size: 14px;">Clients (${customersCount})</div>
                <table>
                    <thead>
                        <tr><th>Client</th><th>Points</th><th>Inscrit le</th><th>Action</th></tr>
                    </thead>
                    <tbody>${rowsHTML}</tbody>
                </table>
            </div>
            
            <div style="flex: 1; background: rgba(0,0,0,0.2); border-radius: 8px; overflow:hidden; max-height: 300px; overflow-y: auto;">
                <div style="padding: 10px; background: rgba(0,0,0,0.3); font-weight: bold; font-size: 14px;">Historique Récent</div>
                <table>
                    <thead>
                        <tr><th>Date</th><th>Action</th><th>Client</th></tr>
                    </thead>
                    <tbody>${logsRowsHTML}</tbody>
                </table>
            </div>
        </div>
    `;
}

// ==========================================
// Event Listeners & Actions
// ==========================================

// Switch between the Offre / Design / Contact tabs of a merchant card.
window.switchOfferTab = function(e, merchantId, tab) {
    ['offre', 'design', 'contact'].forEach(t => {
        const pane = document.getElementById(`otab-${t}_${merchantId}`);
        if (pane) pane.style.display = (t === tab) ? 'flex' : 'none';
    });
    const bar = e.target.parentElement;
    bar.querySelectorAll('.offer-tab').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
};

// Show only the fields relevant to the selected loyalty type.
window.updateOfferFields = function(merchantId) {
    const type = document.getElementById(`ltype_${merchantId}`).value;
    const setShown = (id, on) => {
        const el = document.getElementById(id);
        if (el) el.style.display = on ? 'flex' : 'none';
    };
    setShown(`field-threshold_${merchantId}`, type === 'points' || type === 'stamps');
    setShown(`field-tiers_${merchantId}`, type === 'tiers');
    setShown(`field-cashback_${merchantId}`, type === 'cashback');

    // Explanatory text + contextual label for the threshold field.
    const descEl = document.getElementById(`ltype-desc_${merchantId}`);
    if (descEl) descEl.innerText = LOYALTY_DESC[type] || '';
    const threshLabel = document.getElementById(`thresh-label_${merchantId}`);
    if (threshLabel) threshLabel.innerText = (type === 'stamps') ? 'Nombre de tampons' : 'Seuil';

    // Suggest a card label that matches the chosen model (only if not customized).
    const plabel = document.getElementById(`plabel_${merchantId}`);
    if (plabel) {
        if (type === 'stamps' && (!plabel.value || plabel.value === 'Points')) plabel.value = 'Tampons';
        if (type === 'points' && plabel.value === 'Tampons') plabel.value = 'Points';
    }
};

window.updateOffer = async function(e, merchantId) {
    e.preventDefault();
    const threshold = document.getElementById(`thresh_${merchantId}`).value;
    const desc = document.getElementById(`desc_${merchantId}`).value;
    const color = document.getElementById(`color_${merchantId}`).value;
    const logo = document.getElementById(`logo_${merchantId}`).value;
    const hero = document.getElementById(`hero_${merchantId}`).value;
    const programName = document.getElementById(`program_${merchantId}`).value;
    const pointsLabel = document.getElementById(`plabel_${merchantId}`).value;
    const phone = document.getElementById(`phone_${merchantId}`).value;
    const website = document.getElementById(`website_${merchantId}`).value;
    const loyaltyType = document.getElementById(`ltype_${merchantId}`).value;

    // Parse the tiers editor: one line "threshold = reward".
    const tiers = document.getElementById(`tiers_${merchantId}`).value
        .split('\n')
        .map(line => {
            const idx = line.indexOf('=');
            if (idx === -1) return null;
            const threshold = parseInt(line.slice(0, idx).trim(), 10);
            const reward = line.slice(idx + 1).trim();
            return (threshold > 0 && reward) ? { threshold, reward } : null;
        })
        .filter(Boolean)
        .sort((a, b) => a.threshold - b.threshold);

    if (loyaltyType === 'tiers' && tiers.length === 0) {
        alert("Type « Paliers » sélectionné mais aucun palier valide. Format attendu : « 5 = Café offert » (un par ligne).");
        return;
    }

    const cashbackRate = parseFloat(document.getElementById(`cashback_${merchantId}`).value) || 0;
    if (loyaltyType === 'cashback' && cashbackRate <= 0) {
        alert("Type « Cashback » sélectionné mais le taux est à 0 %. Indiquez un taux (ex : 5).");
        return;
    }

    if ((loyaltyType === 'points' || loyaltyType === 'stamps') && (!(parseInt(threshold) > 0) || !desc.trim())) {
        alert("Pour « Points » / « Tampons », renseignez un seuil (> 0) et une récompense.");
        return;
    }

    // The form also contains the tab buttons, so target the actual submit button
    // (not the first <button>, which is the "Offre" tab).
    const btn = e.submitter || e.target.querySelector('button[type="submit"]');

    btn.innerText = "Sauvegarde...";
    try {
        const res = await adminFetch(`${API_BASE_URL}/dashboard/admin/update_offer`, {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                merchant_id: merchantId,
                reward_threshold: parseInt(threshold),
                reward_description: desc,
                color_hex: color,
                logo_url: logo,
                hero_url: hero,
                program_name: programName,
                points_label: pointsLabel,
                phone: phone,
                website: website,
                loyalty_type: loyaltyType,
                tiers: tiers,
                cashback_rate: cashbackRate
            })
        });
        if (!res.ok) throw new Error("Erreur");
        const data = await res.json().catch(() => ({}));
        btn.innerText = "Sauvegardé !";
        btn.style.background = "var(--success)";

        // Show whether Google Wallet accepted the design sync (key for diagnosing
        // "the card doesn't change").
        const ws = data.wallet_sync;
        if (ws && ws.ok === false) {
            alert("Réglages enregistrés ✅, mais la mise à jour des cartes Wallet a échoué ❌.\n\n"
                + (ws.error || 'erreur inconnue')
                + (ws.total ? `\n\n(${ws.updated || 0}/${ws.total} cartes mises à jour)` : ''));
        } else if (ws && ws.ok === true) {
            btn.innerText = ws.total ? `Cartes synchro ✓ (${ws.updated}/${ws.total})` : "Sauvegardé ✓";
        }

        setTimeout(() => {
            btn.innerText = "Sauvegarder les paramètres";
            btn.style.background = "";
        }, 2500);
    } catch (err) {
        alert("Erreur lors de la mise à jour");
        btn.innerText = "Sauvegarder les paramètres";
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
        const res = await adminFetch(`${API_BASE_URL}/dashboard/admin/merchants/create`, {
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
        const res = await adminFetch(`${API_BASE_URL}/dashboard/admin/customers/${merchantId}/${customerId}`, {
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
        const res = await adminFetch(`${API_BASE_URL}/dashboard/admin/merchants/${merchantId}`, {
            method: 'DELETE'
        });
        if (!res.ok) throw new Error("Erreur lors de la suppression de la boutique");
        fetchAgencyData(); // Refresh UI
    } catch (err) {
        alert(err.message);
    }
}
