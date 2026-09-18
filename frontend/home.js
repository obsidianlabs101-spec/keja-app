(function () {
    Keja.requireAuth();
    Keja.renderNav("home");
    Keja.renderAd("adSlotTop");

    const user = Keja.getUser();
    const hour = new Date().getHours();
    const timeGreeting = hour < 12 ? "Good morning" : hour < 17 ? "Good afternoon" : "Good evening";
    document.getElementById("greeting").textContent = timeGreeting + (user && user.name ? ", " + user.name.split(" ")[0] : "") + " 👋";
    const avatar = document.getElementById("avatar");
    if (user && user.profile_pic_url) {
        avatar.innerHTML = '<img src="' + resolveMedia(user.profile_pic_url) + '">';
    } else if (user && user.name) {
        avatar.textContent = user.name.trim()[0].toUpperCase();
    }

    function resolveMedia(url) {
        if (!url) return "";
        if (url.startsWith("http")) return url;
        return window.BASH_API_BASE_URL + "/" + url.replace(/^\/+/, "");
    }

    function cardHtml(p) {
        const img = p.main_image_url ? resolveMedia(p.main_image_url) : "";
        const badge = p.is_booked ? '<span class="keja-card-badge booked">Booked</span>' : "";
        return (
            '<div class="keja-card" data-id="' + p.id + '">' +
            '<div class="keja-card-img" style="background-image:url(\'' + img + '\')">' + badge + '</div>' +
            '<div class="keja-card-body">' +
            '<div class="keja-price">' + Keja.fmtPrice(p.price) + '</div>' +
            '<div class="keja-type">' + p.property_type + '</div>' +
            '<div class="keja-location">' + [p.area, p.county].filter(Boolean).join(", ") + '</div>' +
            (p.proximity_note ? '<div class="keja-proximity">' + p.proximity_note + '</div>' : '') +
            '</div></div>'
        );
    }

    function bindCards(container) {
        container.querySelectorAll(".keja-card").forEach(function (el) {
            el.addEventListener("click", function () {
                location.href = "property.html?id=" + el.dataset.id;
            });
        });
    }

    async function loadSections() {
        try {
            const recent = await Keja.api("/properties/?limit=12");
            const recEl = document.getElementById("recommended");
            const nearEl = document.getElementById("nearPopular");
            const gridEl = document.getElementById("recentGrid");

            if (!recent.length) {
                recEl.innerHTML = '<div class="keja-empty">No listings yet — check back soon.</div>';
                nearEl.innerHTML = "";
                gridEl.innerHTML = '<div class="keja-empty">No listings yet.</div>';
                return;
            }

            recEl.innerHTML = recent.slice(0, 8).map(cardHtml).join("");
            bindCards(recEl);

            const nairobi = recent.filter(function (p) { return (p.county || "").toLowerCase().includes("nairobi"); });
            nearEl.innerHTML = (nairobi.length ? nairobi : recent).slice(0, 8).map(cardHtml).join("");
            bindCards(nearEl);

            gridEl.innerHTML = recent.slice(0, 6).map(cardHtml).join("");
            bindCards(gridEl);
        } catch (e) {
            console.warn("[Keja] failed to load home sections", e);
        }
    }

    document.getElementById("searchForm").addEventListener("submit", function (e) {
        e.preventDefault();
        const q = document.getElementById("searchInput").value.trim();
        location.href = "discover.html" + (q ? "?q=" + encodeURIComponent(q) : "");
    });

    loadSections();
})();
