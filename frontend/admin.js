// Global Configuration
const API_BASE = window.BASH_API_BASE_URL;

// The backend's /media/upload (and host verification docs) return a
// relative path like "/static/docs/x.jpg". Every other page (home.js,
// host_dashboard.js, profile.js, cheki.html) resolves that back to an
// absolute URL through this same helper before ever putting it in an
// <img src>; admin.js was missing it entirely, which is why the host
// review photos and the payout-request event thumbnail never rendered —
// the browser was trying to load "/static/..." against admin.html's own
// origin instead of the API server.
function resolveMediaUrl(u) {
  if (!u) return u;
  if (/^(https?:)?\/\//i.test(u) || u.startsWith("data:")) return u;
  return API_BASE + (u.startsWith("/") ? "" : "/") + u;
}

async function loadAdminHostEvents() {
    const listContainer = document.getElementById("events-list");
    const counter = document.getElementById("metric-events-count");
    
    if (!listContainer) return;

    try {
        const response = await fetch(`${API_BASE}/admin/host_events`, {
            method: 'GET',
            headers: getAuthHeaders()
        });
        
        if (!response.ok) throw new Error('Failed to load events');
        
        const events = await response.json();
        
        // 1. Update the Count
        counter.textContent = events.length;
        
        // 2. Render the List
        listContainer.innerHTML = events.length > 0 
            ? events.map(event => `
                <div class="event-item" style="padding: 1rem; border-bottom: 1px solid var(--border-color); cursor: pointer;">
                    <div style="font-weight: 600; color: var(--text-main);">${event.eventName || 'Untitled Event'}</div>
                    <div style="font-size: 0.8rem; color: var(--text-muted);">
                        Host: ${event.username} | ${event.location || 'Thika'}
                    </div>
                </div>
            `).join('')
            : '<p style="padding: 1rem; color: var(--text-muted);">No active gatherings found.</p>';
            
    } catch (e) {
        console.error("Error loading events into dashboard:", e);
    }
}

// Local In-Memory Application Memory Stores
let activeVerificationUser = null;
let completeEventsCache = [];
let currentVerificationFilter = 'pending'; // Tracks active sub-tab: 'pending', 'approved', or 'rejected'

// Base Header Generator containing Admin Token Authentication
function getAuthHeaders() {
    let token = localStorage.getItem("bashAdminAccessToken");
    if (!token) {
        token = localStorage.getItem("bashToken");
    }
    if (!token) {
        console.warn("Production Warning: Missing administrative security token context mapping.");
    }
    return {
        "Content-Type": "application/json",
        "Authorization": token ? `Bearer ${token}` : ""
    };
}

// Dynamic Sub-Navigation Switcher for Verification States
function switchVerificationFilter(filterType) {
    currentVerificationFilter = filterType;
    
    // Clear active states across the sidebar buttons
    document.getElementById('filter-pending-btn').classList.remove('active');
    document.getElementById('filter-approved-btn').classList.remove('active');
    document.getElementById('filter-rejected-btn').classList.remove('active');
    
    // Set active status on current selector
    const activeBtn = document.getElementById(`filter-${filterType}-btn`);
    if (activeBtn) activeBtn.classList.add('active');
    
    // Update container header prose dynamically
    const panelTitles = {
        'pending': 'Pending Applications',
        'approved': 'Approved Onboarded Hosts',
        'rejected': 'Rejected Administrative Portfolio'
    };
    document.getElementById('verification-panel-title').innerText = panelTitles[filterType] || 'Applications';
    
    loadFilteredVerifications();
}

// Global Core View Switcher Engine - Safely handles showing/hiding the flyout sidebar container
function switchPage(pageId, elementAnchor = null) {
    if (typeof window.__updateTopbar === 'function') window.__updateTopbar(pageId);
    if (typeof window.closeMobileNav === 'function') window.closeMobileNav();
    document.querySelectorAll('.page-view').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.suite-sidebar .nav-btn').forEach(b => b.classList.remove('active'));
    
    const targetPage = document.getElementById(`page-${pageId}`);
    if (targetPage) targetPage.classList.add('active');
    
    if (elementAnchor) {
        elementAnchor.classList.add('active');
    }

    const sidebarNode = document.getElementById('verification-sidebar-nav');
    if (pageId === 'verifications') {
        if (sidebarNode) sidebarNode.style.display = 'flex';
        loadFilteredVerifications();
    } else {
        if (sidebarNode) sidebarNode.style.display = 'none';
    }

    // Stop the support-desk poller whenever we navigate away from it —
    if (pageId !== 'support' && window.adminChatTimer) {
        clearInterval(window.adminChatTimer);
        window.adminChatTimer = null;
    }

    if (pageId === 'events') { fetchAllPlatformEvents(); loadEventsTabCounts(); }
    if (pageId === 'payouts') loadPayoutRequests();
    if (pageId === 'refunds') initRefundsPage();
    if (pageId === 'manual-payments') initManualPaymentsPage();
    if (pageId === 'referral-gate') initReferralGatePage();
    if (pageId === 'duplicate-guard') initDuplicateGuardPage();
    if (pageId === 'adder') initAdderPage();
    if (pageId === 'financials') openFinancialsGate();
    if (pageId === 'broadcasts') initBroadcastPage();
    if (pageId === 'support') initSupportPage();
    if (pageId === 'analytics') initAnalyticsPage();
    if (pageId === 'usergrowth') initUserGrowthPage();
}

// ---- Sidebar badge counts (Events "not reviewed" + Refunds "requested") ----
async function refreshSidebarBadges() {
    try {
        const res = await fetch(`${API_BASE}/admin/events/reviewed-counts`, { headers: getAuthHeaders() });
        if (res.ok) {
            const data = await res.json();
            const badge = document.getElementById("nav-badge-events");
            if (badge) {
                badge.textContent = data.unreviewed;
                badge.classList.toggle("show", data.unreviewed > 0);
            }
        }
    } catch (e) { /* non-fatal */ }

    try {
        const res = await fetch(`${API_BASE}/admin/refunds/pending-count`, { headers: getAuthHeaders() });
        if (res.ok) {
            const data = await res.json();
            const badge = document.getElementById("nav-badge-refunds");
            if (badge) {
                badge.textContent = data.pending;
                badge.classList.toggle("show", data.pending > 0);
            }
        }
    } catch (e) { /* non-fatal */ }

    try {
        const res = await fetch(`${API_BASE}/admin/manual-payments/pending-count`, { headers: getAuthHeaders() });
        if (res.ok) {
            const data = await res.json();
            const badge = document.getElementById("nav-badge-manualpay");
            if (badge) {
                badge.textContent = data.count;
                badge.classList.toggle("show", data.count > 0);
            }
        }
    } catch (e) { /* non-fatal */ }

    try {
        const res = await fetch(`${API_BASE}/admin/duplicate-guard/pending`, { headers: getAuthHeaders() });
        if (res.ok) {
            const data = await res.json();
            const count = (data.pending || []).length;
            const badge = document.getElementById("nav-badge-dupguard");
            if (badge) {
                badge.textContent = count;
                badge.classList.toggle("show", count > 0);
            }
        }
    } catch (e) { /* non-fatal */ }
}
setInterval(refreshSidebarBadges, 30000);
document.addEventListener("DOMContentLoaded", refreshSidebarBadges);

// ---- Payout Requests (hosts demanding payment via the Payout Ledger) ----
async function loadPayoutRequests() {
    const list = document.getElementById("payouts-list");
    if (!list) return;
    list.innerHTML = `<p style="color:var(--text-muted); padding:1rem;">Loading pending payout requests…</p>`;
    try {
        const res = await fetch(`${API_BASE}/admin/withdrawals/pending`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const rows = await res.json();
        if (!Array.isArray(rows) || !rows.length) {
            list.innerHTML = `<p style="color:var(--text-muted); padding:1rem;">No pending payout requests.</p>`;
            return;
        }
        const statusLabel = {
            requested: "Awaiting your message",
            awaiting_host_confirmation: "Waiting on host to confirm/deny",
            confirmed_by_host: "Host confirmed — send M-Pesa & log code",
        };
        list.innerHTML = rows.map(w => `
            <div class="host-card" style="display:flex; flex-direction:column; gap:0.5rem; padding:1rem; border:1px solid var(--border-color); border-radius:12px; margin-bottom:0.75rem;">
                <div style="display:flex; gap:0.75rem; align-items:center; justify-content:space-between;">
                    <div style="display:flex; gap:0.75rem; align-items:center; min-width:0;">
                        <div style="width:44px; height:44px; border-radius:10px; flex-shrink:0; background:rgba(255,255,255,0.06) center/cover no-repeat; ${w.event_poster_url ? `background-image:url('${resolveMediaUrl(w.event_poster_url)}');` : ""}"></div>
                        <strong style="overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${w.event_title || "Untitled event"}</strong>
                    </div>
                    <span style="font-size:0.68rem; text-transform:uppercase; color:var(--accent-primary); font-weight:700; flex-shrink:0;">${statusLabel[w.status] || w.status}</span>
                </div>
                <p style="font-size:0.78rem; color:var(--text-muted);">${w.host_name || w.host_username || "Unknown host"} · ${w.host_email || ""}</p>
                <div style="display:grid; grid-template-columns:repeat(3,1fr); gap:0.5rem; background:rgba(0,0,0,0.2); border-radius:10px; padding:0.65rem 0.75rem; margin-top:0.25rem;">
                    <div><p style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase;">Revenue</p><p style="font-weight:700;">KSh ${Number(w.gross_revenue || 0).toLocaleString()}</p></div>
                    <div><p style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase;">Our 12% cut</p><p style="font-weight:700; color:var(--accent-primary);">KSh ${Number(w.platform_cut || 0).toLocaleString()}</p></div>
                    <div><p style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase;">Host payout</p><p style="font-weight:700; color:var(--accent-success);">KSh ${Number(w.host_payout_amount || 0).toLocaleString()}</p></div>
                </div>
                <p style="font-size:0.75rem; color:var(--text-muted); margin-top:0.35rem;">
                    ${w.mpesa_paybill ? `M-Pesa: ${w.mpesa_paybill}` : ""}${w.mpesa_paybill && w.bank_name ? " · " : ""}${w.bank_name ? `${w.bank_name} · ${w.account_number || ""} (${w.account_name || ""})${w.bank_business_number ? ` · Biz No: ${w.bank_business_number}` : ""}` : ""}
                    ${!w.mpesa_paybill && !w.bank_name ? "No bank/M-Pesa details on file yet" : ""}
                </p>
                <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
                    ${w.status === "requested" ? `<button class="action-btn" style="flex:1;" onclick="messageHostForPayout('${w.id}')">Message</button>` : ""}
                    ${w.status === "awaiting_host_confirmation" ? `<button class="action-btn" style="flex:1;" disabled>Waiting on host…</button>` : ""}
                    ${w.status === "confirmed_by_host" ? `<button class="action-btn" style="flex:1; background:var(--accent-success); color:#04150d;" onclick="markPayoutPaid('${w.id}')">Enter M-Pesa Code &amp; Mark Paid</button>` : ""}
                </div>
            </div>
        `).join("");
    } catch (err) {
        console.error("Failed loading payout requests:", err);
        list.innerHTML = `<p style="color:var(--text-muted); padding:1rem;">Couldn't reach the server to load payout requests.</p>`;
    }
}

async function messageHostForPayout(withdrawalId) {
    try {
        const res = await fetch(`${API_BASE}/admin/withdrawals/${withdrawalId}/message`, {
            method: "POST",
            headers: getAuthHeaders(),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            alert(data.detail || "Couldn't message this host.");
            return;
        }
        alert("Sent — the host now has the event, expected payment, and bank details to confirm or deny.");
        loadPayoutRequests();
    } catch (err) {
        console.error("Message host failed:", err);
        alert("Couldn't reach the server to message this host.");
    }
}

async function markPayoutPaid(withdrawalId) {
    const mpesa_code = prompt("M-Pesa confirmation code for this payout (after you've sent the money):");
    if (mpesa_code === null || !mpesa_code.trim()) return;
    try {
        const res = await fetch(`${API_BASE}/admin/withdrawals/${withdrawalId}/mark-paid`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ mpesa_code: mpesa_code.trim() }),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            alert(data.detail || "Couldn't mark this payout as paid.");
            return;
        }
        alert("Logged — the host has been sent the M-Pesa code as proof of payment.");
        loadPayoutRequests();
    } catch (err) {
        console.error("Mark paid failed:", err);
        alert("Couldn't reach the server to log this payment.");
    }
}

// Background worker thread engine updating all badge totals concurrently
async function updateSidebarBadgeCounters() {
    const endpoints = {
        'pending': `${API_BASE}/admin/hosts/pending`,
        'approved': `${API_BASE}/admin/hosts/approved`,
        'rejected': `${API_BASE}/admin/hosts/rejected`
    };

    try {
        const [pendingRes, approvedRes, rejectedRes] = await Promise.all([
            fetch(endpoints.pending, { headers: getAuthHeaders() }),
            fetch(endpoints.approved, { headers: getAuthHeaders() }),
            fetch(endpoints.rejected, { headers: getAuthHeaders() })
        ]);

        if (pendingRes.ok) {
            const data = await pendingRes.json();
            document.getElementById('badge-pending-count').innerText = data.length;
        }
        if (approvedRes.ok) {
            const data = await approvedRes.json();
            document.getElementById('badge-approved-count').innerText = data.length;
        }
        if (rejectedRes.ok) {
            const data = await rejectedRes.json();
            document.getElementById('badge-rejected-count').innerText = data.length;
        }
    } catch (err) {
        console.warn("Failed syncing background badge metrics maps:", err);
    }
}

// ==========================================
async function loadFilteredVerifications() {
    try {
        const endpoints = {
            'pending': `${API_BASE}/admin/hosts/pending`,
            'approved': `${API_BASE}/admin/hosts/approved`,
            'rejected': `${API_BASE}/admin/hosts/rejected`
        };

        const response = await fetch(endpoints[currentVerificationFilter], { headers: getAuthHeaders() });
        if (!response.ok) throw new Error(`HTTP Error Status: ${response.status}`);
        
        const applicants = await response.json();
        const container = document.getElementById("verifications-list");
        container.innerHTML = "";

        const metricId = `metric-${currentVerificationFilter}-count`;
        const metricElement = document.getElementById(metricId);
        if (metricElement) {
            metricElement.innerText = applicants.length;
        }

        if (!applicants.length) {
            container.innerHTML = `<p style="text-align:center; color:var(--text-muted); padding: 2.5rem 1.5rem;">No platform records found matching this filter preference.</p>`;
            updateSidebarBadgeCounters();
            return;
        }

        applicants.forEach(user => {
            const row = document.createElement("div");
            row.className = "list-item";
            row.innerHTML = `
                <div>
                    <h3 style="font-weight:700;">${user.full_name || 'Anonymous Applicant'}</h3>
                    <p style="color: var(--text-muted); font-size:0.85rem; margin-top:0.25rem;">${user.email || 'No email on file'}</p>
                </div>
                <div style="color: var(--accent-primary); font-weight:600;">${user.phone || 'No Phone Connection'}</div>
            `;
            row.onclick = () => showVerificationOverlayCard(user);
            container.appendChild(row);
        });

        updateSidebarBadgeCounters();

    } catch (err) {
        console.error("Verification processing failed:", err);
        document.getElementById("verifications-list").innerHTML = `<p style="text-align:center; color:var(--accent-primary); padding:1.5rem;">Network Pipeline Error Retrieving System Records.</p>`;
    }
}

function loadPendingVerifications() {
    loadFilteredVerifications();
}

function showVerificationOverlayCard(user) {
    activeVerificationUser = user;
    const injector = document.getElementById("modal-injector-content");

    let controlButtonsHTML = '';
    if (currentVerificationFilter === 'pending') {
        controlButtonsHTML = `
            <button class="action-btn btn-reject" onclick="executeVerificationAction('reject')">Reject Applicant</button>
            <button class="action-btn btn-approve" onclick="executeVerificationAction('approve')">Approve Access</button>
        `;
    } else {
        controlButtonsHTML = `
            <button class="action-btn btn-reject" style="border-color: var(--accent-orange); color: var(--accent-orange); width: 100%;" onclick="executeVerificationAction('reverse')">
                🔄 Reverse State to Pending Review
            </button>
        `;
    }

    // Document photos the applicant submitted — this is what an admin actually
    const docsHTML = [
        { label: "Government ID", url: user.government_id_image_url },
        { label: "Business Registration", url: user.business_registration_image_url },
    ].map(doc => doc.url ? `
        <div>
            <p style="font-size:0.75rem; color:var(--text-muted); margin-bottom:0.4rem;">${doc.label}</p>
            <img src="${resolveMediaUrl(doc.url)}" alt="${doc.label}" style="width:100%; border-radius:10px; cursor:zoom-in;" onclick="window.open('${resolveMediaUrl(doc.url)}', '_blank')">
        </div>` : `
        <div>
            <p style="font-size:0.75rem; color:var(--text-muted); margin-bottom:0.4rem;">${doc.label}</p>
            <p style="font-size:0.8rem; color:var(--text-muted); font-style:italic;">Not submitted</p>
        </div>`
    ).join("");

    injector.innerHTML = `
        <div style="text-align:center; margin-bottom:1.5rem;">
            <h2>${user.full_name}</h2>
            <p style="color:var(--text-muted);">${user.email}</p>
        </div>
        <div style="background:rgba(0,0,0,0.2); padding:1.25rem; border-radius:12px; font-size:0.95rem; line-height:1.6;">
            <p><strong>Phone:</strong> ${user.phone || 'Not provided'}</p>
            <p><strong>M-Pesa Paybill:</strong> ${user.mpesa_paybill || 'None on file'}</p>
            <p><strong>Bank:</strong> ${user.bank_name || 'Not provided'}</p>
            <p><strong>Business No:</strong> ${user.bank_business_number || 'Not provided'}</p>
            <p style="margin-top:0.5rem; font-size:0.8rem; color:var(--text-muted);">Status: <span style="text-transform:uppercase; color:var(--accent-primary); font-weight:700;">${currentVerificationFilter}</span></p>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:1rem; margin-top:1rem;">
            ${docsHTML}
        </div>
        <div class="btn-group">
            ${controlButtonsHTML}
        </div>
    `;
    document.getElementById("global-overlay").classList.add("active");
}

async function executeVerificationAction(actionType) {
    if (!activeVerificationUser) return;
    const card = document.getElementById("global-card");
    
    let requestUrl = `${API_BASE}/admin/hosts/${activeVerificationUser.id}/verify`;
    let payloadBody = {};

    if (actionType === 'approve') {
        payloadBody = { approve: true, note: "Onboarded via System Admin Dashboard" };
    } else if (actionType === 'reject') {
        payloadBody = { approve: false, note: "Rejected administrative parameters criteria evaluation failure" };
    } else if (actionType === 'reverse') {
        requestUrl = `${API_BASE}/admin/hosts/${activeVerificationUser.id}/reverse-status`;
        payloadBody = { note: "Administrative reversal status initialization executed" };
    }
    
    try {
        const response = await fetch(requestUrl, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify(payloadBody)
        });

        if (response.ok) {
            card.classList.add(actionType === 'approve' ? "exit-approve" : "exit-reject");
            setTimeout(() => {
                closeGlobalModal();
                card.classList.remove("exit-approve", "exit-reject");
                loadFilteredVerifications();
            }, 450);
        } else {
            alert("Administrative state processing modification rejected by backend validation frameworks.");
        }
    } catch (err) {
        console.error("Action error processing update:", err);
    }
}

