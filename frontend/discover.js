(function () {
    Keja.requireAuth();
    Keja.renderNav("discover");

    const stage = document.getElementById("stage");
    const emptyState = document.getElementById("emptyState");
    let queue = [];
    let filters = {};

    function resolveMedia(url) {
        if (!url) return "";
        if (url.startsWith("http")) return url;
        return window.BASH_API_BASE_URL + "/" + url.replace(/^\/+/, "");
    }

    function populateCounties() {
        const sel = document.getElementById("fCounty");
        if (window.KENYA_LOCATIONS) {
            Object.keys(window.KENYA_LOCATIONS).sort().forEach(function (county) {
                const opt = document.createElement("option");
                opt.value = county; opt.textContent = county;
                sel.appendChild(opt);
            });
        }
    }

    function buildQuery() {
        const p = new URLSearchParams();
        Object.keys(filters).forEach(function (k) {
            if (filters[k] !== "" && filters[k] != null) p.set(k, filters[k]);
        });
        return p.toString();
    }

    async function fetchQueue() {
        emptyState.style.display = "none";
        try {
            const data = await Keja.api("/properties/discover?" + buildQuery());
            queue = data;
            renderTop();
        } catch (e) {
            console.warn("[Keja] discover load failed", e);
        }
    }

    function cardEl(prop, index) {
        const img = resolveMedia(prop.main_image_url);
        const el = document.createElement("div");
        el.className = "keja-swipe-card";
        el.style.backgroundImage = "url('" + img + "')";
        el.style.zIndex = String(100 - index);
        el.dataset.id = prop.id;
        el.innerHTML =
            '<div class="keja-swipe-stamp right">Interested</div>' +
            '<div class="keja-swipe-stamp left">Skip</div>' +
            '<div class="keja-swipe-card-info">' +
            '<div class="keja-price">' + Keja.fmtPrice(prop.price) + '<span style="font-size:13px;font-weight:500">/mo</span></div>' +
            '<div class="keja-type">' + prop.property_type + (prop.bedrooms ? ' · ' + prop.bedrooms + ' bd' : '') + '</div>' +
            '<div class="keja-location">' + [prop.area, prop.county].filter(Boolean).join(", ") + '</div>' +
            (prop.proximity_note ? '<div class="keja-proximity" style="margin-top:8px">' + prop.proximity_note + '</div>' : '') +
            '</div>';
        return el;
    }

    function renderTop() {
        stage.querySelectorAll(".keja-swipe-card").forEach(function (c) { c.remove(); });
        if (!queue.length) {
            emptyState.style.display = "block";
            return;
        }
        emptyState.style.display = "none";
        queue.slice(0, 3).forEach(function (p, i) {
            const el = cardEl(p, i);
            stage.appendChild(el);
            if (i === 0) attachDrag(el, p);
        });
    }

    async function commitSwipe(prop, direction, el) {
        queue.shift();
        el.remove();
        renderTop();
        try {
            await Keja.api("/properties/" + prop.id + "/swipe?direction=" + direction, { method: "POST" });
        } catch (e) {
            console.warn("[Keja] swipe record failed", e);
        }
    }

    function attachDrag(el, prop) {
        let startX = 0, startY = 0, dx = 0, dy = 0, dragging = false;
        const stampR = el.querySelector(".keja-swipe-stamp.right");
        const stampL = el.querySelector(".keja-swipe-stamp.left");

        function onDown(x, y) {
            dragging = true; startX = x; startY = y;
            el.style.transition = "none";
        }
        function onMove(x, y) {
            if (!dragging) return;
            dx = x - startX; dy = y - startY;
            el.style.transform = "translate(" + dx + "px," + dy + "px) rotate(" + (dx / 18) + "deg)";
            stampR.style.opacity = Math.max(0, Math.min(1, dx / 90));
            stampL.style.opacity = Math.max(0, Math.min(1, -dx / 90));
        }
        function onUp() {
            if (!dragging) return;
            dragging = false;
            el.style.transition = "transform .25s ease";
            if (dx > 110) {
                el.style.transform = "translate(600px," + dy + "px) rotate(20deg)";
                setTimeout(function () { commitSwipe(prop, "right", el); }, 180);
            } else if (dx < -110) {
                el.style.transform = "translate(-600px," + dy + "px) rotate(-20deg)";
                setTimeout(function () { commitSwipe(prop, "left", el); }, 180);
            } else if (dy < -120) {
                location.href = "property.html?id=" + prop.id;
            } else {
                el.style.transform = "translate(0,0)";
                stampR.style.opacity = 0; stampL.style.opacity = 0;
            }
            dx = 0; dy = 0;
        }

        el.addEventListener("pointerdown", function (e) { el.setPointerCapture(e.pointerId); onDown(e.clientX, e.clientY); });
        el.addEventListener("pointermove", function (e) { onMove(e.clientX, e.clientY); });
        el.addEventListener("pointerup", onUp);
        el.addEventListener("pointercancel", onUp);

        el.addEventListener("click", function (e) {
            if (Math.abs(dx) < 5 && Math.abs(dy) < 5) {
                location.href = "property.html?id=" + prop.id;
            }
        });
    }

    // ---- Filters modal ----
    const filterModal = document.getElementById("filterModal");
    document.getElementById("filterBtn").onclick = function () { filterModal.style.display = "block"; };
    document.getElementById("closeFiltersBtn").onclick = function () { filterModal.style.display = "none"; };
    document.getElementById("filterBackdrop").addEventListener("click", function (e) {
        if (e.target === this) filterModal.style.display = "none";
    });
    document.getElementById("applyFiltersBtn").onclick = function () {
        filters = {
            county: document.getElementById("fCounty").value,
            area: document.getElementById("fArea").value.trim(),
            min_price: document.getElementById("fMin").value,
            max_price: document.getElementById("fMax").value,
            property_type: document.getElementById("fType").value,
        };
        filterModal.style.display = "none";
        fetchQueue();
    };
    document.getElementById("resetFiltersBtn").onclick = function () {
        filters = {};
        ["fCounty", "fArea", "fMin", "fMax", "fType"].forEach(function (id) { document.getElementById(id).value = ""; });
        fetchQueue();
    };

    const initialQ = new URLSearchParams(location.search).get("q");
    if (initialQ) document.getElementById("fArea").value = initialQ;

    populateCounties();
    fetchQueue();
})();
