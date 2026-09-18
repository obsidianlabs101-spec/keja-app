(function () {
    Keja.requireAuth();
    Keja.renderNav("interested");

    const grid = document.getElementById("grid");

    function resolveMedia(url) {
        if (!url) return "";
        if (url.startsWith("http")) return url;
        return window.BASH_API_BASE_URL + "/" + url.replace(/^\/+/, "");
    }

    function cardHtml(p) {
        const badge = p.is_booked ? '<span class="keja-card-badge booked">Booked</span>' : "";
        return (
            '<div class="keja-card" data-id="' + p.id + '">' +
            '<div class="keja-card-img" style="background-image:url(\'' + resolveMedia(p.main_image_url) + '\')">' + badge + '</div>' +
            '<div class="keja-card-body">' +
            '<div class="keja-price">' + Keja.fmtPrice(p.price) + '</div>' +
            '<div class="keja-type">' + p.property_type + '</div>' +
            '<div class="keja-location">' + [p.area, p.county].filter(Boolean).join(", ") + '</div>' +
            '</div></div>'
        );
    }

    async function load() {
        try {
            const list = await Keja.api("/properties/interested");
            if (!list.length) {
                grid.innerHTML = '<div class="keja-empty" style="grid-column:1/-1">Nothing saved yet — swipe right on something you like in Discover.</div>';
                return;
            }
            grid.innerHTML = list.map(cardHtml).join("");
            grid.querySelectorAll(".keja-card").forEach(function (el) {
                el.addEventListener("click", function () { location.href = "property.html?id=" + el.dataset.id; });
            });
        } catch (e) {
            grid.innerHTML = '<div class="keja-empty" style="grid-column:1/-1">Couldn\'t load your saved listings.</div>';
        }
    }

    load();
})();