// ==========================================
let deadlineCountdownTimer = null;
let currentDetailedEventId = null;
let currentEventsTab = 'unreviewed'; // 'unreviewed' | 'reviewed' | 'community'

function switchEventsTab(tab) {
    currentEventsTab = tab;
    ['unreviewed', 'reviewed', 'community'].forEach(t => {
        const btn = document.getElementById(`events-tab-${t}`);
        if (btn) btn.classList.toggle('active', t === tab);
    });
    const eventsPanel = document.getElementById('events-tab-panel-events');
    const communityPanel = document.getElementById('events-tab-panel-community');
    if (tab === 'community') {
        if (eventsPanel) eventsPanel.style.display = 'none';
        if (communityPanel) communityPanel.style.display = '';
        loadCommunityPosts();
    } else {
        if (eventsPanel) eventsPanel.style.display = '';
        if (communityPanel) communityPanel.style.display = 'none';
        fetchAllPlatformEvents();
    }
}

async function loadEventsTabCounts() {
    try {
        const res = await fetch(`${API_BASE}/admin/events/reviewed-counts`, { headers: getAuthHeaders() });
        if (res.ok) {
            const data = await res.json();
            const u = document.getElementById('events-tab-count-unreviewed');
            const r = document.getElementById('events-tab-count-reviewed');
            if (u) u.textContent = data.unreviewed;
            if (r) r.textContent = data.reviewed;
        }
    } catch (e) { console.error("Failed loading events review counts:", e); }

    try {
        const res = await fetch(`${API_BASE}/admin/community-posts/seen-counts`, { headers: getAuthHeaders() });
        if (res.ok) {
            const data = await res.json();
            const c = document.getElementById('events-tab-count-community');
            if (c) c.textContent = data.unseen;
        }
    } catch (e) { console.error("Failed loading community post counts:", e); }
}

async function fetchAllPlatformEvents() {
    try {
        const reviewedParam = currentEventsTab === 'reviewed' ? 'reviewed' : (currentEventsTab === 'unreviewed' ? 'unreviewed' : '');
        const url = `${API_BASE}/admin/events/all${reviewedParam ? `?reviewed=${reviewedParam}` : ""}`;
        const response = await fetch(url, { headers: getAuthHeaders() });
        if (!response.ok) throw new Error(`HTTP Status Code: ${response.status}`);
        completeEventsCache = await response.json();
        renderEventsListView(completeEventsCache);
        loadEventsTabCounts();
    } catch (err) {
        console.error("Events fetch failed:", err);
        document.getElementById("events-list").innerHTML = `<p style="text-align:center; color:var(--accent-primary); padding:1.5rem;">Failed retrieving events ledger portfolio index.</p>`;
    }
}

// ---- Community Posts (Events Uploaded > Community Posts tab) ----
let communityPostsCache = [];

async function loadCommunityPosts() {
    const container = document.getElementById("community-posts-list");
    if (!container) return;
    container.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Loading…</p>`;
    try {
        const res = await fetch(`${API_BASE}/admin/community-posts`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const posts = await res.json();
        communityPostsCache = posts;
        renderCommunityPosts(posts);
        loadEventsTabCounts();
    } catch (err) {
        console.error("Failed loading community posts:", err);
        container.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Couldn't reach the server.</p>`;
    }
}

function renderCommunityPosts(posts) {
    const container = document.getElementById("community-posts-list");
    if (!container) return;
    if (!posts || !posts.length) {
        container.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">No community posts yet.</p>`;
        return;
    }
    container.innerHTML = posts.map(p => {
        const isVideo = p.media_url && String(p.media_url).match(/\.(mp4|webm|ogg|mov|m4v)($|\?)/i);
        return `
        <div class="list-item" data-post-id="${p.id}" style="cursor:default; ${p.revoked_at ? "opacity:0.55;" : ""}">
            <div style="display:flex; align-items:center; gap:1rem; flex:1; min-width:0;">
                <div class="media-viewport" style="width:70px; height:70px; margin:0; flex-shrink:0; cursor:pointer; position:relative;" onclick="openCommunityPostMedia('${p.id}')">
                    ${p.media_url ? (isVideo
                        ? `<video src="${resolveMediaUrl(p.media_url)}" muted preload="metadata"></video><div style="position:absolute; inset:0; display:flex; align-items:center; justify-content:center; background:rgba(0,0,0,0.25); font-size:1.4rem;">▶</div>`
                        : `<img src="${resolveMediaUrl(p.media_url)}">`)
                        : `<div style="width:100%; height:100%; display:flex; align-items:center; justify-content:center; color:var(--text-muted); font-size:0.65rem;">No media</div>`}
                </div>
                <div style="min-width:0;">
                    <h3 style="font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                        ${p.username || "@unknown"}
                        ${p.revoked_at
                            ? `<span style="font-size:0.62rem; color:#ff6b6b; font-weight:800; text-transform:uppercase; margin-left:0.4rem;">Revoked</span>`
                            : (p.seen_by_admin_at ? `<span style="font-size:0.62rem; color:var(--accent-success); font-weight:800; text-transform:uppercase; margin-left:0.4rem;">✓ Seen</span>` : `<span style="font-size:0.62rem; color:#ff9f43; font-weight:800; text-transform:uppercase; margin-left:0.4rem;">● New</span>`)}
                    </h3>
                    <p style="color:var(--text-muted); font-size:0.8rem; margin-top:0.2rem; white-space:nowrap; overflow:hidden; text-overflow:ellipsis; max-width:360px;">${p.caption || "No caption"}</p>
                    <p style="color:var(--text-muted); font-size:0.72rem; margin-top:0.2rem;">${p.location || p.county || "Unknown location"} • ${p.created_at ? new Date(p.created_at).toLocaleString() : ""}</p>
                </div>
            </div>
            <div style="text-align:right; flex-shrink:0; display:flex; flex-direction:column; gap:0.4rem; align-items:flex-end;">
                <button class="action-btn" style="width:auto; padding:0.4rem 0.9rem;" onclick="openCommunityPostMedia('${p.id}')">▶ Play</button>
                ${p.revoked_at
                    ? `<span style="font-size:0.72rem; color:var(--text-muted);">Removed ${new Date(p.revoked_at).toLocaleString()}</span>`
                    : `<button class="action-btn" style="width:auto; padding:0.4rem 0.9rem; background:rgba(255,80,80,0.12); color:#ff6b6b;" onclick="revokeCommunityPost('${p.id}')">Revoke</button>`
                }
            </div>
        </div>
    `;
    }).join("");

    // Marking seen: as soon as the row renders on-screen for an admin, log
    // it — mirrors "opening" a message the way the Events tab does.
    (posts || []).forEach(p => {
        if (!p.seen_by_admin_at && !p.revoked_at) {
            fetch(`${API_BASE}/admin/community-posts/${p.id}/mark-seen`, { method: "POST", headers: getAuthHeaders() }).catch(() => {});
        }
    });
}

