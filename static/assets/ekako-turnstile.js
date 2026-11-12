/* Un nouveau widget et un nouveau jeton sont créés à chaque tentative. */
(function () {
  "use strict";
  const enabled = document.body.dataset.ekakoTurnstileEnabled === "1";
  const sitekey = document.body.dataset.ekakoTurnstileSitekey || "";

  async function waitForAPI() {
    for (let elapsed = 0; elapsed < 10000; elapsed += 100) {
      if (window.turnstile) return window.turnstile;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    throw new Error("La vérification anti-robot ne répond pas. Vérifiez la connexion.");
  }

  window.ekakoGetTurnstileToken = async function (action) {
    if (!enabled) return "";
    const box = document.getElementById("ekakoTurnstileContainer");
    if (!sitekey || !box) throw new Error("Protection anti-robot mal configurée.");
    const turnstile = await waitForAPI();

    box.replaceChildren();
    box.style.display = "block";
    let widgetId = null;
    try {
      return await new Promise(function (resolve, reject) {
        let finished = false;
        const deadline = setTimeout(
          () => finish(new Error("Vérification trop longue. Réessayez.")),
          90000
        );
        function finish(err, token) {
          if (finished) return;
          finished = true;
          clearTimeout(deadline);
          if (err) reject(err);
          else resolve(token);
        }
        try {
          widgetId = turnstile.render(box, {
            sitekey: sitekey,
            action: action,
            execution: "execute",
            appearance: "interaction-only",
            callback: token => finish(null, token),
            "error-callback": () => finish(new Error("Vérification anti-robot échouée.")),
            "expired-callback": () => finish(new Error("Vérification expirée. Réessayez.")),
            "timeout-callback": () => finish(new Error("Vérification expirée. Réessayez.")),
          });
          turnstile.execute(widgetId);
        } catch (err) {
          finish(err);
        }
      });
    } finally {
      if (widgetId !== null) {
        try { turnstile.remove(widgetId); } catch (_) {}
      }
      box.replaceChildren();
      box.style.display = "none";
    }
  };
})();
