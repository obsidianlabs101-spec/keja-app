(function () {
    Keja.requireAuth();

    const params = new URLSearchParams(location.search);
    const propertyId = params.get("id");
    const content = document.getElementById("content");
    const ctaBar = document.getElementById("ctaBar");
    const ctaBtn = document.getElementById("ctaBtn");
    const saveBtn = document.getElementById("saveBtn");
    const modalRoot = document.getElementById("modalRoot");

    let property = null;
    let unlockStatus = null;
    let saved = false;

    function resolveMedia(url) {
        if (!url) return "";
        if (url.startsWith("http")) return url;
        return window.BASH_API_BASE_URL + "/" + url.replace(/^\/+/, "");
    }

    function toast(msg) {
        const el = document.createElement("div");
        el.className = "keja-toast";
        el.textContent = msg;
        document.body.appendChild(el);
        setTimeout(function () { el.remove(); }, 2200);
    }

    function render() {
        const p = property;
        const images = (p.images && p.images.length) ? p.images.map(function (i) { return i.url; }) : (p.main_image_url ? [p.main_image_url] : []);
        content.innerHTML =
            '<div class="keja-gallery">' +
            (images.length
                ? images.map(function (u) { return '<img src="' + resolveMedia(u) + '">'; }).join("")
                : '<div style="width:100%;aspect-ratio:4/3;background:var(--primary-light);border-radius:16px"></div>') +
            '</div>' +
            '<div class="p-title">' + p.title + '</div>' +
            '<div class="p-loc">' + [p.area, p.county].filter(Boolean).join(", ") + '</div>' +
            '<div class="p-price-row"><div class="p-price">' + Keja.fmtPrice(p.price) + '<span style="font-size:14px;font-weight:600;color:var(--text-secondary)">/month</span></div>' +
            '<span class="keja-status-pill ' + (p.is_booked ? "booked" : "available") + '">' + (p.is_booked ? "Booked" : "Available") + '</span></div>' +
            (p.proximity_note ? '<div class="keja-proximity">' + p.proximity_note + '</div>' : '') +
            '<div class="keja-detail-grid">' +
            '<div class="keja-detail-item"><div class="k">Type</div><div class="v">' + p.property_type + '</div></div>' +
            '<div class="keja-detail-item"><div class="k">Bedrooms</div><div class="v">' + (p.bedrooms != null ? p.bedrooms : "—") + '</div></div>' +
            '<div class="keja-detail-item"><div class="k">Bathrooms</div><div class="v">' + (p.bathrooms != null ? p.bathrooms : "—") + '</div></div>' +
            '<div class="keja-detail-item"><div class="k">Listed</div><div class="v">' + (p.created_at ? new Date(p.created_at).toLocaleDateString() : "—") + '</div></div>' +
            '</div>' +
            (p.description ? '<div class="p-desc">' + p.description + '</div>' : '') +
            '<div id="contactRevealed"></div>';

        renderCta();
    }

    function renderCta() {
        if (property.is_booked) {
            ctaBar.style.display = "block";
            ctaBtn.textContent = "This property is already booked";
            ctaBtn.disabled = true;
            return;
        }
        ctaBar.style.display = "block";
        if (unlockStatus && unlockStatus.status === "unlocked") {
            ctaBtn.style.display = "none";
            document.getElementById("contactRevealed").innerHTML =
                '<div class="landlord-row">' +
                '<div class="landlord-avatar">🏠</div>' +
                '<div><div style="font-weight:700">Landlord contact unlocked</div>' +
                '<a href="tel:' + unlockStatus.phone + '" style="color:var(--primary);font-weight:700">' + unlockStatus.phone + '</a></div>' +
                '</div>' +
                '<a class="keja-btn success" style="margin-top:12px" href="https://wa.me/' + toWhatsappFormat(unlockStatus.whatsapp) + '" target="_blank">Message on WhatsApp</a>';
        } else if (unlockStatus && unlockStatus.status === "awaiting_admin_match") {
            ctaBtn.style.display = "none";
            document.getElementById("contactRevealed").innerHTML =
                '<div class="keja-till-box">We\'re verifying your M-Pesa payment — this usually takes a few minutes. Check back shortly, or resend your code below.</div>' +
                '<button class="keja-btn secondary" id="resendClaimBtn">Resend payment code</button>';
            document.getElementById("resendClaimBtn").onclick = openPaymentModal;
        } else {
            ctaBtn.style.display = "block";
            ctaBtn.disabled = false;
            const hasFree = unlockStatus && unlockStatus.free_credits_available > 0;
            ctaBtn.textContent = hasFree ? "Get Contact — Free credit available 🎁" : "Get Contact — KES 50";
        }
    }

    function toWhatsappFormat(phone) {
        let p = (phone || "").replace(/\D/g, "");
        if (p.startsWith("0")) p = "254" + p.slice(1);
        return p;
    }

    async function loadUnlockStatus() {
        try {
            unlockStatus = await Keja.api("/contact-unlock/" + propertyId);
        } catch (e) {
            unlockStatus = null;
        }
    }

    async function load() {
        try {
            property = await Keja.api("/properties/" + propertyId);
            await loadUnlockStatus();
            render();

            const interested = await Keja.api("/properties/interested");
            saved = interested.some(function (p) { return p.id === propertyId; });
            updateSaveBtn();
        } catch (e) {
            content.innerHTML = '<div class="keja-empty">This listing could not be found — it may have been removed.</div>';
        }
    }

    function updateSaveBtn() {
        saveBtn.classList.toggle("saved", saved);
    }

    saveBtn.addEventListener("click", async function () {
        try {
            if (saved) {
                await Keja.api("/properties/" + propertyId + "/interested", { method: "DELETE" });
                saved = false;
                toast("Removed from Interested");
            } else {
                await Keja.api("/properties/" + propertyId + "/swipe?direction=right", { method: "POST" });
                saved = true;
                toast("Saved to Interested");
            }
            updateSaveBtn();
        } catch (e) {
            toast(e.message || "Something went wrong");
        }
    });

    function closeModal() { modalRoot.innerHTML = ""; }

    function openPaymentModal() {
        const till = window.KEJA_MPESA_TILL;
        modalRoot.innerHTML =
            '<div class="keja-modal-backdrop" id="unlockBackdrop">' +
            '<div class="keja-modal">' +
            '<h3>Unlock landlord contact</h3>' +
            '<p>Pay a one-time KES ' + till.amount + ' to reveal this landlord\'s phone number and WhatsApp.</p>' +
            '<div class="keja-till-box">Go to M-Pesa → Lipa na M-Pesa → Buy Goods and Services<br>Till Number: <b>' + till.till + '</b> (' + till.name + ')<br>Amount: <b>KES ' + till.amount + '</b></div>' +
            '<div class="keja-field"><label>Paste the M-Pesa confirmation SMS (or just the code)</label>' +
            '<textarea id="claimText" placeholder="e.g. QGH7XXXXX Confirmed. Ksh50.00 sent to Keja Kenya..."></textarea></div>' +
            '<div class="auth-error" id="claimError" style="color:#ef4444;font-size:13px;min-height:16px"></div>' +
            '<button class="keja-btn" id="submitClaimBtn">I\'ve paid — verify my code</button>' +
            '<button class="keja-btn ghost" id="cancelClaimBtn" style="margin-top:8px">Cancel</button>' +
            '</div></div>';

        document.getElementById("unlockBackdrop").addEventListener("click", function (e) { if (e.target === this) closeModal(); });
        document.getElementById("cancelClaimBtn").onclick = closeModal;
        document.getElementById("submitClaimBtn").onclick = async function () {
            const btn = this;
            const raw = document.getElementById("claimText").value.trim();
            const errEl = document.getElementById("claimError");
            if (!raw) { errEl.textContent = "Paste your M-Pesa code or message first."; return; }
            btn.disabled = true; btn.textContent = "Verifying…";
            try {
                unlockStatus = await Keja.api("/contact-unlock/" + propertyId + "/claim", {
                    method: "POST",
                    body: JSON.stringify({ raw_text: raw }),
                });
                closeModal();
                renderCta();
                toast(unlockStatus.status === "unlocked" ? "Contact unlocked!" : "Submitted — verifying your payment");
            } catch (e) {
                errEl.textContent = e.message || "Couldn't submit — try again";
                btn.disabled = false; btn.textContent = "I've paid — verify my code";
            }
        };
    }

    ctaBtn.addEventListener("click", async function () {
        if (unlockStatus && unlockStatus.free_credits_available > 0) {
            ctaBtn.disabled = true; ctaBtn.textContent = "Unlocking…";
            try {
                unlockStatus = await Keja.api("/contact-unlock/" + propertyId + "/use-free-credit", { method: "POST" });
                renderCta();
                toast("Free contact credit used 🎉");
            } catch (e) {
                toast(e.message || "Something went wrong");
                ctaBtn.disabled = false;
                renderCta();
            }
            return;
        }
        openPaymentModal();
    });

    load();
})();