// Full-size, actually-playable view of one community post so an admin can
// judge whether it's appropriate before deciding to revoke it.
function openCommunityPostMedia(postId) {
    const p = communityPostsCache.find(post => String(post.id) === String(postId));
    if (!p) return;

    const injector = document.getElementById("modal-injector-content");
    document.getElementById("global-overlay").classList.add("fullscreen-modal");
    const isVideo = p.media_url && String(p.media_url).match(/\.(mp4|webm|ogg|mov|m4v)($|\?)/i);

    injector.innerHTML = `
        <div>
            <h2 style="margin-bottom:0.25rem;">${p.username || "@unknown"}</h2>
            <p style="color:var(--text-muted); font-size:0.85rem;">${p.location || p.county || "Unknown location"} • ${p.created_at ? new Date(p.created_at).toLocaleString() : ""}</p>
            ${p.caption ? `<p style="margin-top:0.5rem; font-size:0.9rem;">${p.caption}</p>` : ""}
        </div>
        <div style="width:100%; max-height:70vh; border-radius:14px; overflow:hidden; background:#000; margin-top:1rem; display:flex; align-items:center; justify-content:center;">
            ${p.media_url
                ? (isVideo
                    ? `<video src="${resolveMediaUrl(p.media_url)}" controls autoplay playsinline style="width:100%; max-height:70vh; object-fit:contain;"></video>`
                    : `<img src="${resolveMediaUrl(p.media_url)}" style="width:100%; max-height:70vh; object-fit:contain;">`)
                : `<p style="color:var(--text-muted); padding:2rem;">No media attached to this post.</p>`}
        </div>
        ${!p.revoked_at ? `
        <button class="action-btn" style="margin-top:1rem; width:100%; background:rgba(255,80,80,0.12); color:#ff6b6b; border:1px solid rgba(255,80,80,0.3);" onclick="revokeCommunityPost('${p.id}'); closeGlobalModal();">
            🚫 Revoke — pull this off the Cheki feed
        </button>` : `<p style="margin-top:1rem; color:var(--text-muted); font-size:0.8rem;">Removed ${new Date(p.revoked_at).toLocaleString()}</p>`}
    `;
    document.getElementById("global-overlay").classList.add("active");
}

async function revokeCommunityPost(postId) {
    if (!confirm("Revoke this community post? It will be pulled off the Cheki feed.")) return;
    try {
        const res = await fetch(`${API_BASE}/admin/community-posts/${postId}/revoke`, { method: "POST", headers: getAuthHeaders() });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            alert(data.detail || "Couldn't revoke this post.");
            return;
        }
        loadCommunityPosts();
    } catch (err) {
        console.error("Failed to revoke community post:", err);
        alert("Couldn't reach the server.");
    }
}

function fmtDeadline(iso) {
    if (!iso) return "No deadline set";
    const d = new Date(iso);
    if (isNaN(d.getTime())) return "No deadline set";
    return d.toLocaleString("en-KE", { weekday: "short", day: "2-digit", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit" });
}

// Halted media markup used in both the list row and the expanded view.
function buildHaltedMediaMarkup(ev) {
    const isVideo = (ev.media_url || "").match(/\.(mp4|webm|ogg|mov|m4v)$/i);
    if (ev.media_url && isVideo) {
        return `<video src="${resolveMediaUrl(ev.media_url)}" preload="metadata" muted playsinline></video>`;
    }
    const img = ev.media_url ? resolveMediaUrl(ev.media_url) : "https://images.unsplash.com/photo-1516450360452-9312f5e86fc7?auto=format&fit=crop&w=800&q=80";
    return `<img src="${img}" alt="${ev.title} media preview">`;
}

function haltAnyVideosIn(container) {
    container.querySelectorAll("video").forEach(v => {
        v.pause();
        v.currentTime = 0;
        v.removeAttribute("autoplay");
    });
}

function renderEventsListView(events) {
    const container = document.getElementById("events-list");
    container.innerHTML = "";

    document.getElementById("metric-events-count").innerText = events.length;

    if (!events.length) {
        container.innerHTML = `<p style="text-align:center; color:var(--text-muted); padding: 1.5rem;">No matching platform configurations registered.</p>`;
        return;
    }

    events.forEach(ev => {
        const row = document.createElement("div");
        row.className = "list-item";
        row.innerHTML = `
            <div style="display:flex; align-items:center; gap:1rem; flex:1; min-width:0;">
                <div class="media-viewport" style="width:80px; height:80px; margin:0; flex-shrink:0; cursor:pointer;">
                    ${buildHaltedMediaMarkup(ev)}
                </div>
                <div style="min-width:0;">
                    <h3 style="font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                        ${ev.title}
                        ${ev.reviewed_at
                            ? `<span style="font-size:0.62rem; color:var(--accent-success); font-weight:800; text-transform:uppercase; margin-left:0.4rem; vertical-align:middle;">✓ Reviewed</span>`
                            : `<span style="font-size:0.62rem; color:#ff9f43; font-weight:800; text-transform:uppercase; margin-left:0.4rem; vertical-align:middle;">● New</span>`}
                    </h3>
                    <p style="color: var(--text-muted); font-size:0.8rem; margin-top:0.2rem;">${ev.host_name || "Unknown host"} • ${ev.host_email || "no email on file"}</p>
                    <p style="color: var(--text-muted); font-size:0.72rem; margin-top:0.2rem; font-family: monospace;">ID: ${ev.id}</p>
                </div>
            </div>
            <div style="text-align:right; flex-shrink:0;">
                <span style="color:var(--accent-success); font-weight:700; font-size:1.0rem;">KSh ${ev.price}</span>
                <p style="color:var(--text-muted); font-size:0.72rem; margin-top:0.25rem;">Deadline: ${fmtDeadline(ev.ticket_deadline)}</p>
            </div>
        `;
        row.onclick = () => openDetailedEventOverlay(ev);
        container.appendChild(row);
        haltAnyVideosIn(row);
    });
}

function handleEventSearch(e) {
    const term = e.target.value.toLowerCase();
    const filtered = completeEventsCache.filter(ev => ev.title.toLowerCase().includes(term));
    renderEventsListView(filtered);
}

// ---- Expand-to-fill detail view (reuses existing .fullscreen-modal / .detail CSS) ----
async function openDetailedEventOverlay(event) {
    currentDetailedEventId = event.id;
    const injector = document.getElementById("modal-injector-content");
    const overlay = document.getElementById("global-overlay");

    let telemetry = { tickets_sold: 0, remaining_seats: event.capacity };
    try {
        const telemetryRes = await fetch(`${API_BASE}/admin/events/${event.id}/analytics`, { headers: getAuthHeaders() });
        if (telemetryRes.ok) telemetry = await telemetryRes.json();
    } catch (e) {
        console.warn("Failed retrieving dynamic analytical fields context hooks", e);
    }

    let finalList = { final_list_locked_at: null, confirmed_count: 0, confirmed_amount: 0, gate_unlocked: false, tickets_sent_at: null };
    try {
        const finalListRes = await fetch(`${API_BASE}/admin/events/${event.id}/final-list`, { headers: getAuthHeaders() });
        if (finalListRes.ok) finalList = await finalListRes.json();
    } catch (e) {
        console.warn("Failed retrieving final list state", e);
    }

    injector.innerHTML = `
        <div>
            <h2 style="margin-bottom:0.25rem;">${event.title}${event.status === "revoked" ? ' <span style="font-size:0.7rem; color:#ff6b6b; text-transform:uppercase; font-weight:800; vertical-align:middle;">Revoked</span>' : ""}</h2>
            <p style="color:var(--text-muted); font-size:0.9rem;">Host: ${event.host_name || "Unknown"} (${event.host_email || "no email"})</p>
            <p style="color:var(--text-muted); font-size:0.8rem; font-family: monospace; margin-top:0.25rem;">Event ID: ${event.id}</p>
            <p id="event-reviewed-readout" style="font-size:0.78rem; color:${event.reviewed_at ? "var(--accent-success)" : "#ff9f43"}; margin-top:0.35rem; font-weight:700;">
                ${event.reviewed_at ? `✓ Reviewed ${new Date(event.reviewed_at).toLocaleString()}` : "● Not reviewed yet"}
            </p>
        </div>

        <div class="media-viewport" onclick="toggleMediaPresentation(this)">
            ${buildHaltedMediaMarkup(event)}
            <div class="media-badge">KSh ${event.price}</div>
        </div>

        <button id="revoke-event-btn" class="action-btn" style="margin-top:1rem; width:100%; background:rgba(255,80,80,0.12); color:#ff6b6b; border:1px solid rgba(255,80,80,0.3);" ${event.status === "revoked" ? "disabled" : ""}>
            ${event.status === "revoked" ? "✓ Event revoked — removed from platform" : "🚫 Revoke Event — remove from everywhere"}
        </button>

        <div style="display:grid; grid-template-columns: 1fr 1fr; gap:1rem; background:rgba(0,0,0,0.2); padding:1.25rem; border-radius:12px; margin-top:1rem;">
            <div>
                <p style="color:var(--text-muted); font-size:0.8rem; text-transform:uppercase;">Remaining Availability</p>
                <p style="font-size:1.5rem; font-weight:800; color:var(--accent-primary);">${telemetry.remaining_seats !== null ? telemetry.remaining_seats : 'Open Entry'}</p>
            </div>
            <div>
                <p style="color:var(--text-muted); font-size:0.8rem; text-transform:uppercase;">Tickets Claimed</p>
                <p style="font-size:1.5rem; font-weight:800; color:var(--text-main);">${telemetry.tickets_sold}</p>
            </div>
            <div style="grid-column: span 2;">
                <p style="color:var(--text-muted); font-size:0.8rem; text-transform:uppercase;">Ticket Deadline <span style="font-weight:400; text-transform:none; opacity:0.7;">(FYI notification only — doesn't stop sales)</span></p>
                <p style="font-size:1.1rem; font-weight:700; color:var(--text-main);">${fmtDeadline(event.ticket_deadline)}</p>
            </div>
            <div style="grid-column: span 2; border-top:1px solid rgba(255,255,255,0.06); padding-top:0.85rem; margin-top:0.15rem;">
                <p style="color:var(--text-muted); font-size:0.8rem; text-transform:uppercase;">Ticket Sales Status</p>
                <p id="sales-status-readout" style="font-size:1rem; font-weight:700;">—</p>
            </div>
        </div>
        <p style="font-size:0.7rem; color:var(--text-muted); margin-top:0.5rem;">Sales close automatically 2 hours before the event starts — no admin action needed. The deadline above just sends the host a heads-up notification when it passes.</p>

        <!-- Attendance final list — the confirmed-going list frozen an hour
             before the event start (T-1). This is fully automatic now:
             both a scheduled sweep AND an on-demand check (whenever the
             event is viewed) freeze the list and open the Live Gate — no
             admin action, manual override, or button exists for this. -->
        <div style="margin-top:1.5rem; background:rgba(0,0,0,0.2); padding:1.25rem; border-radius:12px;">
            <p style="color:var(--text-muted); font-size:0.8rem; text-transform:uppercase; margin-bottom:0.5rem;">Attendance Final List <span style="font-weight:400; text-transform:none; opacity:0.7;">(auto-sent 1hr before event start)</span></p>
            ${finalList.final_list_locked_at
                ? `<p style="font-size:0.85rem; color:var(--text-main);">Locked ${new Date(finalList.final_list_locked_at).toLocaleString()} · <strong>${finalList.confirmed_count}</strong> confirmed · KSh ${Number(finalList.confirmed_amount || 0).toLocaleString()}</p>`
                : `<p style="font-size:0.85rem; color:var(--text-muted);">Not frozen yet — locks and sends automatically an hour before the event starts.</p>`
            }
            ${finalList.still_pending_response ? `<p style="font-size:0.75rem; color:var(--text-muted); margin-top:0.25rem;">${finalList.still_pending_response} buyers still haven't responded to the attendance check.</p>` : ""}
            <p id="send-tickets-status" style="margin-top:0.85rem; font-size:0.85rem; font-weight:700; ${finalList.gate_unlocked ? "color:var(--accent-success);" : "color:var(--text-muted);"}">
                ${finalList.gate_unlocked
                    ? `✓ Live Gate unlocked ${finalList.tickets_sent_at ? "· " + new Date(finalList.tickets_sent_at).toLocaleString() : ""}`
                    : "Pending — will open automatically at T-1hr"}
            </p>
        </div>
    `;

    overlay.classList.add("active", "fullscreen-modal");
    haltAnyVideosIn(injector);
    bindSalesStatusReadout(event.start_date);

    // Opening an event's detail is what "reviewing" it means here — mark it
    // reviewed the first time an admin looks at it, same as a message
    // getting marked read by opening it.
    if (!event.reviewed_at) {
        fetch(`${API_BASE}/admin/events/${event.id}/mark-reviewed`, { method: "POST", headers: getAuthHeaders() })
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (!data) return;
                event.reviewed_at = data.reviewed_at;
                const readout = document.getElementById("event-reviewed-readout");
                if (readout) {
                    readout.style.color = "var(--accent-success)";
                    readout.textContent = `✓ Reviewed ${new Date(data.reviewed_at).toLocaleString()}`;
                }
                loadEventsTabCounts();
                refreshSidebarBadges();
            })
            .catch(err => console.warn("Failed to mark event reviewed:", err));
    }

    const revokeBtn = document.getElementById("revoke-event-btn");
    if (revokeBtn && event.status !== "revoked") {
        revokeBtn.onclick = async () => {
            const reason = prompt(`Revoke "${event.title}"? This removes it from ticket sales, the Cheki feed, and the host's dashboard, and fully refunds any buyers who already paid.\n\nOptional reason (shown to the host and buyers):`, "");
            if (reason === null) return; // cancelled
            revokeBtn.disabled = true;
            revokeBtn.textContent = "Revoking…";
            try {
                const res = await fetch(`${API_BASE}/admin/events/${event.id}/revoke${reason ? `?reason=${encodeURIComponent(reason)}` : ""}`, {
                    method: "POST",
                    headers: getAuthHeaders(),
                });
                const data = await res.json().catch(() => ({}));
                if (!res.ok) {
                    alert(data.detail || "Couldn't revoke this event.");
                    revokeBtn.disabled = false;
                    revokeBtn.textContent = "🚫 Revoke Event — remove from everywhere";
                    return;
                }
                revokeBtn.textContent = "✓ Event revoked — removed from platform";
                revokeBtn.style.background = "rgba(255,80,80,0.2)";
                alert(`Revoked. ${data.refunded_bookings} buyer(s) refunded a total of KSh ${Number(data.refunded_total || 0).toLocaleString()}.`);
                fetchAllPlatformEvents();

                // Jump straight to Refunds > Requested for this event so the
                // admin sees who's owed money and the number to pay them on,
                // instead of having to go find it themselves.
                closeGlobalModal();
                currentRefundsTab = 'requested';
                const refundsNavBtn = document.querySelector('.suite-sidebar .nav-btn[onclick*="refunds"]');
                switchPage('refunds', refundsNavBtn);
                openRefundEventDetail(event.id);
            } catch (err) {
                console.error("revoke-event failed:", err);
                alert("Couldn't reach the server to revoke this event.");
                revokeBtn.disabled = false;
                revokeBtn.textContent = "🚫 Revoke Event — remove from everywhere";
            }
        };
    }
}

