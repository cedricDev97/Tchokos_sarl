(function () {
  const enabled = document.body.dataset.ekakoTurnstileEnabled === "1";
  const sitekey = document.body.dataset.ekakoTurnstileSitekey || "";
  window.ekakoGetTurnstileToken = async function (action) {
    if (!enabled) return "";
    const box = document.getElementById("ekakoTurnstileContainer");
    if (!sitekey || !window.turnstile || !box) throw new Error("Vérification anti-robot indisponible. Rechargez cette page.");
    box.replaceChildren();
    box.style.display = "block";
    try {
      return await new Promise(function (resolve, reject) {
        let finished = false;
        const done = (error, token) => {
          if (finished) return;
          finished = true;
          if (error) reject(error);
          else resolve(token);
        };
        try {
          const widget = turnstile.render(box, {
            sitekey, action, execution: "execute", appearance: "interaction-only",
            callback: token => done(null, token),
            "error-callback": () => done(new Error("Vérification anti-robot échouée.")),
            "expired-callback": () => done(new Error("Vérification expirée. Réessayez.")),
          });
          turnstile.execute(widget);
        } catch (e) { done(e); }
      });
    } finally {
      box.replaceChildren();
      box.style.display = "none";
    }
  };
})();
