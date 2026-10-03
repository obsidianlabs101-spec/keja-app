/* One place to edit the details that appear on every legal page.
   Change the values below, redeploy, and all pages update. */
window.KEJA_LEGAL = {
  company: "Obsidian Labs",                 // the business operating Keja
  email: "support@YOUR-DOMAIN.co.ke",       // <-- put your real support email
  phone: "+254 7XX XXX XXX",                // <-- optional support phone / WhatsApp
  address: "Nairobi, Kenya",                // <-- registered / postal address
  odpcReg: "",                              // <-- ODPC registration number if you have one (leave blank otherwise)
  effective: "3 October 2026"
};
document.addEventListener("DOMContentLoaded", function () {
  var c = window.KEJA_LEGAL;
  document.querySelectorAll("[data-fill]").forEach(function (el) {
    var k = el.getAttribute("data-fill"), v = c[k];
    if (!v) { if (k === "odpcReg") el.closest("[data-optional]") && (el.closest("[data-optional]").style.display = "none"); return; }
    if (k === "email") { el.innerHTML = '<a href="mailto:' + v + '">' + v + "</a>"; } else { el.textContent = v; }
  });
});