// ---- Interactive deadline button: strict lockout while counting down, instant
function bindSalesStatusReadout(startDateIso) {
    if (deadlineCountdownTimer) { clearInterval(deadlineCountdownTimer); deadlineCountdownTimer = null; }

    const el = document.getElementById("sales-status-readout");
    if (!el) return;

    const startMs = startDateIso ? new Date(startDateIso).getTime() : NaN;
    const closeMs = startMs - (2 * 60 * 60 * 1000); // T-2

    if (isNaN(startMs)) {
        el.textContent = "No start time on record";
        el.style.color = "var(--text-muted)";
        return;
    }

    const tick = () => {
        const now = Date.now();
        if (now >= closeMs) {
            el.textContent = "🔒 Closed — sales ended 2h before the event";
            el.style.color = "#ff6b6b";
            clearInterval(deadlineCountdownTimer);
            deadlineCountdownTimer = null;
            return;
        }
        const diff = closeMs - now;
        const d = Math.floor(diff / 86400000);
        const h = Math.floor((diff % 86400000) / 3600000);
        const m = Math.floor((diff % 3600000) / 60000);
        const s = Math.floor((diff % 60000) / 1000);
        const pad = (n) => String(n).padStart(2, "0");
        el.textContent = `✓ Open — closes automatically in ${d}d ${pad(h)}h ${pad(m)}m ${pad(s)}s`;
        el.style.color = "var(--accent-success)";
    };

    tick();
    deadlineCountdownTimer = setInterval(tick, 1000);
}

function toggleMediaPresentation(element) {
    element.classList.toggle('fullscreen-media');
    const video = element.querySelector('video');
    if (video) {
        if (element.classList.contains('fullscreen-media')) {
            video.play();
            video.muted = false;
        } else {
            video.pause();
            video.currentTime = 0;
            video.muted = true;
        }
    }
}

// ==========================================
function adminLogout() {
    if (!confirm("Log out of the admin panel?")) return;
    localStorage.removeItem("bashAdminAccessToken");
    localStorage.removeItem("bashToken");
    sessionStorage.removeItem("financeUnlocked");
    window.location.href = "index.html";
}

// ==========================================
function openFinancialsGate() {
    const gate = document.getElementById("financials-gate");
    const content = document.getElementById("financials-content");
    const form = document.getElementById("financials-gate-form");
    const errorEl = document.getElementById("financials-gate-error");
    if (!gate || !content || !form) return;

    // Already unlocked earlier this session — skip straight to the cards.
    if (sessionStorage.getItem("financeUnlocked") === "true") {
        gate.style.display = "none";
        content.style.display = "block";
        return;
    }

    gate.style.display = "block";
    content.style.display = "none";
    errorEl.style.display = "none";

    form.onsubmit = async (e) => {
        e.preventDefault();
        const password = document.getElementById("financials-gate-password").value;
        const submitBtn = form.querySelector("button[type=submit]");
        submitBtn.disabled = true;
        submitBtn.textContent = "Checking…";
        errorEl.style.display = "none";

        try {
            const res = await fetch(`${API_BASE}/admin/financials/verify-password`, {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({ password }),
            });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                errorEl.textContent = res.status === 403
                    ? "Your account isn't cleared for financial access yet — ask another verified admin to grant it."
                    : (data.detail || "Incorrect password.");
                errorEl.style.display = "block";
                submitBtn.disabled = false;
                submitBtn.textContent = "Unlock Financials";
                return;
            }
            sessionStorage.setItem("financeUnlocked", "true");
            gate.style.display = "none";
            content.style.display = "block";
        } catch (err) {
            console.error("Financials gate check failed:", err);
            errorEl.textContent = "Couldn't reach the server.";
            errorEl.style.display = "block";
            submitBtn.disabled = false;
            submitBtn.textContent = "Unlock Financials";
        }
    };
}

// ==========================================
let cutoEntriesCache = [];
let cutoActiveAdminId = null;

async function openCutoActivityLog() {
    const injector = document.getElementById("modal-injector-content");
    document.getElementById("global-overlay").classList.add("fullscreen-modal");
    injector.innerHTML = `
        <div class="wa-shell" style="height: calc(100vh - 110px);">
            <aside class="wa-sidebar">
                <div class="wa-sidebar-head">Admins</div>
                <div id="cuto-admin-list" class="wa-sidebar-list">
                    <p style="text-align:center; color:var(--text-muted); font-size:0.75rem; padding:1rem 0.5rem;">Loading…</p>
                </div>
            </aside>
            <div class="wa-main">
                <div class="wa-main-head" id="cuto-main-head">Select an admin</div>
                <div id="cuto-main-body" class="wa-main-body">
                    <p class="wa-main-empty">Pick an admin on the left to see everything they've done — payouts, revokes, broadcasts, refunds — with the date and time of each.</p>
                </div>
            </div>
        </div>
    `;
    document.getElementById("global-overlay").classList.add("active");

    try {
        const res = await fetch(`${API_BASE}/admin/financials/activity?limit=500`, { headers: getAuthHeaders() });
        const data = await res.json();
        const listEl = document.getElementById("cuto-admin-list");
        if (!res.ok) {
            listEl.innerHTML = `<p style="color:#ff6b6b; padding:1rem;">${data.detail || "Couldn't load the activity log."}</p>`;
            return;
        }

        cutoEntriesCache = data.entries || [];

        // Group by admin so the sidebar is one row per admin, WhatsApp-style.
        const byAdmin = {};
        cutoEntriesCache.forEach(e => {
            if (!byAdmin[e.admin_id]) byAdmin[e.admin_id] = { admin_id: e.admin_id, admin_name: e.admin_name, count: 0, latest: e.created_at };
            byAdmin[e.admin_id].count += 1;
        });
        const payoutsByAdmin = data.payouts_by_admin || {};
        const admins = Object.values(byAdmin).sort((a, b) => new Date(b.latest) - new Date(a.latest));

        if (!admins.length) {
            listEl.innerHTML = `<p style="color:var(--text-muted); padding:1rem;">No admin activity logged yet.</p>`;
            return;
        }

        listEl.innerHTML = admins.map(a => {
            const initials = (a.admin_name || "A").trim().split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase();
            const payout = payoutsByAdmin[a.admin_id];
            return `
            <div class="wa-sidebar-row" data-admin-id="${a.admin_id}" onclick="selectCutoAdmin('${a.admin_id}')">
                <div class="wa-sidebar-avatar">${initials}</div>
                <div class="wa-sidebar-meta">
                    <div class="wa-sidebar-name">${a.admin_name}</div>
                    <div class="wa-sidebar-sub">${payout ? `KSh ${payout.total_paid_out.toLocaleString()} paid out` : new Date(a.latest).toLocaleString()}</div>
                </div>
                <div class="wa-sidebar-badge">${a.count}</div>
            </div>`;
        }).join("");

        if (admins[0]) selectCutoAdmin(admins[0].admin_id);
    } catch (e) {
        console.error("Cuto activity log failed:", e);
        document.getElementById("cuto-admin-list").innerHTML = `<p style="color:#ff6b6b; padding:1rem;">Couldn't reach the server.</p>`;
    }
}

function selectCutoAdmin(adminId) {
    cutoActiveAdminId = adminId;
    document.querySelectorAll("#cuto-admin-list .wa-sidebar-row").forEach(row => {
        row.classList.toggle("active", row.dataset.adminId === adminId);
    });

    const entries = cutoEntriesCache.filter(e => e.admin_id === adminId);
    const head = document.getElementById("cuto-main-head");
    const body = document.getElementById("cuto-main-body");
    if (!entries.length) {
        if (head) head.textContent = "Admin activity";
        if (body) body.innerHTML = `<p class="wa-main-empty">No activity for this admin yet.</p>`;
        return;
    }
    if (head) head.textContent = `${entries[0].admin_name} — every logged action`;
    if (body) {
        body.innerHTML = entries.map(e => `
            <div style="border-left:3px solid var(--accent-primary); padding:0.5rem 0 0.5rem 0.9rem; margin-bottom:0.75rem;">
                <div style="display:flex; justify-content:space-between; font-size:0.8rem;">
                    <strong>${(e.action || "").replace(/_/g, " ")}</strong>
                    <span style="color:var(--text-muted); font-family:monospace; font-size:0.7rem;">${e.created_at ? new Date(e.created_at).toLocaleString() : ""}</span>
                </div>
                <p style="font-size:0.8rem; color:var(--text-muted); margin-top:0.15rem;">${e.detail || ""}${e.amount ? ` · KSh ${Number(e.amount).toLocaleString()}` : ""}</p>
            </div>
        `).join("");
    }
}

// ==========================================
async function openFinancialDetail(type) {
    const injector = document.getElementById("modal-injector-content");
    document.getElementById("global-overlay").classList.add("fullscreen-modal");

    if (type === 'host') {
        injector.innerHTML = `<h2>Host Settlement Distributions</h2><p style="color:var(--text-muted); margin-bottom:1.5rem;">Every payout that's been sent, grouped by host — click one to see the M-Pesa code as proof.</p><div id="host-financials-loading" style="display:flex; flex-direction:column; gap:1rem;"></div>`;
        document.getElementById("global-overlay").classList.add("active");

        try {
            const res = await fetch(`${API_BASE}/admin/withdrawals/paid`, { headers: getAuthHeaders() });
            const paid = await res.json();
            const targetList = document.getElementById("host-financials-loading");
            targetList.innerHTML = "";

            if (!Array.isArray(paid) || !paid.length) {
                targetList.innerHTML = `<p style="color:var(--text-muted);">No settled payouts yet.</p>`;
                return;
            }

            // Group by host for the summary row, but keep each event's line
            const byHost = {};
            paid.forEach(w => {
                const key = w.host_id;
                if (!byHost[key]) byHost[key] = { name: w.host_name || w.host_username, email: w.host_email, total: 0, items: [] };
                byHost[key].total += Number(w.host_payout_amount || 0);
                byHost[key].items.push(w);
            });

            Object.values(byHost).forEach(h => {
                const block = document.createElement("div");
                block.style = "background:rgba(0,0,0,0.2); padding:1rem; border-radius:12px; cursor:pointer;";
                block.innerHTML = `
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div style="text-align:left;">
                            <strong>${h.name}</strong>
                            <p style="font-size:0.8rem; color:var(--text-muted);">${h.email}</p>
                        </div>
                        <span style="color:var(--accent-success); font-weight:700;">KSh ${h.total.toLocaleString()}</span>
                    </div>
                `;
                block.onclick = () => showPayoutProof(h.items);
                targetList.appendChild(block);
            });
        } catch (e) { console.error(e); }

    } else if (type === 'company') {
        injector.innerHTML = `<h2>Company Revenue Engine</h2><p style="color:var(--text-muted); margin-bottom:1.5rem;">Our 12% cut from every settled payout — click one for the M-Pesa proof.</p><div id="company-financials-loading" style="text-align:center; font-size:2rem; font-weight:800; color:var(--accent-success); margin-bottom:1.5rem;">KSh 0.00</div><div id="company-hosts-list" style="display:flex; flex-direction:column; gap:0.75rem;"></div>`;
        document.getElementById("global-overlay").classList.add("active");

        try {
            const res = await fetch(`${API_BASE}/admin/withdrawals/paid`, { headers: getAuthHeaders() });
            const paid = await res.json();
            const totalCut = (Array.isArray(paid) ? paid : []).reduce((sum, w) => sum + Number(w.platform_cut || 0), 0);
            document.getElementById("company-financials-loading").innerText = `KSh ${totalCut.toLocaleString(undefined, { minimumFractionDigits: 2 })}`;

            const dynamicList = document.getElementById("company-hosts-list");
            dynamicList.innerHTML = "";
            if (!Array.isArray(paid) || !paid.length) {
                dynamicList.innerHTML = `<p style="color:var(--text-muted);">No settled payouts yet.</p>`;
                return;
            }
            paid.forEach(w => {
                const item = document.createElement("div");
                item.style = "background:rgba(0,0,0,0.2); padding:1rem; border-radius:12px; display:flex; justify-content:space-between; align-items:center; cursor:pointer;";
                item.innerHTML = `
                    <div style="text-align:left;">
                        <strong>${w.event_title || "Untitled event"}</strong>
                        <p style="font-size:0.75rem; color:var(--text-muted);">${w.host_name || w.host_username} · ${w.paid_at ? new Date(w.paid_at).toLocaleString() : ""}</p>
                    </div>
                    <span style="color:var(--accent-primary); font-weight:700;">KSh ${Number(w.platform_cut || 0).toLocaleString()}</span>
                `;
                item.onclick = () => showPayoutProof([w]);
                dynamicList.appendChild(item);
            });
        } catch (e) { console.error(e); }
    }
}

