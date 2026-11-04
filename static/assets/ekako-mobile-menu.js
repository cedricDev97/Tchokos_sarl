/* eKAKO menu mobile V1 : sans changement du panier ni du code des commandes. */
(function () {
  function init() {
    const toggle = document.getElementById("ekakoMobileMenuBtn");
    if (!toggle) return;
    const header = toggle.closest("header");
    if (!header) return;
    const mobile = window.matchMedia("(max-width: 760px)");

    // Dans la boutique, placer le bouton panier sur la barre supérieure sur mobile.
    const topbar = header.querySelector(".topbar");
    const actions = header.querySelector("#ekakoMobileActions");
    const cart = document.getElementById("openCheckoutBtn");

    function closeMenu() {
      header.classList.remove("ekako-menu-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "Ouvrir le menu");
      toggle.textContent = "☰";
    }

    function adapt() {
      if (topbar && actions && cart) {
        if (mobile.matches && cart.parentElement !== topbar) {
          topbar.insertBefore(cart, toggle);
        } else if (!mobile.matches && cart.parentElement !== actions) {
          actions.appendChild(cart);
        }
      }
      if (!mobile.matches) closeMenu();
    }

    toggle.addEventListener("click", function () {
      const opening = !header.classList.contains("ekako-menu-open");
      header.classList.toggle("ekako-menu-open", opening);
      toggle.setAttribute("aria-expanded", String(opening));
      toggle.setAttribute("aria-label", opening ? "Fermer le menu" : "Ouvrir le menu");
      toggle.textContent = opening ? "✕" : "☰";
    });

    header.querySelectorAll(".nav-links a, .ekako-store-nav a, .ekako-store-nav button").forEach(function (link) {
      link.addEventListener("click", closeMenu);
    });
    document.addEventListener("keydown", function (event) {
      if (event.key === "Escape" && header.classList.contains("ekako-menu-open")) {
        closeMenu();
        toggle.focus();
      }
    });
    document.addEventListener("click", function (event) {
      if (mobile.matches && !header.contains(event.target)) closeMenu();
    });
    if (mobile.addEventListener) mobile.addEventListener("change", adapt);
    else if (mobile.addListener) mobile.addListener(adapt);
    adapt();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", init);
  else init();
})();
