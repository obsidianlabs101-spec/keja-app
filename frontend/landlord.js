(function () {
    Keja.requireAuth();
    Keja.renderNav("profile");

    const listEl = document.getElementById("list");
    const noticeEl = document.getElementById("verificationNotice");
    const modalRoot = document.getElementById("modalRoot");
    let user = Keja.getUser();
    let editingId = null;
    let pendingImages = []; // {file, url, is_main}

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

    function populateCounties(selectId, current) {
        const sel = document.getElementById(selectId);
        sel.innerHTML = "";
        if (window.KENYA_LOCATIONS) {
            Object.keys(window.KENYA_LOCATIONS).sort().forEach(function (county) {
                const opt = document.createElement("option");
                opt.value = county; opt.textContent = county;
                if (county === current) opt.selected = true;
                sel.appendChild(opt);
            });
        }
    }

    async function checkLandlordAccess() {
        user = await Keja.refreshCurrentUser();
        if (user && user.is_host) {
            document.getElementById("newListingBtn").style.display = "flex";
            loadListings();
            return;
        }

        document.getElementById("newListingBtn").style.display = "none";
        let status = "none";
        try {
            const v = await Keja.api("/users/host-verification/me");
            status = v.host_verification_status || "none";
        } catch (e) { /* ignore */ }

        if (status === "pending") {
            noticeEl.style.display = "block";
            noticeEl.innerHTML = '<div class="keja-empty">Your landlord verification is pending review. We\'ll notify you once it\'s approved.</div>';
            listEl.innerHTML = "";
        } else {
            noticeEl.style.display = "block";
            noticeEl.innerHTML =
                '<div class="keja-empty">' +
                '<p>List your property on Keja — become a verified landlord.</p>' +
                '<button class="keja-btn" id="becomeLandlordBtn" style="max-width:260px;margin:10px auto 0">Become a landlord</button>' +
                '</div>';
            listEl.innerHTML = "";
            document.getElementById("becomeLandlordBtn").onclick = openLandlordRequestModal;
        }
    }

    function openLandlordRequestModal() {
        modalRoot.innerHTML =
            '<div class="keja-modal-backdrop" id="lReqBackdrop"><div class="keja-modal">' +
            '<h3>Become a landlord</h3>' +
            '<p>Verification helps keep Keja trustworthy for renters. This is reviewed by our team.</p>' +
            '<div class="keja-field"><label>Government ID number</label><input id="lReqGovId" type="text"></div>' +
            '<div class="keja-field"><label>Phone for renter contact</label><input id="lReqPhone" type="tel" value="' + (user.phone || "") + '"></div>' +
            '<div class="auth-error" id="lReqError" style="color:#ef4444;font-size:13px;min-height:16px"></div>' +
            '<button class="keja-btn" id="lReqSubmit">Submit for review</button>' +
            '<button class="keja-btn ghost" id="lReqCancel" style="margin-top:8px">Cancel</button>' +
            '</div></div>';
        document.getElementById("lReqBackdrop").addEventListener("click", function (e) { if (e.target === this) modalRoot.innerHTML = ""; });
        document.getElementById("lReqCancel").onclick = function () { modalRoot.innerHTML = ""; };
        document.getElementById("lReqSubmit").onclick = async function () {
            const btn = this;
            btn.disabled = true; btn.textContent = "Submitting…";
            try {
                await Keja.api("/users/host-verification/request", {
                    method: "POST",
                    body: JSON.stringify({
                        government_id: document.getElementById("lReqGovId").value.trim(),
                        phone: document.getElementById("lReqPhone").value.trim(),
                    }),
                });
                modalRoot.innerHTML = "";
                toast("Submitted — we'll review shortly");
                checkLandlordAccess();
            } catch (e) {
                document.getElementById("lReqError").textContent = e.message || "Couldn't submit";
                btn.disabled = false; btn.textContent = "Submit for review";
            }
        };
    }

    function rowHtml(p) {
        return (
            '<div class="keja-listing-row" data-id="' + p.id + '">' +
            '<img src="' + resolveMedia(p.main_image_url) + '">' +
            '<div style="flex:1">' +
            '<div style="font-weight:700">' + p.title + '</div>' +
            '<div class="keja-type">' + Keja.fmtPrice(p.price) + " · " + p.property_type + '</div>' +
            '<div class="keja-location">' + [p.area, p.county].filter(Boolean).join(", ") + '</div>' +
            '<span class="keja-status-pill ' + (p.is_booked ? "booked" : "available") + '" style="margin-top:4px">' + (p.is_booked ? "Booked" : "Available") + '</span>' +
            '<div class="listing-actions">' +
            '<button class="keja-btn secondary editBtn">Edit</button>' +
            '<button class="keja-btn ' + (p.is_booked ? "" : "success") + ' toggleBookedBtn">' + (p.is_booked ? "Mark available" : "Mark booked") + '</button>' +
            '<button class="keja-btn ghost removeBtn" style="color:#ef4444">Remove</button>' +
            '</div></div></div>'
        );
    }

    async function loadListings() {
        try {
            const mine = await Keja.api("/properties/mine");
            if (!mine.length) {
                listEl.innerHTML = '<div class="keja-empty">You haven\'t listed anything yet — tap + to add your first property.</div>';
                return;
            }
            listEl.innerHTML = mine.map(rowHtml).join("");
            bindRowActions();
        } catch (e) {
            listEl.innerHTML = '<div class="keja-empty">Couldn\'t load your listings.</div>';
        }
    }

    function bindRowActions() {
        listEl.querySelectorAll(".keja-listing-row").forEach(function (row) {
            const id = row.dataset.id;
            row.querySelector(".editBtn").onclick = function () { openListingModal(id); };
            row.querySelector(".toggleBookedBtn").onclick = async function () {
                const currentlyBooked = this.textContent.trim() === "Mark available";
                try {
                    await Keja.api("/properties/" + id, { method: "PATCH", body: JSON.stringify({ is_booked: currentlyBooked }) });
                    loadListings();
                } catch (e) { toast(e.message || "Couldn't update"); }
            };
            row.querySelector(".removeBtn").onclick = async function () {
                if (!confirm("Remove this listing? Renters will no longer see it.")) return;
                try {
                    await Keja.api("/properties/" + id, { method: "DELETE" });
                    loadListings();
                } catch (e) { toast(e.message || "Couldn't remove"); }
            };
        });
    }

    function openListingModal(id) {
        editingId = id || null;
        pendingImages = [];
        modalRoot.innerHTML =
            '<div class="keja-modal-backdrop" id="lModalBackdrop"><div class="keja-modal">' +
            '<h3>' + (id ? "Edit listing" : "New listing") + '</h3>' +
            '<div class="keja-field"><label>Title</label><input id="lTitle" type="text" placeholder="e.g. Cozy bedsitter near USIU"></div>' +
            '<div class="keja-field"><label>Photos</label><div class="thumb-row" id="thumbRow"><label>+<input type="file" id="lPhotoInput" accept="image/*" multiple style="display:none"></label></div></div>' +
            '<div class="keja-field"><label>Monthly rent (KES)</label><input id="lPrice" type="number" min="0"></div>' +
            '<div class="filter-row" style="display:flex;gap:10px">' +
            '<div class="keja-field" style="flex:1"><label>Type</label><select id="lType">' +
            '<option>Bedsitter</option><option>1 Bedroom</option><option>2 Bedroom</option><option>3 Bedroom</option><option>Studio</option><option>Airbnb</option></select></div>' +
            '<div class="keja-field" style="flex:1"><label>Bedrooms</label><input id="lBedrooms" type="number" min="0"></div>' +
            '</div>' +
            '<div class="keja-field"><label>County</label><select id="lCounty"></select></div>' +
            '<div class="keja-field"><label>Area / estate</label><input id="lArea" type="text" placeholder="e.g. Kasarani"></div>' +
            '<div class="keja-field"><label>Proximity note</label><input id="lProximity" type="text" placeholder="e.g. 5 min walk to USIU gate"></div>' +
            '<div class="keja-field"><label>Description</label><textarea id="lDesc"></textarea></div>' +
            '<div class="auth-error" id="lError" style="color:#ef4444;font-size:13px;min-height:16px"></div>' +
            '<button class="keja-btn" id="lSaveBtn">' + (id ? "Save changes" : "Publish listing") + '</button>' +
            '<button class="keja-btn ghost" id="lCancelBtn" style="margin-top:8px">Cancel</button>' +
            '</div></div>';

        populateCounties("lCounty");
        document.getElementById("lModalBackdrop").addEventListener("click", function (e) { if (e.target === this) modalRoot.innerHTML = ""; });
        document.getElementById("lCancelBtn").onclick = function () { modalRoot.innerHTML = ""; };
        document.getElementById("lPhotoInput").addEventListener("change", onPhotosSelected);

        if (id) fillForEdit(id);

        document.getElementById("lSaveBtn").onclick = saveListing;
    }

    function onPhotosSelected(e) {
        const files = Array.from(e.target.files || []);
        files.forEach(function (file) {
            const url = URL.createObjectURL(file);
            pendingImages.push({ file: file, url: url, is_main: pendingImages.length === 0 });
        });
        renderThumbs();
    }

    function renderThumbs() {
        const row = document.getElementById("thumbRow");
        const uploadLabel = row.querySelector("label");
        row.querySelectorAll("img").forEach(function (i) { i.remove(); });
        pendingImages.forEach(function (img) {
            const el = document.createElement("img");
            el.src = img.url;
            row.insertBefore(el, uploadLabel);
        });
    }

    async function fillForEdit(id) {
        try {
            const p = await Keja.api("/properties/" + id);
            document.getElementById("lTitle").value = p.title || "";
            document.getElementById("lPrice").value = p.price || "";
            document.getElementById("lType").value = p.property_type || "Bedsitter";
            document.getElementById("lBedrooms").value = p.bedrooms != null ? p.bedrooms : "";
            document.getElementById("lArea").value = p.area || "";
            document.getElementById("lProximity").value = p.proximity_note || "";
            document.getElementById("lDesc").value = p.description || "";
            populateCounties("lCounty", p.county);
        } catch (e) { toast("Couldn't load listing details"); }
    }

    async function saveListing() {
        const btn = document.getElementById("lSaveBtn");
        const errEl = document.getElementById("lError");
        const payload = {
            title: document.getElementById("lTitle").value.trim(),
            price: Number(document.getElementById("lPrice").value),
            property_type: document.getElementById("lType").value,
            bedrooms: document.getElementById("lBedrooms").value ? Number(document.getElementById("lBedrooms").value) : null,
            county: document.getElementById("lCounty").value,
            area: document.getElementById("lArea").value.trim(),
            proximity_note: document.getElementById("lProximity").value.trim(),
            description: document.getElementById("lDesc").value.trim(),
        };
        if (!payload.title || !payload.price || !payload.county) {
            errEl.textContent = "Title, price and county are required.";
            return;
        }
        btn.disabled = true; btn.textContent = "Saving…";
        try {
            let prop;
            if (editingId) {
                prop = await Keja.api("/properties/" + editingId, { method: "PATCH", body: JSON.stringify(payload) });
            } else {
                prop = await Keja.api("/properties/create", { method: "POST", body: JSON.stringify(payload) });
            }
            for (const img of pendingImages) {
                const fd = new FormData();
                fd.append("file", img.file);
                await Keja.api("/properties/" + prop.id + "/images?is_main=" + img.is_main, { method: "POST", body: fd });
            }
            modalRoot.innerHTML = "";
            toast(editingId ? "Listing updated" : "Listing published 🎉");
            loadListings();
        } catch (e) {
            errEl.textContent = e.message || "Couldn't save listing";
            btn.disabled = false; btn.textContent = editingId ? "Save changes" : "Publish listing";
        }
    }

    document.getElementById("newListingBtn").addEventListener("click", function () { openListingModal(null); });

    checkLandlordAccess();
})();