// Shared detail view for a settled payout (or a host's full list of them):
function showPayoutProof(items) {
    const injector = document.getElementById("modal-injector-content");
    injector.innerHTML = `
        <h2>Payout Proof</h2>
        <div style="display:flex; flex-direction:column; gap:1rem; margin-top:1rem;">
            ${items.map(w => `
                <div style="background:rgba(0,0,0,0.25); border-radius:14px; padding:1.1rem;">
                    <strong>${w.event_title || "Untitled event"}</strong>
                    <p style="font-size:0.78rem; color:var(--text-muted); margin-top:0.2rem;">${w.host_name || w.host_username} · ${w.paid_at ? new Date(w.paid_at).toLocaleString() : "—"}</p>
                    <div style="display:grid; grid-template-columns:repeat(2,1fr); gap:0.5rem; margin-top:0.75rem;">
                        <div><p style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase;">M-Pesa Code (Proof)</p><p style="font-weight:700; font-family:monospace;">${w.mpesa_code || "—"}</p></div>
                        <div><p style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase;">Our 12% Cut</p><p style="font-weight:700; color:var(--accent-primary);">KSh ${Number(w.platform_cut || 0).toLocaleString()}</p></div>
                        <div><p style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase;">Host Total Output</p><p style="font-weight:700; color:var(--accent-success);">KSh ${Number(w.host_payout_amount || 0).toLocaleString()}</p></div>
                        <div><p style="font-size:0.65rem; color:var(--text-muted); text-transform:uppercase;">Gross Revenue</p><p style="font-weight:700;">KSh ${Number(w.gross_revenue || 0).toLocaleString()}</p></div>
                    </div>
                </div>
            `).join("")}
        </div>
        <button class="action-btn" style="margin-top:1.25rem; width:100%;" onclick="openFinancialDetail('host')">← Back</button>
    `;
}

// ==========================================
// MANUAL PAYMENTS — admin page: mode toggle, pending-claims list, batch
// code matching, and a force-match override for edge cases. Mirrors the
// Technical Difficulties switch pattern above.
function renderManualPayState(data) {
    const label = document.getElementById("manualpay-status-label");
    const updated = document.getElementById("manualpay-status-updated");
    const card = document.getElementById("manualpay-status-card");
    const btn = document.getElementById("manualpay-toggle-btn");
    if (!label || !btn) return;

    const isOn = !!data.manual_payment_mode;
    label.textContent = isOn ? "🔁 ON — manual payment mode" : "✅ OFF — STK push as normal";
    label.style.color = isOn ? "#ff2d95" : "var(--neon-gold, #3ddc97)";
    if (card) card.style.borderColor = isOn ? "#ff2d95" : "var(--border-color, rgba(255,255,255,0.08))";
    const updatedAt = data.manual_payment_mode_updated_at;
    if (updated) updated.textContent = updatedAt ? `Last changed ${new Date(updatedAt).toLocaleString()}` : "";
    btn.textContent = isOn ? "Turn OFF — back to STK" : "Turn ON — manual payments";
    btn.className = isOn ? "action-btn btn-reject" : "action-btn btn-approve";
    btn.disabled = false;
}

async function initManualPaymentsPage() {
    const btn = document.getElementById("manualpay-toggle-btn");
    if (btn) { btn.disabled = true; btn.textContent = "Loading…"; }
    try {
        const res = await fetch(`${API_BASE}/admin/platform-settings`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Couldn't load status");
        const data = await res.json();
        renderManualPayState(data);
    } catch (err) {
        console.error("Couldn't load manual payment mode status:", err);
        const label = document.getElementById("manualpay-status-label");
        if (label) label.textContent = "Couldn't load — try reopening this page.";
        if (btn) { btn.disabled = false; btn.textContent = "Retry"; btn.onclick = initManualPaymentsPage; }
    }
    loadManualPaymentsPending();
}

async function toggleManualPaymentMode() {
    const btn = document.getElementById("manualpay-toggle-btn");
    const msg = document.getElementById("manualpay-toggle-msg");
    if (btn) { btn.disabled = true; btn.textContent = "Updating…"; }
    if (msg) msg.textContent = "";
    try {
        const res = await fetch(`${API_BASE}/admin/platform-settings/toggle-manual-payment-mode`, {
            method: "POST",
            headers: getAuthHeaders(),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "Couldn't update the switch.");
        }
        const data = await res.json();
        renderManualPayState(data);
        if (msg) {
            msg.textContent = data.manual_payment_mode
                ? "Live: buyers now see the Till + code entry instead of an STK prompt."
                : "Live: back to normal — STK push is used first again (still falls back to manual per-booking on failure).";
        }
    } catch (err) {
        console.error("Toggle failed:", err);
        if (msg) { msg.style.color = "#ff2d95"; msg.textContent = err.message || "Couldn't reach the server."; }
        initManualPaymentsPage();
    }
}

// ==========================================
// REFERRAL GATE — off by default. Mirrors the Manual Payment Mode
// pattern exactly (see above). When off, booking a free event costs
// nothing (no referral credit spend), and referral.js's isLocked()
// always returns false — no padlocks show anywhere. Turning it on
// brings back the original credit-per-booking mechanic exactly as it was.
function renderReferralGateState(data) {
    const label = document.getElementById("referralgate-status-label");
    const updated = document.getElementById("referralgate-status-updated");
    const card = document.getElementById("referralgate-status-card");
    const btn = document.getElementById("referralgate-toggle-btn");
    if (!label || !btn) return;

    const isOn = !!data.referral_gate_enabled;
    label.textContent = isOn ? "🔒 ON — free events cost a referral credit" : "🎁 OFF — free events are simply bookable";
    label.style.color = isOn ? "#ff2d95" : "var(--neon-gold, #3ddc97)";
    if (card) card.style.borderColor = isOn ? "#ff2d95" : "var(--border-color, rgba(255,255,255,0.08))";
    const updatedAt = data.referral_gate_enabled_updated_at;
    if (updated) updated.textContent = updatedAt ? `Last changed ${new Date(updatedAt).toLocaleString()}` : "";
    btn.textContent = isOn ? "Turn OFF — free events unrestricted" : "Turn ON — require referral credits";
    btn.className = isOn ? "action-btn btn-reject" : "action-btn btn-approve";
    btn.disabled = false;
}

async function initReferralGatePage() {
    const btn = document.getElementById("referralgate-toggle-btn");
    if (btn) { btn.disabled = true; btn.textContent = "Loading…"; }
    try {
        const res = await fetch(`${API_BASE}/admin/platform-settings`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Couldn't load status");
        const data = await res.json();
        renderReferralGateState(data);
    } catch (err) {
        console.error("Couldn't load referral gate status:", err);
        const label = document.getElementById("referralgate-status-label");
        if (label) label.textContent = "Couldn't load — try reopening this page.";
        if (btn) { btn.disabled = false; btn.textContent = "Retry"; btn.onclick = initReferralGatePage; }
    }
}

async function toggleReferralGate() {
    const btn = document.getElementById("referralgate-toggle-btn");
    const msg = document.getElementById("referralgate-toggle-msg");
    if (btn) { btn.disabled = true; btn.textContent = "Updating…"; }
    if (msg) msg.textContent = "";
    try {
        const res = await fetch(`${API_BASE}/admin/platform-settings/toggle-referral-gate`, {
            method: "POST",
            headers: getAuthHeaders(),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "Couldn't update the switch.");
        }
        const data = await res.json();
        renderReferralGateState(data);
        if (msg) {
            msg.textContent = data.referral_gate_enabled
                ? "Live: free events now require a referral credit again, and padlocks are back."
                : "Live: free events are unrestricted — no credits, no padlocks anywhere.";
        }
    } catch (err) {
        console.error("Toggle failed:", err);
        if (msg) { msg.style.color = "#ff2d95"; msg.textContent = err.message || "Couldn't reach the server."; }
        initReferralGatePage();
    }
}

async function loadManualPaymentsPending() {
    const list = document.getElementById("manualpay-pending-list");
    const countEl = document.getElementById("manualpay-pending-count");
    if (!list) return;
    list.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Loading…</p>`;
    try {
        const res = await fetch(`${API_BASE}/admin/manual-payments/pending`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Couldn't load pending manual payments");
        const data = await res.json();
        const rows = data.pending || [];
        if (countEl) countEl.textContent = rows.length;
        if (!rows.length) {
            list.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Nothing waiting right now.</p>`;
            return;
        }
        list.innerHTML = rows.map(r => `
            <div class="list-item" style="display:block; padding:0.9rem 1rem;">
                <div style="display:flex; justify-content:space-between; align-items:flex-start; gap:0.75rem;">
                    <div>
                        <p style="font-weight:600;">${escapeHtmlAdmin(r.event_title || 'Event')}</p>
                        <p style="font-size:0.78rem; color:var(--text-muted); margin-top:0.15rem;">
                            ${escapeHtmlAdmin(r.buyer_name || r.buyer_username || 'Buyer')} · Ref ${escapeHtmlAdmin(r.booking_reference || '')} · KES ${Number(r.amount || 0).toLocaleString()}
                        </p>
                        <p style="font-size:0.78rem; color:var(--text-muted); margin-top:0.15rem;">
                            Status: ${r.status === 'awaiting_admin_match' ? 'Buyer submitted a code — waiting on a match' : 'Waiting on the buyer to pay & submit a code'}
                        </p>
                        ${r.buyer_claimed_code ? `<p style="font-size:0.78rem; margin-top:0.15rem;">Claimed code: <strong>${escapeHtmlAdmin(r.buyer_claimed_code)}</strong></p>` : ''}
                        ${r.buyer_claimed_raw_message ? `<p style="font-size:0.72rem; color:var(--text-muted); margin-top:0.15rem; word-break:break-word;">"${escapeHtmlAdmin(r.buyer_claimed_raw_message)}"</p>` : ''}
                    </div>
                    ${r.status === 'awaiting_admin_match' ? `<button class="action-btn btn-approve" style="width:auto; padding:0 1rem; white-space:nowrap;" onclick="submitManualPaymentForceMatch('${r.payment_id}')">Force Match</button>` : ''}
                </div>
                <p id="manualpay-force-msg-${r.payment_id}" style="font-size:0.75rem; color:var(--text-muted); margin-top:0.4rem;"></p>
            </div>
        `).join("");
    } catch (err) {
        console.error("Failed loading manual payments:", err);
        list.innerHTML = `<p style="padding:1rem; color:#ff2d95;">Couldn't load — try again.</p>`;
    }
}

async function submitManualPaymentBatchMatch() {
    const input = document.getElementById("manualpay-batch-input");
    const btn = document.getElementById("manualpay-batch-btn");
    const msg = document.getElementById("manualpay-batch-msg");
    const raw = (input && input.value || "").trim();
    if (!raw) {
        if (msg) { msg.style.color = "#ff2d95"; msg.textContent = "Paste at least one code or confirmation message first."; }
        return;
    }
    if (btn) { btn.disabled = true; btn.textContent = "Matching…"; }
    if (msg) { msg.style.color = "var(--text-muted)"; msg.textContent = ""; }
    try {
        const res = await fetch(`${API_BASE}/admin/manual-payments/batch-match`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ raw_text: raw }),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "Couldn't match those codes.");
        }
        const data = await res.json();
        if (msg) {
            msg.style.color = "var(--neon-gold, #3ddc97)";
            msg.textContent = `Matched ${data.matched_count} booking(s) — issued their tickets. ${data.pooled_count} code(s) parked, waiting on a buyer claim.`;
        }
        if (input) input.value = "";
        loadManualPaymentsPending();
    } catch (err) {
        console.error("Batch match failed:", err);
        if (msg) { msg.style.color = "#ff2d95"; msg.textContent = err.message || "Couldn't reach the server."; }
    } finally {
        if (btn) { btn.disabled = false; btn.textContent = "Match Codes"; }
    }
}

