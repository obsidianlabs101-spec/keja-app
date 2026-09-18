(function () {
    Keja.requireAuth();
    Keja.renderNav("profile");

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

    async function render() {
        const user = (await Keja.refreshCurrentUser()) || Keja.getUser();
        if (!user) return;

        document.getElementById("pName").textContent = user.name || user.username || "Keja user";
        document.getElementById("pEmail").textContent = user.email || "";
        const avatar = document.getElementById("avatar");
        if (user.profile_pic_url) {
            avatar.innerHTML = '<img src="' + resolveMedia(user.profile_pic_url) + '" style="width:100%;height:100%;border-radius:50%;object-fit:cover">';
        } else if (user.name) {
            avatar.textContent = user.name.trim()[0].toUpperCase();
        }

        // Referral card — disappears for good once the one-time bonus
        // has been earned (referral_bonus_granted), per Keja's
        // "refer once, earn once" contact-credit rule.
        if (!user.referral_bonus_granted) {
            const card = document.getElementById("referralCard");
            card.style.display = "block";
            document.getElementById("refCode").textContent = user.referral_code || "—";
            document.getElementById("copyRefBtn").onclick = function () {
                const link = location.origin + location.pathname.replace(/profile\.html$/, "index.html") + "?ref=" + (user.referral_code || "");
                navigator.clipboard.writeText(link).then(function () { toast("Referral link copied!"); });
            };
        }

        if ((user.free_contact_credits || 0) > 0) {
            document.getElementById("creditsRow").style.display = "flex";
            document.getElementById("creditsCount").textContent = user.free_contact_credits;
        }
    }

    const themeSwitch = document.getElementById("themeSwitch");
    function syncThemeSwitch() {
        const on = document.documentElement.getAttribute("data-theme") === "dark";
        themeSwitch.classList.toggle("on", on);
    }
    themeSwitch.addEventListener("click", function () {
        Keja.toggleTheme();
        syncThemeSwitch();
    });
    syncThemeSwitch();

    document.getElementById("logoutBtn").addEventListener("click", function () {
        Keja.clearSession();
        location.href = "index.html";
    });

    render();
})();