async function submitManualPaymentForceMatch(paymentId) {
    const msgEl = document.getElementById(`manualpay-force-msg-${paymentId}`);
    const note = prompt("Force-match this claim as paid?\n\nOptional note (e.g. why it didn't auto-match):", "");
    if (note === null) return; // cancelled
    if (msgEl) { msgEl.style.color = "var(--text-muted)"; msgEl.textContent = "Matching…"; }
    try {
        const res = await fetch(`${API_BASE}/admin/manual-payments/${paymentId}/force-match`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ admin_note: note || null }),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "Couldn't force-match this claim.");
        }
        loadManualPaymentsPending();
    } catch (err) {
        console.error("Force match failed:", err);
        if (msgEl) { msgEl.style.color = "#ff2d95"; msgEl.textContent = err.message || "Couldn't reach the server."; }
    }
}

function escapeHtmlAdmin(s) {
    return String(s ?? '').replace(/[&<>"']/g, m => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m]));
}

// ==========================================
// DUPLICATE GUARD — admin review queue for submitted verification photos.
// ==========================================
// ADDER — direct admin add for platform-wide categories/towns/locations.
// No approval queue — only admins can reach this page, so nothing here
// needs review before going live for everyone.
let adderActiveFilter = 'category';
let adderAllEntries = [];

function initAdderPage() {
    const typeSelect = document.getElementById("adder-entry-type");
    if (typeSelect && !typeSelect.dataset.wired) {
        typeSelect.dataset.wired = "1";
        typeSelect.addEventListener("change", () => {
            const row = document.getElementById("adder-parent-town-row");
            if (row) row.style.display = typeSelect.value === "location" ? "block" : "none";
        });
    }
    loadAdderList();
}

function switchAdderFilter(type, btn) {
    adderActiveFilter = type;
    document.querySelectorAll('[data-adder-filter]').forEach(b => b.classList.toggle('active', b === btn));
    renderAdderList();
}

async function loadAdderList() {
    const list = document.getElementById("adder-list");
    if (!list) return;
    list.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Loading…</p>`;
    try {
        const res = await fetch(`${API_BASE}/admin/taxonomy`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Couldn't load the list");
        const data = await res.json();
        adderAllEntries = data.entries || [];
        renderAdderList();
    } catch (err) {
        console.error("Failed loading Adder list:", err);
        list.innerHTML = `<p style="padding:1rem; color:#ff2d95;">Couldn't load — try again.</p>`;
    }
}

function renderAdderList() {
    const list = document.getElementById("adder-list");
    if (!list) return;
    const rows = adderAllEntries.filter(e => e.entry_type === adderActiveFilter);
    if (!rows.length) {
        list.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Nothing added here yet.</p>`;
        return;
    }
    list.innerHTML = rows.map(r => `
        <div class="list-item" style="display:flex; align-items:center; justify-content:space-between; padding:0.85rem 1rem;">
            <div>
                <p style="font-weight:600;">${escapeHtmlAdmin(r.value)}</p>
                ${r.parent_town ? `<p style="font-size:0.75rem; color:var(--text-muted); margin-top:0.15rem;">in ${escapeHtmlAdmin(r.parent_town)}</p>` : ''}
            </div>
            <button class="action-btn btn-reject" style="width:auto; padding:0 1rem;" onclick="deleteAdderEntry('${r.id}')">Remove</button>
        </div>
    `).join("");
}

async function submitAdderEntry() {
    const entryType = document.getElementById("adder-entry-type").value;
    const valueInput = document.getElementById("adder-value");
    const parentTownInput = document.getElementById("adder-parent-town");
    const msg = document.getElementById("adder-submit-msg");
    const btn = document.getElementById("adder-submit-btn");
    const value = (valueInput.value || "").trim();

    if (!value) {
        msg.style.color = "#ff2d95";
        msg.textContent = "Enter a value first.";
        return;
    }

    btn.disabled = true;
    msg.style.color = "var(--text-muted)";
    msg.textContent = "Adding…";
    try {
        const res = await fetch(`${API_BASE}/admin/taxonomy/add`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({
                entry_type: entryType,
                value: value,
                parent_town: entryType === "location" ? (parentTownInput.value || "").trim() || null : null,
            }),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "Couldn't add that.");
        }
        const data = await res.json();
        msg.style.color = "var(--neon-gold, #ffd166)";
        msg.textContent = data.already_existed ? "That's already on the list." : "Added — live for everyone now.";
        valueInput.value = "";
        if (parentTownInput) parentTownInput.value = "";
        loadAdderList();
    } catch (err) {
        console.error("Adder submit failed:", err);
        msg.style.color = "#ff2d95";
        msg.textContent = err.message || "Couldn't reach the server.";
    } finally {
        btn.disabled = false;
    }
}

async function deleteAdderEntry(entryId) {
    if (!confirm("Remove this option? It'll disappear from every picker showing it.")) return;
    try {
        const res = await fetch(`${API_BASE}/admin/taxonomy/${entryId}`, { method: "DELETE", headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Couldn't remove that.");
        loadAdderList();
    } catch (err) {
        console.error("Adder delete failed:", err);
        alert(err.message || "Couldn't reach the server.");
    }
}

async function initDuplicateGuardPage() {
    loadDuplicateGuardPending();
}

async function loadDuplicateGuardPending() {
    const list = document.getElementById("dupguard-pending-list");
    const countEl = document.getElementById("dupguard-pending-count");
    if (!list) return;
    list.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Loading…</p>`;
    try {
        const res = await fetch(`${API_BASE}/admin/duplicate-guard/pending`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error("Couldn't load pending photos");
        const data = await res.json();
        const rows = data.pending || [];
        if (countEl) countEl.textContent = rows.length;
        if (!rows.length) {
            list.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Nothing waiting right now.</p>`;
            return;
        }
        list.innerHTML = rows.map(r => `
            <div class="list-item" style="display:block; padding:0.9rem 1rem;">
                <div style="display:flex; gap:1rem; align-items:flex-start;">
                    <div class="media-viewport" onclick="toggleMediaPresentation(this)" style="width:72px; height:72px; border-radius:12px; border:1px solid var(--border-color); cursor:zoom-in; flex-shrink:0;">
                        <img src="${escapeHtmlAdmin(r.photo_url)}" alt="" />
                    </div>
                    <div style="flex:1; min-width:0;">
                        <p style="font-weight:600;">${escapeHtmlAdmin(r.full_name || r.username)}</p>
                        <p style="font-size:0.78rem; color:var(--text-muted); margin-top:0.15rem;">${escapeHtmlAdmin(r.username)}</p>
                        <p style="font-size:0.72rem; color:var(--text-muted); margin-top:0.15rem;">Submitted ${r.submitted_at ? new Date(r.submitted_at).toLocaleString() : ''}</p>
                        <div style="display:flex; gap:0.5rem; margin-top:0.6rem;">
                            <button class="action-btn btn-approve" style="width:auto; padding:0 1rem;" onclick="approveDuplicateGuard('${r.user_id}')">Approve</button>
                            <button class="action-btn btn-reject" style="width:auto; padding:0 1rem;" onclick="rejectDuplicateGuard('${r.user_id}')">Reject</button>
                        </div>
                    </div>
                </div>
                <p id="dupguard-msg-${r.user_id}" style="font-size:0.75rem; color:var(--text-muted); margin-top:0.4rem;"></p>
            </div>
        `).join("");
    } catch (err) {
        console.error("Failed loading duplicate guard queue:", err);
        list.innerHTML = `<p style="padding:1rem; color:#ff2d95;">Couldn't load — try again.</p>`;
    }
}

async function approveDuplicateGuard(userId) {
    const msgEl = document.getElementById(`dupguard-msg-${userId}`);
    if (msgEl) { msgEl.style.color = "var(--text-muted)"; msgEl.textContent = "Approving…"; }
    try {
        const res = await fetch(`${API_BASE}/admin/duplicate-guard/${userId}/approve`, { method: "POST", headers: getAuthHeaders() });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "Couldn't approve this photo.");
        }
        loadDuplicateGuardPending();
    } catch (err) {
        console.error("Approve failed:", err);
        if (msgEl) { msgEl.style.color = "#ff2d95"; msgEl.textContent = err.message || "Couldn't reach the server."; }
    }
}

async function rejectDuplicateGuard(userId) {
    const msgEl = document.getElementById(`dupguard-msg-${userId}`);
    const reason = prompt("Reject this photo?\n\nOptional reason (shown to the user):", "");
    if (reason === null) return;
    if (msgEl) { msgEl.style.color = "var(--text-muted)"; msgEl.textContent = "Rejecting…"; }
    try {
        const res = await fetch(`${API_BASE}/admin/duplicate-guard/${userId}/reject`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ reason: reason || null }),
        });
        if (!res.ok) {
            const data = await res.json().catch(() => ({}));
            throw new Error(data.detail || "Couldn't reject this photo.");
        }
        loadDuplicateGuardPending();
    } catch (err) {
        console.error("Reject failed:", err);
        if (msgEl) { msgEl.style.color = "#ff2d95"; msgEl.textContent = err.message || "Couldn't reach the server."; }
    }
}

// ==========================================
function initBroadcastPage() {
    const broadcastForm = document.getElementById("admin-broadcast-form");
    if (!broadcastForm) return;

    const audienceInput = document.getElementById("broadcast-audience");
    document.querySelectorAll(".broadcast-audience-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            document.querySelectorAll(".broadcast-audience-btn").forEach(b => b.classList.remove("active"));
            btn.classList.add("active");
            audienceInput.value = btn.dataset.audience;
        });
    });

    broadcastForm.onsubmit = async (e) => {
        e.preventDefault();
        const title = document.getElementById("broadcast-title").value.trim();
        const body = document.getElementById("broadcast-body").value.trim();
        const type = document.getElementById("broadcast-type").value;
        const reference = document.getElementById("broadcast-reference").value.trim();
        const audience = audienceInput.value || "organisers";
        if (!title || !body) return;

        const submitBtn = broadcastForm.querySelector("button[type=submit]");
        const originalText = submitBtn.textContent;
        submitBtn.disabled = true;
        submitBtn.textContent = "Transmitting…";

        try {
            const res = await fetch(`${API_BASE}/admin/broadcast`, {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({ title, body, type, reference: reference || null, audience }),
            });
            if (!res.ok) {
                const data = await res.json().catch(() => ({}));
                alert(data.detail || "Couldn't send broadcast.");
                return;
            }
            const data = await res.json();
            broadcastForm.reset();
            // Reset the pill filter back to its default alongside the rest of the form
            document.querySelectorAll(".broadcast-audience-btn").forEach(b => b.classList.remove("active"));
            document.querySelector('.broadcast-audience-btn[data-audience="organisers"]')?.classList.add("active");
            audienceInput.value = "organisers";
            const parts = [];
            if (data.host_recipients) parts.push(`${data.host_recipients} organiser(s)`);
            if (data.community_recipients) parts.push(`${data.community_recipients} community member(s)`);
            alert(`Broadcast sent to ${parts.join(" and ")}.`);
        } catch (err) {
            console.error("Broadcast failed:", err);
            alert("Couldn't reach the server to send this broadcast.");
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = originalText;
        }
    };
}

function initSupportPage() {
    const chatStream = document.getElementById("admin-desk-chat-stream");
    const ticketList = document.getElementById("support-ticket-list");
    const replyForm = document.getElementById("admin-desk-reply-form");
    const replyInput = document.getElementById("admin-desk-reply-input");
    const sendBtn = document.getElementById("admin-desk-send-btn");

    if (!chatStream || !ticketList || !replyForm) return;

    let activeHostId = null;

    // 1. Fetch the list of hosts with active/unresolved support threads
    async function pollTicketList() {
        try {
            const res = await fetch(`${API_BASE}/admin/support-tickets/active`, { headers: getAuthHeaders() });
            if (!res.ok) return;
            const tickets = await res.json();

            if (!tickets || tickets.length === 0) {
                ticketList.innerHTML = `<p style="text-align:center; color: var(--text-muted); font-size: 0.75rem; padding: 0.5rem 0;">No active support tickets.</p>`;
                return;
            }

            ticketList.innerHTML = tickets.map(t => {
                const initials = (t.full_name || "H").trim().split(/\s+/).map(w => w[0]).slice(0, 2).join("").toUpperCase();
                return `
                <div class="wa-sidebar-row ${activeHostId === t.host_id ? 'active' : ''}" data-host-id="${t.host_id}">
                    <div class="wa-sidebar-avatar">${initials}</div>
                    <div class="wa-sidebar-meta">
                        <div class="wa-sidebar-name">${t.full_name || 'Host'}</div>
                        <div class="wa-sidebar-sub">${t.message}</div>
                    </div>
                    ${t.unread ? `<div class="wa-sidebar-badge">•</div>` : `<span style="font-size:0.65rem; color:var(--text-muted); flex-shrink:0;">${new Date(t.created_at).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})}</span>`}
                </div>`;
            }).join("");

            ticketList.querySelectorAll(".wa-sidebar-row").forEach(row => {
                row.onclick = () => selectHostThread(row.dataset.hostId, row.querySelector(".wa-sidebar-name")?.textContent || "Host");
            });
        } catch (e) {
            console.error("Failed loading support ticket list:", e);
        }
    }

    // 2. Load a specific host's full thread into the chat stream
    async function selectHostThread(hostId, hostName) {
        activeHostId = hostId;
        replyInput.disabled = false;
        sendBtn.disabled = false;
        const headEl = document.getElementById("support-thread-header");
        if (headEl) headEl.textContent = `${hostName || "Host"} — conversation with BASH HQ`;
        // Mobile: swap from the host list to the full-screen chat view
        // (desktop's two-pane layout is untouched by this class).
        document.getElementById("page-support")?.querySelector(".wa-shell")?.classList.add("thread-open");
        pollTicketList();
        await pollActiveThread();
    }

    // Mobile back button — returns from the open chat to the host list.
    const backBtn = document.getElementById("support-back-btn");
    backBtn?.addEventListener("click", () => {
        document.getElementById("page-support")?.querySelector(".wa-shell")?.classList.remove("thread-open");
    });

    async function pollActiveThread() {
        if (!activeHostId) return;
        try {
            const res = await fetch(`${API_BASE}/admin/support-tickets/${activeHostId}/thread`, { headers: getAuthHeaders() });
            if (!res.ok) return;
            const messages = await res.json();

            chatStream.innerHTML = messages.map(m => `
                <div style="${m.sender === 'admin'
                    ? 'background: linear-gradient(135deg, var(--accent-primary), #ff8a5c); color: white; align-self: flex-end;'
                    : 'background: var(--bg-card); border: 1px solid var(--border-color); align-self: flex-start;'}
                    padding: 1rem; border-radius: 12px; max-width: 85%; font-size: 0.85rem;">
                    ${m.message}
                    <div style="font-size: 0.65rem; opacity:0.7; text-align: right; margin-top: 0.35rem; font-family: monospace;">
                        ${new Date(m.created_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                    </div>
                </div>
            `).join("") || `<p style="text-align:center; color: var(--text-muted); font-size: 0.8rem; padding: 2rem 0;">No messages yet.</p>`;
            chatStream.scrollTop = chatStream.scrollHeight;
        } catch (e) {
            console.error("Failed painting admin live desk stream:", e);
        }
    }

    // 3. Handle Live Response Dispatches
    replyForm.onsubmit = async (e) => {
        e.preventDefault();
        const msgText = replyInput.value.trim();
        if (!msgText || !activeHostId) return;

        const adminBubble = document.createElement("div");
        adminBubble.style = "background: linear-gradient(135deg, var(--accent-primary), #ff8a5c); color: white; padding: 1rem; border-radius: 12px; align-self: flex-end; max-width: 85%; font-size: 0.85rem;";
        adminBubble.textContent = msgText;
        chatStream.appendChild(adminBubble);

        replyInput.value = "";
        chatStream.scrollTop = chatStream.scrollHeight;

        try {
            await fetch(`${API_BASE}/admin/support-tickets/reply`, {
                method: "POST",
                headers: getAuthHeaders(),
                body: JSON.stringify({ host_id: activeHostId, message: msgText })
            });
            pollTicketList();
        } catch (err) {
            console.warn("Async queue tracking transmission established.");
        }
    };

    pollTicketList();

    if (window.adminChatTimer) clearInterval(window.adminChatTimer);
    window.adminChatTimer = setInterval(() => {
        pollTicketList();
        pollActiveThread();
    }, 4000);
}

// ==========================================
function initAnalyticsPage() {
    const startBtn = document.getElementById("startAnalyticsPollBtn");
    const stopBtn = document.getElementById("stopAnalyticsPollBtn");
    const statusBox = document.getElementById("analytics-poll-status");
    const slotsBox = document.getElementById("analytics-slots");
    const winnersBox = document.getElementById("analytics-winners");

    if (!startBtn || startBtn.dataset.bound) {
        // Already bound on a prior visit — just refresh the leaderboard.
        pollAnalyticsLeaderboard();
        return;
    }
    startBtn.dataset.bound = "1";

    startBtn.onclick = async () => {
        try {
            const res = await fetch(`${API_BASE}/admin/analytics/poll/start`, { method: "POST", headers: getAuthHeaders() });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) { alert(data.detail || "Couldn't start poll."); return; }
            statusBox.textContent = `Poll active — notified ${data.notified_hosts} host(s). Bids are coming in live below.`;
            pollAnalyticsLeaderboard();
            if (window.analyticsTimer) clearInterval(window.analyticsTimer);
            window.analyticsTimer = setInterval(pollAnalyticsLeaderboard, 4000);
        } catch (err) {
            alert("Couldn't reach the server to start the poll.");
        }
    };

    stopBtn.onclick = async () => {
        if (!confirm("Stop the poll and take the top bid for each of the 3 slots?")) return;
        try {
            const res = await fetch(`${API_BASE}/admin/analytics/poll/stop`, { method: "POST", headers: getAuthHeaders() });
            const data = await res.json().catch(() => ({}));
            if (!res.ok) { alert(data.detail || "Couldn't stop poll."); return; }
            if (window.analyticsTimer) clearInterval(window.analyticsTimer);
            statusBox.textContent = "Poll closed.";
            renderWinners(data.winners || []);
        } catch (err) {
            alert("Couldn't reach the server to stop the poll.");
        }
    };

    function renderWinners(winners) {
        if (!winners.length) {
            winnersBox.innerHTML = `<p style="color: var(--text-muted);">No bids were placed on any slot.</p>`;
            return;
        }
        winnersBox.innerHTML = `
            <h2 style="margin-bottom:1rem;">Winning Media — Ready to Publish</h2>
            <div style="display:grid; grid-template-columns: repeat(3, 1fr); gap:1rem;">
                ${winners.map(w => `
                    <div class="floating-financial-card" style="cursor:default;">
                        <h2>Slot ${w.slot_number}</h2>
                        <p style="color: var(--text-main); font-weight:700; margin-top:0.5rem;">${w.host_name || 'Host'}</p>
                        <p style="color: var(--accent-primary); font-weight:800;">KSh ${Number(w.amount).toLocaleString()}</p>
                        <img src="${w.media_url}" alt="" style="width:100%; border-radius:12px; margin-top:0.75rem; max-height:140px; object-fit:cover;" onerror="this.style.display='none'">
                    </div>
                `).join("")}
            </div>
            <button class="action-btn btn-approve" style="margin-top:1.25rem;" onclick="publishHeaderMedia()">📡 Publish to Home Page Header</button>
        `;
    }

    pollAnalyticsLeaderboard();

    let _lastLeaderboardSignature = null;

    async function pollAnalyticsLeaderboard() {
        try {
            const res = await fetch(`${API_BASE}/admin/analytics/poll/active`, { headers: getAuthHeaders() });
            if (!res.ok) return;
            const data = await res.json();
            if (!data.active) {
                if (_lastLeaderboardSignature !== "inactive") {
                    slotsBox.innerHTML = `<p style="padding:1rem; color: var(--text-muted);">No active poll. Start one to see live bids per slot.</p>`;
                    _lastLeaderboardSignature = "inactive";
                }
                statusBox.textContent = "No active poll.";
                return;
            }
            statusBox.textContent = "Poll active — bidding in progress.";
            // Cheap signature of the slots — skip the innerHTML rebuild
            // entirely when a poll tick brings back the exact same bids as
            // last time (the common case), which is what was causing this
            // to visibly flash every 4 seconds while an admin watched it.
            const signature = JSON.stringify(data.slots.map(s => [s.slot_number, s.bid_count, s.top_bid?.host_name, s.top_bid?.amount]));
            if (signature === _lastLeaderboardSignature) return;
            _lastLeaderboardSignature = signature;
            slotsBox.innerHTML = data.slots.map(s => `
                <div style="padding:1rem; border-bottom:1px solid var(--border-color);">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <strong>Slot ${s.slot_number}</strong>
                        <span style="font-size:0.7rem; color: var(--text-muted);">${s.bid_count} bid(s)</span>
                    </div>
                    ${s.top_bid ? `
                        <p style="margin-top:0.4rem; font-size:0.85rem;">Top: <strong>${s.top_bid.host_name}</strong> — <span style="color:var(--accent-primary); font-weight:700;">KSh ${Number(s.top_bid.amount).toLocaleString()}</span></p>
                    ` : `<p style="margin-top:0.4rem; font-size:0.8rem; color: var(--text-muted);">No bids yet.</p>`}
                </div>
            `).join("");
        } catch (e) {
            console.warn("Failed polling analytics leaderboard:", e);
        }
    }

    window._pollAnalyticsLeaderboard = pollAnalyticsLeaderboard;
}

async function publishHeaderMedia() {
    try {
        const res = await fetch(`${API_BASE}/admin/header-media/publish`, { method: "POST", headers: getAuthHeaders() });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) { alert(data.detail || "Couldn't publish."); return; }
        alert("Published! The home page header will now show these 3 slots.");
    } catch (err) {
        alert("Couldn't reach the server to publish.");
    }
}

// ==========================================
// User Growth analytics — total users/hosts, active-user counts, average
// session time, and a weekly cumulative-user-count chart. The chart's
// y-axis auto-scales its formatting (raw / K / M) so it stays readable
// whether the platform has a hundred users or several million.
// ==========================================

function formatCompactNumber(n) {
    n = Number(n) || 0;
    if (n >= 1000000) return (n / 1000000).toFixed(n % 1000000 === 0 ? 0 : 1) + "M";
    if (n >= 1000) return (n / 1000).toFixed(n % 1000 === 0 ? 0 : 1) + "K";
    return String(Math.round(n));
}

function renderUserGrowthChart(series) {
    const wrap = document.getElementById("ug-chart-wrap");
    if (!wrap) return;

    if (!series || series.length === 0) {
        wrap.innerHTML = `<p style="text-align:center; color: var(--text-muted); font-size: 0.85rem; padding: 2rem 0;">No signup data yet.</p>`;
        return;
    }

    const values = series.map(s => s.cumulative_users);
    const maxVal = Math.max(...values, 1);
    const minVal = Math.min(...values, 0);

    // Layout — width grows with the number of weeks so points never crowd
    // together; the wrapper scrolls horizontally on smaller screens.
    const pointGap = 56;
    const leftPad = 56, rightPad = 24, topPad = 20, bottomPad = 36;
    const chartW = Math.max(560, series.length * pointGap);
    const chartH = 280;
    const plotW = chartW - leftPad - rightPad;
    const plotH = chartH - topPad - bottomPad;

    const xFor = (i) => leftPad + (series.length === 1 ? plotW / 2 : (i / (series.length - 1)) * plotW);
    const yFor = (v) => {
        if (maxVal === minVal) return topPad + plotH / 2;
        return topPad + plotH - ((v - minVal) / (maxVal - minVal)) * plotH;
    };

    // 4 evenly spaced horizontal gridlines/labels, formatted with the same
    // adaptive K/M shorthand as the stat cards.
    const gridCount = 4;
    let gridLines = "";
    for (let g = 0; g <= gridCount; g++) {
        const val = minVal + ((maxVal - minVal) * g) / gridCount;
        const y = yFor(val);
        gridLines += `
            <line x1="${leftPad}" y1="${y}" x2="${chartW - rightPad}" y2="${y}" stroke="var(--border-color)" stroke-width="1" stroke-dasharray="3,4" />
            <text x="${leftPad - 10}" y="${y + 4}" text-anchor="end" font-size="11" fill="var(--text-muted)">${formatCompactNumber(val)}</text>
        `;
    }

    const linePoints = series.map((s, i) => `${xFor(i)},${yFor(s.cumulative_users)}`).join(" ");
    const areaPoints = `${xFor(0)},${yFor(minVal)} ${linePoints} ${xFor(series.length - 1)},${yFor(minVal)}`;

    // Show every x-axis label if there's room, otherwise thin them out so
    // they don't overlap on a 52-week view.
    const labelEvery = series.length > 16 ? Math.ceil(series.length / 12) : 1;

    let dots = "", xLabels = "";
    series.forEach((s, i) => {
        const x = xFor(i), y = yFor(s.cumulative_users);
        dots += `<circle cx="${x}" cy="${y}" r="3.5" fill="var(--accent-primary)" />`;
        if (i % labelEvery === 0 || i === series.length - 1) {
            const d = new Date(s.week_start + "T00:00:00");
            const label = d.toLocaleDateString([], { month: "short", day: "numeric" });
            xLabels += `<text x="${x}" y="${chartH - bottomPad + 18}" text-anchor="middle" font-size="10.5" fill="var(--text-muted)">${label}</text>`;
        }
    });

    wrap.innerHTML = `
        <svg viewBox="0 0 ${chartW} ${chartH}" width="${chartW}" height="${chartH}" style="display:block; min-width:${chartW}px;">
            ${gridLines}
            <polygon points="${areaPoints}" fill="var(--accent-primary)" opacity="0.10" />
            <polyline points="${linePoints}" fill="none" stroke="var(--accent-primary)" stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round" />
            ${dots}
            ${xLabels}
        </svg>
    `;
}

async function initUserGrowthPage() {
    const weeksSelect = document.getElementById("ug-weeks-select");
    if (!weeksSelect) return;

    async function loadGrowth() {
        const weeks = weeksSelect.value || 26;
        try {
            const res = await fetch(`${API_BASE}/admin/analytics/growth?weeks=${weeks}`, { headers: getAuthHeaders() });
            if (!res.ok) return;
            const data = await res.json();

            document.getElementById("ug-total-users").textContent = formatCompactNumber(data.total_users);
            document.getElementById("ug-total-hosts").textContent = formatCompactNumber(data.total_hosts);
            document.getElementById("ug-active-7d").textContent = formatCompactNumber(data.active_last_7_days);

            const avgMin = data.avg_session_minutes || 0;
            document.getElementById("ug-avg-session").textContent = avgMin >= 60
                ? `${(avgMin / 60).toFixed(1)}h`
                : `${avgMin}m`;

            renderUserGrowthChart(data.weekly_series);
        } catch (e) {
            console.error("Failed loading user growth analytics:", e);
        }
    }

    weeksSelect.onchange = loadGrowth;
    loadGrowth();
}

// Global Core Close Modal Actions Handler
function closeGlobalModal() {
    const overlay = document.getElementById("global-overlay");
    overlay.classList.remove("active");
    overlay.classList.remove("fullscreen-modal");
    activeVerificationUser = null;
    if (deadlineCountdownTimer) { clearInterval(deadlineCountdownTimer); deadlineCountdownTimer = null; }
}

// Initial Boot Lifecycle Entry Hook
window.addEventListener("DOMContentLoaded", () => {
    loadFilteredVerifications();
    loadAdminHostEvents();
});

// NOTE: previously had a hidden "tap the avatar 7x" trigger that opened a
// Create Admin modal posting to /admin/register. Removed alongside that
// backend endpoint — it created rows in a database table
// (see backend app/api/v1/admin.py) that could never actually authenticate
// as an admin, so the modal's "Admin created and saved" message was a
// false positive. The one real path to admin access is a `users` row with
// is_admin=True, set directly at the database level.
// ---- Refunds subpage: Requested / Paid nav, per-event drilldown ----
let currentRefundsTab = 'requested';
let currentRefundEventId = null;

function initRefundsPage() {
    switchRefundsTab(currentRefundsTab);
    loadRefundSearchResults();
}

function switchRefundsTab(tab) {
    currentRefundsTab = tab;
    ['requested', 'paid'].forEach(t => {
        const btn = document.getElementById(`refunds-tab-${t}`);
        if (btn) btn.classList.toggle('active', t === tab);
    });
    const title = document.getElementById('refunds-events-title');
    if (title) title.textContent = tab === 'paid' ? 'Events with refunds paid' : 'Events with refunds requested';
    closeRefundEventDetail();
    loadRefundEventsList();
}

async function loadRefundEventsList() {
    const container = document.getElementById('refunds-events-list');
    if (!container) return;
    container.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Loading…</p>`;
    try {
        const res = await fetch(`${API_BASE}/admin/refunds/events?status=${currentRefundsTab}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const rows = await res.json();
        renderRefundEventsList(rows);
        const countEl = document.getElementById(`refunds-tab-count-${currentRefundsTab}`);
        if (countEl) countEl.textContent = rows.reduce((n, r) => n + r.count, 0);
    } catch (err) {
        console.error("Failed loading refund events:", err);
        container.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Couldn't reach the server.</p>`;
    }
}

function renderRefundEventsList(rows) {
    const container = document.getElementById('refunds-events-list');
    if (!rows || !rows.length) {
        container.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">No ${currentRefundsTab === 'paid' ? 'paid' : 'outstanding'} refunds right now.</p>`;
        return;
    }
    container.innerHTML = rows.map(ev => `
        <div class="list-item" onclick="openRefundEventDetail('${ev.event_id}')">
            <div style="display:flex; align-items:center; gap:1rem; flex:1; min-width:0;">
                <div class="media-viewport" style="width:64px; height:64px; margin:0; flex-shrink:0;">
                    ${ev.media_url ? `<img src="${resolveMediaUrl(ev.media_url)}">` : ""}
                </div>
                <div style="min-width:0;">
                    <h3 style="font-weight:700; white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">${ev.event_title}</h3>
                    <p style="color:var(--text-muted); font-size:0.8rem; margin-top:0.2rem;">KSh ${Number(ev.total_amount || 0).toLocaleString()} total</p>
                </div>
            </div>
            <div style="text-align:right; flex-shrink:0;">
                <span class="wa-sidebar-badge" style="display:inline-flex;">${ev.count}</span>
            </div>
        </div>
    `).join("");
}

function closeRefundEventDetail() {
    currentRefundEventId = null;
    document.getElementById('refunds-events-panel').style.display = '';
    document.getElementById('refunds-event-detail-panel').style.display = 'none';
}

async function openRefundEventDetail(eventId) {
    currentRefundEventId = eventId;
    document.getElementById('refunds-events-panel').style.display = 'none';
    const detailPanel = document.getElementById('refunds-event-detail-panel');
    detailPanel.style.display = '';
    const listEl = document.getElementById('refunds-event-detail-list');
    const titleEl = document.getElementById('refunds-event-detail-title');
    listEl.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Loading…</p>`;

    try {
        const res = await fetch(`${API_BASE}/admin/refunds/events/${eventId}?status=${currentRefundsTab}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        titleEl.textContent = `Refunds ${currentRefundsTab === 'paid' ? 'paid' : 'requested'} — ${data.event_title}`;
        renderRefundNamesList(data.refunds);
    } catch (err) {
        console.error("Failed loading refunds for event:", err);
        listEl.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Couldn't reach the server.</p>`;
    }
}

function renderRefundNamesList(refunds) {
    const listEl = document.getElementById('refunds-event-detail-list');
    if (!refunds || !refunds.length) {
        listEl.innerHTML = `<p style="padding:1rem; color:var(--text-muted);">Nothing here.</p>`;
        return;
    }
    listEl.innerHTML = refunds.map(r => `
        <div>
            <div class="refund-name-row" onclick="toggleRefundDetail('${r.booking_id}')">
                <div style="min-width:0;">
                    <strong>${r.buyer_name}</strong>
                    <p style="font-size:0.75rem; color:var(--text-muted); margin-top:0.15rem;">${r.buyer_username ? "@" + r.buyer_username + " · " : ""}Requested ${r.requested_at ? new Date(r.requested_at).toLocaleString() : "—"}</p>
                    <p style="font-size:0.78rem; color:var(--text-main); margin-top:0.2rem;"><strong>Paid with:</strong> ${r.buyer_phone || "Not on file"}</p>
                </div>
                <span style="font-weight:700; color:var(--accent-success);">KSh ${Number(r.amount || 0).toLocaleString()}</span>
            </div>
            <div class="refund-detail-panel" id="refund-detail-${r.booking_id}" style="display:none;">
                <p style="font-size:0.85rem;"><strong>Phone used to pay:</strong> ${r.buyer_phone || "Not on file"}</p>
                ${r.refund_payout_status === 'paid'
                    ? `<p style="font-size:0.85rem; color:var(--accent-success); margin-top:0.5rem;">✓ Paid ${r.refund_paid_at ? new Date(r.refund_paid_at).toLocaleString() : ""}${r.refund_paid_by_admin_name ? " by " + r.refund_paid_by_admin_name : ""} — M-Pesa code <strong>${r.refund_mpesa_code || ""}</strong></p>`
                    : `
                    <div style="display:flex; gap:0.6rem; margin-top:0.6rem;">
                        <input type="text" id="mpesa-code-${r.booking_id}" class="search-input" placeholder="M-Pesa code as proof of payment" style="flex:1;">
                        <button class="action-btn btn-approve" style="width:auto; padding:0 1rem;" onclick="submitMarkRefundPaid('${r.booking_id}')">Mark Paid</button>
                    </div>
                    <p id="refund-paid-msg-${r.booking_id}" style="font-size:0.78rem; color:var(--text-muted); margin-top:0.4rem;"></p>
                    `
                }
            </div>
        </div>
    `).join("");
}

function toggleRefundDetail(bookingId) {
    const panel = document.getElementById(`refund-detail-${bookingId}`);
    if (panel) panel.style.display = panel.style.display === 'none' ? '' : 'none';
}

async function submitMarkRefundPaid(bookingId) {
    const input = document.getElementById(`mpesa-code-${bookingId}`);
    const msgEl = document.getElementById(`refund-paid-msg-${bookingId}`);
    const mpesa_code = (input?.value || "").trim();
    if (!mpesa_code) {
        if (msgEl) msgEl.textContent = "Enter the M-Pesa code first.";
        return;
    }
    if (msgEl) msgEl.textContent = "Saving…";
    try {
        const res = await fetch(`${API_BASE}/admin/refunds/bookings/${bookingId}/mark-paid`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ mpesa_code }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            if (msgEl) msgEl.textContent = data.detail || "Couldn't mark this refund paid.";
            return;
        }
        // Re-render the current event's list so this name moves out of
        // Requested (or shows the new Paid state if we're already there).
        if (currentRefundEventId) openRefundEventDetail(currentRefundEventId);
        loadRefundEventsList();
        refreshSidebarBadges();
    } catch (err) {
        console.error("Failed marking refund paid:", err);
        if (msgEl) msgEl.textContent = "Couldn't reach the server.";
    }
}

// ---- Refunds archive (paste M-Pesa message -> archive; search by name/username) ----
function renderRefundEntries(container, rows) {
    if (!Array.isArray(rows) || !rows.length) {
        container.innerHTML = `<p style="color:var(--text-muted); padding:1rem;">No refund messages archived yet.</p>`;
        return;
    }
    container.innerHTML = rows.map(e => `
        <div class="host-card" style="padding:0.85rem 1rem; border:1px solid var(--border-color); border-radius:12px; margin-bottom:0.6rem;">
            <div style="display:flex; justify-content:space-between; align-items:center; gap:0.5rem;">
                <strong>${e.payer_name || "Name not detected"}</strong>
                <span style="font-size:0.68rem; color:var(--text-muted);">${e.created_at ? new Date(e.created_at).toLocaleString() : ""}</span>
            </div>
            <p style="font-size:0.78rem; color:var(--text-muted); margin-top:0.25rem;">
                ${e.matched_username ? `@${e.matched_username} · ` : ""}${e.phone || "No phone detected"}${e.mpesa_code ? ` · Code ${e.mpesa_code}` : ""}${e.amount ? ` · KSh ${Number(e.amount).toLocaleString()}` : ""}
            </p>
            <p style="font-size:0.72rem; color:var(--text-muted); margin-top:0.4rem; font-style:italic; opacity:0.75;">${(e.raw_message || "").slice(0, 160)}${(e.raw_message || "").length > 160 ? "…" : ""}</p>
        </div>
    `).join("");
}

let refundArchiveSearchLoadedOnce = false;
function toggleRefundArchiveSearch() {
    const section = document.getElementById("refund-archive-search-section");
    const icon = document.getElementById("refund-archive-toggle-icon");
    const label = document.getElementById("refund-archive-toggle-label");
    const btn = document.getElementById("refund-archive-toggle-btn");
    if (!section) return;
    const opening = section.style.display === "none";
    section.style.display = opening ? "block" : "none";
    if (icon) icon.textContent = opening ? "▲" : "🔍";
    if (label) label.textContent = opening ? "Hide Refund Archive" : "Search the Refund Archive";
    if (btn) btn.setAttribute("aria-expanded", opening ? "true" : "false");
    // Load on first open only — search-as-you-type (below) handles the rest.
    if (opening && !refundArchiveSearchLoadedOnce) {
        refundArchiveSearchLoadedOnce = true;
        loadRefundSearchResults();
    }
}

async function submitRefundArchive() {
    const msgInput = document.getElementById("refund-message-input");
    const userInput = document.getElementById("refund-username-input");
    const statusEl = document.getElementById("refund-archive-msg");
    const btn = document.getElementById("refund-archive-btn");
    const raw_message = (msgInput?.value || "").trim();
    if (!raw_message) {
        if (statusEl) statusEl.textContent = "Paste the M-Pesa message first.";
        return;
    }
    if (btn) btn.disabled = true;
    if (statusEl) statusEl.textContent = "Archiving…";
    try {
        const res = await fetch(`${API_BASE}/admin/refunds/archive`, {
            method: "POST",
            headers: getAuthHeaders(),
            body: JSON.stringify({ raw_message, matched_username: (userInput?.value || "").trim() || null }),
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            if (statusEl) statusEl.textContent = data.detail || "Couldn't archive that message.";
            return;
        }
        if (statusEl) statusEl.textContent = `Archived — ${data.payer_name || "name not detected"} logged ✓`;
        if (msgInput) msgInput.value = "";
        if (userInput) userInput.value = "";
        loadRefundSearchResults();
    } catch (err) {
        console.error("Failed to archive refund message:", err);
        if (statusEl) statusEl.textContent = "Couldn't reach the server.";
    } finally {
        if (btn) btn.disabled = false;
    }
}

let refundSearchDebounce = null;
async function loadRefundSearchResults() {
    const container = document.getElementById("refund-search-results");
    if (!container) return;
    const q = document.getElementById("refund-search-input")?.value || "";
    container.innerHTML = `<p style="color:var(--text-muted); padding:1rem;">Loading…</p>`;
    try {
        const res = await fetch(`${API_BASE}/admin/refunds/search?q=${encodeURIComponent(q)}`, { headers: getAuthHeaders() });
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const rows = await res.json();
        renderRefundEntries(container, rows);
    } catch (err) {
        console.error("Failed loading refund archive:", err);
        container.innerHTML = `<p style="color:var(--text-muted); padding:1rem;">Couldn't reach the server to search the archive.</p>`;
    }
}

document.addEventListener("DOMContentLoaded", () => {
    const searchInput = document.getElementById("refund-search-input");
    if (searchInput) {
        searchInput.addEventListener("input", () => {
            clearTimeout(refundSearchDebounce);
            refundSearchDebounce = setTimeout(loadRefundSearchResults, 300);
        });
    }
});