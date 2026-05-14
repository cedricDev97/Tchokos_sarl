function getCookie(name){
  const cookies = document.cookie ? document.cookie.split(";") : [];
  for (let i = 0; i < cookies.length; i++) {
    const c = cookies[i].trim();
    if (c.startsWith(name + "=")) {
      return decodeURIComponent(c.substring(name.length + 1));
    }
  }
  return "";
}

function normalizeVariantValue(v){
  return String(v ?? "").trim();
}

function formatStatusLabel(status){
  const s = (status || "").toLowerCase();
  const map = {
    received: "Reçue",
    preparing: "Préparation",
    shipped: "Expédiée",
    delivered: "Livrée",
    cancelled: "Annulée",
    failed: "Échouée",
  };
  return map[s] || status || "—";
}

function getVariantLabel(product){
  const type = product?.variant_type || "shoe_size";

  if(type === "shoe_size") return "Pointure";
  if(type === "clothing_size") return "Taille";
  if(type === "color") return "Couleur";
  if(type === "capacity") return "Capacité";
  if(type === "unique") return "Option";
  return "Option";
}

function isPackEligible(product){
  const type = product?.variant_type || "shoe_size";
  return type === "shoe_size" || type === "clothing_size";
}

function formatVariantValue(product, value){
  const type = product?.variant_type || "shoe_size";
  const v = value ?? "";

  if(type === "shoe_size") return `${v}`;
  return `${v}`;
}

function formatVariantStockLabel(product, value){
  const label = getVariantLabel(product);
  return `${label} ${formatVariantValue(product, value)}`;
}

function formatLastActivity(activity){
  if(!activity) return "—";

  const newLabel = formatStatusLabel(activity.new);
  const atText = activity.at ? new Date(activity.at).toLocaleString() : "";

  if(atText){
    return `${newLabel} • ${atText}`;
  }
  return newLabel || "—";
}

async function loadResellerTopProducts(){
  try{
    const res = await fetch("/api/reseller/me/top-products/");
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch(_) {}

    if(!res.ok || !data.ok){
      throw new Error(data.error || text.slice(0, 200) || "Erreur top produits");
    }

    const rows = data.results || [];
    const box = byId("resellerTopProducts");
    if(!box) return;

    box.innerHTML = rows.length
      ? rows.map(r=>`
          <div class="row" style="justify-content:space-between; padding:8px 0; border-bottom:1px dashed rgba(15,23,42,.08);">
            <div>
              <div style="font-weight:800">${r.product_name}</div>
              <div class="mini">${r.sku}</div>
            </div>
            <div class="pill">${r.qty}</div>
          </div>
        `).join("")
      : `<div class="muted">Aucune donnée pour le moment.</div>`;
  }catch(e){
    const box = byId("resellerTopProducts");
    if(box){
      box.innerHTML = `<div class="muted">Erreur: ${e.message}</div>`;
    }
  }
}

function getResellerPaymentRowClass(paymentStatus){
  const s = (paymentStatus || "").toLowerCase();
  if(s === "unpaid") return "reseller-row-unpaid";
  if(s === "pending") return "reseller-row-pending";
  if(s === "failed") return "reseller-row-failed";
  return "";
}

function getResellerPaymentFlag(paymentStatus){
  const s = (paymentStatus || "").toLowerCase();

  if(s === "unpaid"){
    return `<div class="reseller-action-flag warn">Action requise</div>`;
  }
  if(s === "pending"){
    return `<div class="reseller-action-flag pending">Vérification en cours</div>`;
  }
  if(s === "failed"){
    return `<div class="reseller-action-flag danger">Paiement à reprendre</div>`;
  }
  return "";
}

async function openOrderDetail(orderNo){
  const modal = byId("orderDetailModal");
  const body = byId("orderDetailBody");
  modal.style.display = "flex";
  body.innerHTML = `<div class="muted">Chargement...</div>`;

  try{
    const [detailRes, timelineRes] = await Promise.all([
      fetch(`/api/admin/order/${encodeURIComponent(orderNo)}/`),
      fetch(`/api/admin/orders/${encodeURIComponent(orderNo)}/timeline/`)
    ]);

    const detailData = await detailRes.json().catch(()=>({}));
    const timelineData = await timelineRes.json().catch(()=>({}));

    if(!detailRes.ok || !detailData.ok){
      throw new Error(detailData.error || "Erreur détail commande");
    }

    const o = detailData.order;
    const logs = (timelineData.ok && Array.isArray(timelineData.logs)) ? timelineData.logs : [];
    const wa = `https://wa.me/237${String(o.phone||"").replace(/\D/g,"")}`;
    const paidAtText = o.paid_at ? new Date(o.paid_at).toLocaleString() : "—";

    body.innerHTML = `
      <div class="orderDetailCard">
        <div class="orderDetailHeader">
          <div class="orderDetailMeta">
            <div style="font-weight:900; font-size:18px;">${o.orderNo}</div>
            <div class="muted">${o.createdAt ? new Date(o.createdAt).toLocaleString() : ""}</div>
            <div>${statusBadge(o.status)}</div>
            <div>${paymentBadge(o.payment_status)}</div>
          </div>

          <div class="orderDetailAmount">
            <div class="bigTotal">${money(o.total||0)}</div>
            <div class="muted">${o.mode || ""} • ${o.pay_method || ""}</div>
          </div>
        </div>
      </div>

      <div class="orderDetailCard">
        <div class="orderDetailSectionTitle">Paiement</div>

        <div style="margin-bottom:10px;">
          <div class="orderDetailLabel">Référence paiement</div>
          <input class="text" id="paymentRefInput" value="${o.payment_ref || ""}" placeholder="Ex: MTN-84738291">
        </div>

        ${adminPermissions.payments ? `
          <div class="orderDetailActions">
            <button class="btn small primary" onclick="markOrderPaid('${o.orderNo}')">Marquer payé</button>
            <button class="btn small warn" onclick="markOrderPaymentPending('${o.orderNo}')">Mettre en attente</button>
            <button class="btn small danger" onclick="markOrderPaymentFailed('${o.orderNo}')">Paiement échoué</button>
          </div>
      ` : ``}

        <div class="orderDetailGrid" style="margin-top:12px;">
          <div>
            <div class="orderDetailLabel">Référence</div>
            <div class="orderDetailValue">${o.payment_ref || "—"}</div>
          </div>
          <div>
            <div class="orderDetailLabel">Date paiement</div>
            <div class="orderDetailValue">${paidAtText}</div>
          </div>
        </div>
      </div>

      <div class="orderDetailCard">
        <div class="orderDetailSectionTitle">Client</div>
        <div class="orderDetailGrid">
          <div>
            <div class="orderDetailLabel">Nom</div>
            <div class="orderDetailValue">${o.name || ""}</div>
          </div>
          <div>
            <div class="orderDetailLabel">Téléphone</div>
            <div class="orderDetailValue">${o.phone || ""} • <a href="${wa}" target="_blank">WhatsApp</a></div>
          </div>
          <div>
            <div class="orderDetailLabel">Zone</div>
            <div class="orderDetailValue">${o.city || ""} / ${o.quarter || ""}</div>
          </div>
          <div>
            <div class="orderDetailLabel">Adresse</div>
            <div class="orderDetailValue">${o.address || ""}</div>
          </div>
        </div>
      </div>

      <div class="orderDetailCard">
        <div class="orderDetailSectionTitle">Articles</div>
        <div>
          ${(o.items||[]).map(it=>`
            <div class="orderItemRow">
              <div>
                <div class="orderItemName">${it.name}</div>
                <div class="orderItemMeta">${it.sku} • Option ${it.size} • x${it.qty} • ${money(it.unit_price)}</div>
              </div>
              <div class="orderItemTotal">${money(it.line_total)}</div>
            </div>
          `).join("")}
        </div>

        <div style="margin-top:12px; display:flex; flex-direction:column; gap:6px;">
          <div class="row" style="justify-content:space-between;"><div class="muted">Sous-total</div><div>${money(o.subtotal||0)}</div></div>
          <div class="row" style="justify-content:space-between;"><div class="muted">Livraison</div><div>${money(o.shipping||0)}</div></div>
          <div class="row" style="justify-content:space-between;"><div style="font-weight:900">Total</div><div style="font-weight:900">${money(o.total||0)}</div></div>
        </div>
      </div>

      <div class="orderDetailCard">
        <div class="orderDetailSectionTitle">Historique</div>
        ${
          logs.length ? `
            <div class="timelineList">
              ${logs.map(l=>`
                <div class="timelineItem">
                  <div class="timelineTop">
                    <div>
                      <div class="timelineTitle">${formatStatusLabel(l.old)} → ${formatStatusLabel(l.new)}</div>
                      <div class="timelineMeta">${l.by ? `par ${l.by}` : "par système"}</div>
                    </div>
                    <div class="timelineDate">${l.at ? new Date(l.at).toLocaleString() : ""}</div>
                  </div>

                  ${l.note ? `
                    <div class="timelineNote">
                      <div class="timelineNoteTitle">Note</div>
                      <div class="muted">${l.note}</div>
                    </div>
                  ` : ""}
                </div>
              `).join("")}
            </div>
          ` : `<div class="muted">Aucun historique.</div>`
        }
      </div>
    `;
  }catch(e){
    body.innerHTML = `<div class="muted">Erreur: ${e.message}</div>`;
  }
}

async function updatePaymentStatus(orderNo, payment_status, payment_ref = ""){
  try{
    const data = await apiPost(`/api/admin/order/${encodeURIComponent(orderNo)}/payment-status/`, {
      payment_status,
      payment_ref
    });

    if(!data.ok){
      alert(data.error || "Erreur paiement.");
      return;
    }

    await renderDashboard();
    await openOrderDetail(orderNo);
  }catch(err){
    alert(err?.error || err?.message || "Erreur réseau / serveur.");
  }
}

function markOrderPaid(orderNo){
  const currentRef = (byId("paymentRefInput")?.value || "").trim();
  const ref = prompt("Référence paiement (optionnel) :", currentRef);

  // si l'utilisateur annule le prompt
  if(ref === null) return;

  updatePaymentStatus(orderNo, "paid", ref.trim());
}

function markOrderPaymentPending(orderNo){
  updatePaymentStatus(orderNo, "pending");
}

function markOrderPaymentFailed(orderNo){
  updatePaymentStatus(orderNo, "failed");
}

function openAuthModal(tab = "login"){            
  const m = byId("authModal");
  if(!m) return;
  m.style.display = "flex";
  switchAuthTab(tab);
  hideAuthNote();
}

function closeAuthModal(){
  const m = byId("authModal");
  if(m) m.style.display = "none";
}

function showAuthNote(msg){    
  const n = byId("authNote");
  if(!n) return;
  n.style.display = "block";
  n.textContent = msg;
}

function hideAuthNote(){
  const n = byId("authNote");
  if(!n) return;
  n.style.display = "none";
  n.textContent = "";
}

function switchAuthTab(tab){
  const loginPanel = byId("authLoginPanel");
  const registerPanel = byId("authRegisterPanel");
  const loginBtn = byId("authTabLogin");
  const registerBtn = byId("authTabRegister");

  if(tab === "register"){
    if(loginPanel) loginPanel.style.display = "none";
    if(registerPanel) registerPanel.style.display = "block";
    if(loginBtn){
      loginBtn.classList.remove("primary");
    }
    if(registerBtn){
      registerBtn.classList.add("primary");
    }
  }else{
    if(loginPanel) loginPanel.style.display = "block";
    if(registerPanel) registerPanel.style.display = "none";
    if(loginBtn){
      loginBtn.classList.add("primary");
    }
    if(registerBtn){
      registerBtn.classList.remove("primary");
    }
  }

  hideAuthNote();
}

async function apiPost(url, data) {
  const csrftoken = getCookie("csrftoken");

  const res = await fetch(url, {
    method: "POST",
    credentials: "same-origin", // ✅ envoie cookies (session + csrftoken)
    headers: {
      "Content-Type": "application/json",
      "X-CSRFToken": csrftoken, // ✅ CSRF Django
    },
    body: JSON.stringify(data || {}),
  });

  const text = await res.text();
  let json;
  try { json = JSON.parse(text); } catch { json = { ok:false, error:text.slice(0,250) }; }

  if (!res.ok) throw json;
  return json;
}


const SHIPPING = {
    "Douala": { base: 1500, quarters: {"Akwa":500, "Bonamoussadi":700, "Deido":600, "Logpom":900, "PK14":1200, "Autre":1400} },
    "Yaounde":{ base: 2500, quarters: {"Bastos":900, "Mvan":700, "Nlongkak":800, "Emana":900, "Autre":1200} },
    "Kribi":  { base: 2000, quarters: {"Centre":700, "Beach":900, "Autre":1100} },
    "Bafoussam": { base: 3000, quarters: {"Centre":800, "Autre":1200} },
    "Autre": { base: 4000, quarters: {"Autre":1000} }
  };
  const ORDER_STEPS = ["Commande recue","Preparation","Expediee","Livree"];
  const LS = { STOCK:"tchokos_v5_stock_by_size", ORDERS:"tchokos_v5_orders" };

  const STATUS_META = {
  received:   { label: "Reçue", cls: "pill pill-received" },
  preparing:  { label: "Préparation", cls: "pill pill-preparing" },
  shipped:    { label: "Expédiée", cls: "pill pill-shipped" },
  delivered:  { label: "Livrée", cls: "pill pill-delivered" },
  cancelled:  { label: "Annulée", cls: "pill pill-cancelled" },
  failed:     { label: "Échouée", cls: "pill pill-failed" },
};

const PAYMENT_META = {
  unpaid:  { label: "Non payé", cls: "pill pill-failed" },
  pending: { label: "En attente", cls: "pill pill-preparing" },
  paid:    { label: "Payé", cls: "pill pill-delivered" },
  failed:  { label: "Paiement échoué", cls: "pill pill-failed" },
};

function paymentBadge(status){
  const s = (status || "").toLowerCase();
  const m = PAYMENT_META[s] || { label: s || "—", cls: "pill" };
  return `<span class="${m.cls}">${m.label}</span>`;
}

function statusBadge(status){
  const s = (status || "").toLowerCase();
  const m = STATUS_META[s] || { label: s || "—", cls: "pill" };
  return `<span class="${m.cls}">${m.label}</span>`;
}


  let products = [];
  let stockMap = {}; 
 async function loadProductsFromApi(){
  const res = await fetch("/api/products/");
  const data = await res.json();

  stockMap = {};

  products = (data.results || []).map(p => {
    stockMap[p.sku] = {};

    (p.variants || []).forEach(v => {
      const option = normalizeVariantValue(v.size);
      stockMap[p.sku][option] = Number(v.stock_qty ?? 0);
    });

    return {
      id: p.sku,
      brand: p.brand || "",
      name: p.name || "",
      cat: p.category || "",
      tag: p.tag || "",
      desc: p.description || "",
      sizes: (p.variants || []).map(v => normalizeVariantValue(v.size)),
      retail: p.retail_price || 0,
      reseller: p.reseller_price || 0,
      image_url: p.image_url || null,
      moq: p.reseller_moq || 1,
      variant_type: p.variant_type || "shoe_size"
    };
  });

  buildPacksFromProducts();
}

function buildPacksFromProducts() {
  packs = products
    .filter(p => {
      const hasResellerPrice = Number(p.reseller_price || p.reseller || 0) > 0;
      const eligibleType = isPackEligible(p);
      const hasVariants = Array.isArray(p.sizes) && p.sizes.length > 0;
      return hasResellerPrice && eligibleType && hasVariants;
    })
    .map(p => {
      const sku = p.sku || p.id;
      const moq = Number(p.reseller_moq || p.moq || 1);

      const sizes = Object.keys(stockMap[sku] || {})
        .map(x => normalizeVariantValue(x))
        .filter(Boolean)
        .sort((a,b)=>String(a).localeCompare(String(b), "fr", {numeric:true}));

      const dist = {};
      sizes.forEach(s => (dist[s] = 0));

      const available = sizes.filter(s => (stockMap[sku]?.[s] || 0) > 0);
      const useSizes = available.length ? available : sizes;

      if (useSizes.length) {
        let left = moq;
        let i = 0;
        while (left > 0) {
          dist[useSizes[i % useSizes.length]] += 1;
          left--;
          i++;
        }
      }

      const resellerUnit = Number(p.reseller_price || p.reseller || 0);
      const packPrice = resellerUnit * moq;
      const variantLabel = getVariantLabel(p);

      return {
        id: `PK-${sku}`,
        sku,
        title: `Pack ${p.name} (${moq} unités)`,
        moq,
        packPrice,
        defaultDist: dist,
        image_url: p.image_url,
        variant_type: p.variant_type || "shoe_size",
        variant_label: variantLabel,
      };
    });
}

  let packs = [];
  async function loadPacksFromApi(){
  const res = await fetch("/api/packs/");
  const data = await res.json();
  packs = (data.results || []).map(p => {
    return {
      id: p.id,
      title: p.title || "",
      sku: p.sku || "",
      packPrice: p.packPrice || 0,
      defaultDist: p.defaultDist || {}
    };
  });
  renderPacks();
}

  let role = "visitor"; // visitor / reseller / admin
  let mode = "retail"; // retail / reseller
  let adminPermissions = {
    super_admin: false,
    orders: false,
    payments: false,
    inventory: false,
    resellers: false,
    }; // pour affiner les droits admin (ex: gestion commandes, gestion produits, etc)
  let cart = [];
  let selectedProductId = null;
  let query = "", brand = "ALL", cat = "ALL";
  let adminOrdersCache = [];
  let adminStatsCache = null;
  let adminAnalyticsCache = null;
  let resellerOrdersCache = [];

  const byId = id => document.getElementById(id);
  const money = n => new Intl.NumberFormat("fr-FR").format(n) + " FCFA";
  const getProduct = sku => products.find(p=>p.id===sku);
  const priceOf = p => (mode==="reseller" ? p.reseller : p.retail);


  async function logout(){
  const csrf =
    (document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")) ||
    (byId("csrfToken")?.value) || "";

  try{
    await fetch("/api/admin/logout/", {
      method: "POST",
      headers: { "X-CSRFToken": csrf }
    });
  }catch(e){}

  await syncRoleFromBackend();
  renderAll();
  goTab("shop");
}

function syncRoleUI(){
  if(byId("roleLabel")){
    byId("roleLabel").textContent =
      role === "visitor" ? "Visiteur" :
      (role === "reseller" ? "Revendeur" : "Admin");
  }

  if(byId("modeLabel")){
    byId("modeLabel").textContent = mode === "reseller" ? "Revendeur" : "Detail";
  }

  if(byId("resellerGate")){
    byId("resellerGate").style.display = (role === "reseller" ? "none" : "block");
  }
  if(byId("resellerPanel")){
    byId("resellerPanel").style.display = (role === "reseller" ? "block" : "none");
  }
  if(role === "reseller"){
  switchResellerTab("overview");
  loadResellerStats();
  loadResellerTopProducts();
  renderResellerOrders();
  closeResellerOrderDetail();
}

  if(byId("adminGate")){
    byId("adminGate").style.display = (role === "admin" ? "none" : "block");
  }
  if(byId("adminPanel")){
    byId("adminPanel").style.display = (role === "admin" ? "block" : "none");
  }

  const applyBtn = byId("applyResellerBtn");
  if(applyBtn){
    applyBtn.style.display = (role === "admin" || role === "reseller") ? "none" : "inline-flex";
  }

  // ===== Permissions fines admin =====
  const ordersSection = byId("adminOrdersSection");
  const inventorySection = byId("adminInventorySection");
  const resellerAppsSection = byId("adminResellersSection");
  const analyticsSection = byId("adminAnalyticsSection");

  if(role !== "admin"){
    if(ordersSection) ordersSection.style.display = "";
    if(inventorySection) inventorySection.style.display = "";
    if(resellerAppsSection) resellerAppsSection.style.display = "";
    if(analyticsSection) analyticsSection.style.display = "";
    return;
  }

  if(ordersSection){
  ordersSection.style.display = (adminPermissions.orders || adminPermissions.payments) ? "" : "none";
  }

  if(inventorySection){
    inventorySection.style.display = adminPermissions.inventory ? "" : "none";
  }

  if(resellerAppsSection){
    resellerAppsSection.style.display = adminPermissions.resellers ? "" : "none";
  }

  // analytics rattaché aux commandes pour l’instant
  if(analyticsSection){
    analyticsSection.style.display = adminPermissions.orders ? "" : "none";
  }
}

  function initStockIfMissing(){
    if(localStorage.getItem(LS.STOCK)) return;
    const seed = {};
    products.forEach(p=>{
      seed[p.id] = {};
      p.sizes.forEach(s=> seed[p.id][s] = 8);
    });
    localStorage.setItem(LS.STOCK, JSON.stringify(seed));
  }
  function getStock(){ try{ return JSON.parse(localStorage.getItem(LS.STOCK) || "{}"); }catch(e){ return {}; } }
  function setStock(stock){ localStorage.setItem(LS.STOCK, JSON.stringify(stock)); }
  function stockOf(sku, size){
  const key = normalizeVariantValue(size);
  return Number(stockMap?.[sku]?.[key] ?? 0);
}

  function totalStockOfSku(sku){
  const sizes = stockMap?.[sku] || {};
  return Object.values(sizes).reduce((a,b)=>a+Number(b||0),0);
}

  function adjustStock(sku, size, delta){
  const key = normalizeVariantValue(size);
  stockMap[sku] = stockMap[sku] || {};
  const cur = Number(stockMap[sku][key] ?? 0);
  stockMap[sku][key] = Math.max(0, cur + delta);
}

  function validateStock(sku, size, qty){
  const option = normalizeVariantValue(size);
  const available = stockOf(sku, option);

  if(qty > available){
    return {
      ok:false,
      msg:`Stock insuffisant pour ${sku} option ${option}. Dispo: ${available}`
    };
  }

  return {ok:true};
}

  function initCityQuarter(){
    const citySel = byId("cCity");
    citySel.innerHTML = "";
    Object.keys(SHIPPING).forEach(c=>{
      const opt = document.createElement("option");
      opt.value = c; opt.textContent = c;
      citySel.appendChild(opt);
    });
    citySel.addEventListener("change", ()=> refreshQuarter());
    refreshQuarter();
  }
  function refreshQuarter(){
    const city = byId("cCity").value;
    const qSel = byId("cQuarter");
    qSel.innerHTML = "";
    const quarters = SHIPPING[city]?.quarters || {"Autre":1000};
    Object.keys(quarters).forEach(q=>{
      const opt = document.createElement("option");
      opt.value = q; opt.textContent = q;
      qSel.appendChild(opt);
    });
    renderCart();
  }
  function computeShipping(city, quarter){
    const conf = SHIPPING[city] || SHIPPING["Autre"];
    const base = conf.base || 0;
    const add = (conf.quarters?.[quarter] ?? conf.quarters?.["Autre"] ?? 0);
    return base + add;
  }

  function loadOrders(){ try{ return JSON.parse(localStorage.getItem(LS.ORDERS) || "[]"); }catch(e){ return []; } }
  function saveOrders(list){ localStorage.setItem(LS.ORDERS, JSON.stringify(list)); }

  function goTab(tab){
    ["tabShop","tabReseller","tabTrack","tabAdmin"].forEach(id=>byId(id).classList.remove("active"));
    byId("tab"+tab.charAt(0).toUpperCase()+tab.slice(1)).classList.add("active");
    ["pageShop","pageReseller","pageTrack","pageAdmin"].forEach(id=>byId(id).classList.remove("active"));
    byId("page"+tab.charAt(0).toUpperCase()+tab.slice(1)).classList.add("active");
    window.scrollTo({top:0, behavior:"smooth"});
    if(tab==="admin" && role==="admin") renderDashboard();
  }

  function initFilters(){
    const brands = Array.from(new Set(products.map(p=>p.brand))).sort();
    const sel = byId("brandFilter");
    brands.forEach(b=>{
      const opt = document.createElement("option");
      opt.value = b; opt.textContent = "Marque : " + b;
      sel.appendChild(opt);
    });
  }
  function filteredProducts(){
    return products.filter(p=>{
      const okQ = (p.name+" "+p.id+" "+p.brand).toLowerCase().includes(query.toLowerCase());
      const okB = (brand==="ALL" ? true : p.brand===brand);
      const okC = (cat==="ALL" ? true : p.cat===cat);
      return okQ && okB && okC;
    });
  }

  async function reorderResellerOrder(orderNo){
  try{
    const res = await fetch(`/api/reseller/me/orders/${encodeURIComponent(orderNo)}/`);
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch(_) {}

    if(!res.ok || !data.ok){
      alert(data.error || text.slice(0, 200) || "Impossible de recharger cette commande.");
      return;
    }

    const o = data.order;
    const items = Array.isArray(o.items) ? o.items : [];

    if(!items.length){
      alert("Cette commande ne contient aucun article.");
      return;
    }

    // Recharge brut
    const reloaded = items.map(it => ({
      sku: it.sku,
      name: it.name,
      size: normalizeVariantValue(it.size),
      qty: Number(it.qty),
      unit_price: Number(it.unit_price || 0),
      source: "reorder"
    }));

    // Validation immédiate
    cart = validateReorderCart(reloaded);

    mode = "reseller";

    closeResellerOrderDetail();

    renderCart();
    renderProducts();
    renderProductDetail();
    renderPacks();

    goTab("shop");

    const hasIssues = cart.some(i => i.reorder_issue);
    if(hasIssues){
      alert("Commande rechargée, mais certains articles nécessitent une correction avant paiement.");
    }else{
      alert("Les articles de cette commande ont été remis dans votre panier.");
    }
  }catch(e){
    alert("Erreur réseau / serveur.");
  }
}

  function renderProducts(){
  const grid = byId("productGrid");
  if(!grid) return;

  grid.innerHTML = "";
  const list = filteredProducts();
  byId("resultCount").textContent = `${list.length} produit(s)`;

  list.forEach(p=>{
    const totalSt = totalStockOfSku(p.id);
    const statusClass = totalSt<=0 ? "bad" : (totalSt<=6 ? "warn" : "ok");

    // ✅ image en background (ne bloque pas les clics)
    const bg = p.image_url ? `background-image:url('${p.image_url}');` : "";

    const card = document.createElement("div");
    card.className = "card";
    card.innerHTML = `
      <div class="img">
        ${p.image_url ? `<img src="${p.image_url}" alt="${p.name}" style="width:100%;height:100%;object-fit:cover;border-radius:14px">` : ""}
        <div class="tag">${p.tag}</div>
        <div class="statusPill ${statusClass}">${totalSt} stock total</div>
      </div>


      <div class="content">
        <div class="title">
          <div>
            <h4>${p.name}</h4>
            <div class="code">
              ${p.brand} • ${p.id} • ${p.cat}<br/>
              MOQ revendeur: ${p.moq}
            </div>
          </div>
          <div class="price">
            <div class="now">${money(priceOf(p))}</div>
            <div class="hint">${mode==="reseller" ? "prix revendeur" : "prix public"}</div>
          </div>
        </div>

        <div class="footer">
          <button class="btn small primary" data-detail="${p.id}">📄 Voir fiche</button>
          <button class="btn small" data-quick="${p.id}">➕ Ajouter</button>
        </div>
      </div>
    `;

    grid.appendChild(card);
  });

  // ✅ events (important)
  grid.querySelectorAll("[data-detail]").forEach(b=>{
    b.addEventListener("click", ()=> showProductDetail(b.getAttribute("data-detail")));
  });
  grid.querySelectorAll("[data-quick]").forEach(b=>{
    b.addEventListener("click", ()=> quickAdd(b.getAttribute("data-quick")));
  });
}

function switchResellerTab(tabName){
  const map = {
    overview: "resellerTabOverview",
    orders: "resellerTabOrders",
    catalog: "resellerTabCatalog"
  };

  Object.entries(map).forEach(([key, id])=>{
    const el = byId(id);
    if(el) el.style.display = (key === tabName ? "block" : "none");
  });

  document.querySelectorAll(".resellerTabBtn").forEach(btn=>{
    btn.classList.toggle("active", btn.getAttribute("data-reseller-tab") === tabName);
  });
}

function renderResellerOrdersTable(list){
  const tbody = byId("resellerOrdersTable");
  if(!tbody) return;

  const rows = Array.isArray(list) ? list : [];
  const statusFilter = (byId("resellerStatusFilter")?.value || "ALL").toLowerCase();
  const paymentFilter = (byId("resellerPaymentFilter")?.value || "ALL").toLowerCase();
  const searchTerm = (byId("resellerOrderSearch")?.value || "").trim().toLowerCase();
  const sortFilter = (byId("resellerSortFilter")?.value || "recent").toLowerCase();

  const filtered = rows.filter(o=>{
    const st = (o.status || "").toLowerCase();
    const pay = (o.payment_status || "").toLowerCase();
    const haystack = `${o.orderNo || ""} ${o.city || ""} ${o.quarter || ""}`.toLowerCase();

    const okStatus = statusFilter === "all" ? true : st === statusFilter;
    const okPayment = paymentFilter === "all" ? true : pay === paymentFilter;
    const okSearch = !searchTerm ? true : haystack.includes(searchTerm);

    return okStatus && okPayment && okSearch;
  });

  const rankStatus = (s) => {
    const v = (s || "").toLowerCase();
    if (v === "received") return 1;
    if (v === "preparing") return 2;
    if (v === "shipped") return 3;
    if (v === "delivered") return 4;
    if (v === "cancelled") return 5;
    if (v === "failed") return 6;
    return 99;
  };

  const rankPayment = (s) => {
    const v = (s || "").toLowerCase();
    if (v === "unpaid") return 1;
    if (v === "pending") return 2;
    if (v === "failed") return 3;
    if (v === "paid") return 4;
    return 99;
  };

  filtered.sort((a, b) => {
    const aDate = a.createdAt ? new Date(a.createdAt).getTime() : 0;
    const bDate = b.createdAt ? new Date(b.createdAt).getTime() : 0;
    const aTotal = Number(a.total || 0);
    const bTotal = Number(b.total || 0);

    if (sortFilter === "oldest") return aDate - bDate;
    if (sortFilter === "highest") return bTotal - aTotal;
    if (sortFilter === "active") {
      const byStatus = rankStatus(a.status) - rankStatus(b.status);
      if (byStatus !== 0) return byStatus;
      return bDate - aDate;
    }
    if (sortFilter === "payment_due") {
      const byPayment = rankPayment(a.payment_status) - rankPayment(b.payment_status);
      if (byPayment !== 0) return byPayment;
      return bDate - aDate;
    }

    return bDate - aDate;
  });

  tbody.innerHTML = filtered.map(o=>{
  const rowClass = getResellerPaymentRowClass(o.payment_status);
  const paymentFlag = getResellerPaymentFlag(o.payment_status);

  return `
    <tr class="${rowClass}">
      <td><b>${o.orderNo || ""}</b></td>
      <td>${o.createdAt ? new Date(o.createdAt).toLocaleString() : ""}</td>
      <td>${o.city || ""} / ${o.quarter || ""}</td>
      <td style="text-align:right"><b>${money(o.total || 0)}</b></td>
      <td>
        ${paymentBadge(o.payment_status)}
        ${paymentFlag}
      </td>
      <td><span class="mini">${o.payment_ref || "—"}</span></td>
      <td>${statusBadge(o.status)}</td>
      <td>
        <div class="mini" style="max-width:220px;">
          ${formatLastActivity(o.last_activity)}
        </div>
        ${
          o.last_activity?.note
            ? `<div class="mini muted" style="margin-top:3px; max-width:220px;">${o.last_activity.note}</div>`
            : ``
        }
      </td>
      <td>
        <button class="btn small ghost" data-action="viewResellerOrder" data-order="${o.orderNo}">Voir</button>
      </td>
    </tr>
  `;
}).join("");

  if(filtered.length === 0){
    tbody.innerHTML = `<tr><td colspan="9" class="muted">Aucune commande trouvée.</td></tr>`;
  }
}

async function renderResellerOrders(){
  try{
    const res = await fetch("/api/reseller/me/orders/");
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch(_) {}

    if(!res.ok || !data.ok){
      throw new Error(data.error || text.slice(0, 200) || "Erreur commandes revendeur");
    }

    resellerOrdersCache = data.results || [];
    renderResellerOrdersTable(resellerOrdersCache);
  }catch(e){
    if(byId("resellerKpiGrid")){
      byId("resellerKpiGrid").innerHTML = "";
    }
    if(byId("resellerOrdersTable")){
      byId("resellerOrdersTable").innerHTML = `<tr><td colspan="9" class="muted">Erreur: ${e.message}</td></tr>`;
    }
  }
}

async function openResellerOrderDetail(orderNo){
  const modal = byId("resellerOrderDetailModal");
  const body = byId("resellerOrderDetailBody");
  if(!modal || !body) return;

  modal.style.display = "flex";
  body.innerHTML = `<div class="muted">Chargement...</div>`;

  try{
    const [detailRes, timelineRes] = await Promise.all([
      fetch(`/api/reseller/me/orders/${encodeURIComponent(orderNo)}/`),
      fetch(`/api/reseller/me/orders/${encodeURIComponent(orderNo)}/timeline/`)
    ]);

    const detailText = await detailRes.text();
    const timelineText = await timelineRes.text();

    let detailData = {};
    let timelineData = {};

    try { detailData = detailText ? JSON.parse(detailText) : {}; } catch(_) {}
    try { timelineData = timelineText ? JSON.parse(timelineText) : {}; } catch(_) {}

    if(!detailRes.ok || !detailData.ok){
      throw new Error(detailData.error || detailText.slice(0, 200) || "Erreur détail commande");
    }

    const o = detailData.order;
    const logs = (timelineData.ok && Array.isArray(timelineData.logs)) ? timelineData.logs : [];
    const paidAtText = o.paid_at ? new Date(o.paid_at).toLocaleString() : "—";

    body.innerHTML = `
      <div class="orderDetailCard">
        <div class="orderDetailHeader">
          <div class="orderDetailMeta">
            <div style="font-weight:900; font-size:18px;">${o.orderNo}</div>
            <div class="muted">${o.createdAt ? new Date(o.createdAt).toLocaleString() : ""}</div>
            <div>${statusBadge(o.status)}</div>
            <div>${paymentBadge(o.payment_status)}</div>
          </div>
          <div class="orderDetailAmount">
            <div class="bigTotal">${money(o.total||0)}</div>
            <div class="muted">${o.mode || ""} • ${o.pay_method || ""}</div>
            <div style="margin-top:10px;">
              <button class="btn small primary" onclick="reorderResellerOrder('${o.orderNo}')">
                Commander à nouveau
              </button>
            </div>
          </div>
        </div>
      </div>

      <div class="orderDetailCard">
        <div class="orderDetailSectionTitle">Paiement</div>
        <div class="orderDetailGrid">
          <div>
            <div class="orderDetailLabel">Référence</div>
            <div class="orderDetailValue">${o.payment_ref || "—"}</div>
          </div>
          <div>
            <div class="orderDetailLabel">Date paiement</div>
            <div class="orderDetailValue">${paidAtText}</div>
          </div>
        </div>
      </div>

      <div class="orderDetailCard">
        <div class="orderDetailSectionTitle">Livraison</div>
        <div class="orderDetailGrid">
          <div>
            <div class="orderDetailLabel">Nom</div>
            <div class="orderDetailValue">${o.name || ""}</div>
          </div>
          <div>
            <div class="orderDetailLabel">Téléphone</div>
            <div class="orderDetailValue">${o.phone || ""}</div>
          </div>
          <div>
            <div class="orderDetailLabel">Zone</div>
            <div class="orderDetailValue">${o.city || ""} / ${o.quarter || ""}</div>
          </div>
          <div>
            <div class="orderDetailLabel">Adresse</div>
            <div class="orderDetailValue">${o.address || ""}</div>
          </div>
        </div>
      </div>

      <div class="orderDetailCard">
        <div class="orderDetailSectionTitle">Articles</div>
        ${(o.items||[]).map(it=>`
          <div class="orderItemRow">
            <div>
              <div class="orderItemName">${it.name}</div>
              <div class="orderItemMeta">${it.sku} • Option ${it.size} • x${it.qty} • ${money(it.unit_price)}</div>
            </div>
            <div class="orderItemTotal">${money(it.line_total)}</div>
          </div>
        `).join("")}

        <div style="margin-top:12px; display:flex; flex-direction:column; gap:6px;">
          <div class="row" style="justify-content:space-between;"><div class="muted">Sous-total</div><div>${money(o.subtotal||0)}</div></div>
          <div class="row" style="justify-content:space-between;"><div class="muted">Livraison</div><div>${money(o.shipping||0)}</div></div>
          <div class="row" style="justify-content:space-between;"><div style="font-weight:900">Total</div><div style="font-weight:900">${money(o.total||0)}</div></div>
        </div>
      </div>

      <div class="orderDetailCard">
        <div class="orderDetailSectionTitle">Historique</div>
        ${
          logs.length ? `
            <div class="timelineList">
              ${logs.map(l=>`
                <div class="timelineItem">
                  <div class="timelineTop">
                    <div>
                      <div class="timelineTitle">${formatStatusLabel(l.old)} → ${formatStatusLabel(l.new)}</div>
                      <div class="timelineMeta">${l.by ? `par ${l.by}` : "par système"}</div>
                    </div>
                    <div class="timelineDate">${l.at ? new Date(l.at).toLocaleString() : ""}</div>
                  </div>

                  ${l.note ? `
                    <div class="timelineNote">
                      <div class="timelineNoteTitle">Note</div>
                      <div class="muted">${l.note}</div>
                    </div>
                  ` : ""}
                </div>
              `).join("")}
            </div>
          ` : `<div class="muted">Aucun historique.</div>`
        }
      </div>
    `;
  }catch(e){
    body.innerHTML = `<div class="muted">Erreur: ${e.message}</div>`;
  }
}

function closeResellerOrderDetail(){
  if(byId("resellerOrderDetailModal")){
    byId("resellerOrderDetailModal").style.display = "none";
  }
}

function renderResellerSummary(list){
  const box = byId("resellerKpiGrid");
  if(!box) return;

  const rows = Array.isArray(list) ? list : [];

  const totalOrders = rows.length;
  const activeOrders = rows.filter(o => ["received", "preparing", "shipped"].includes((o.status || "").toLowerCase())).length;
  const deliveredOrders = rows.filter(o => (o.status || "").toLowerCase() === "delivered").length;
  const pendingPayments = rows.filter(o => ["unpaid", "pending"].includes((o.payment_status || "").toLowerCase())).length;

  box.innerHTML = `
    <div class="kpi">
      <div class="muted">Total commandes</div>
      <div class="big">${totalOrders}</div>
    </div>
    <div class="kpi">
      <div class="muted">En cours</div>
      <div class="big">${activeOrders}</div>
    </div>
    <div class="kpi">
      <div class="muted">Livrées</div>
      <div class="big">${deliveredOrders}</div>
    </div>
    <div class="kpi">
      <div class="muted">Paiements en attente</div>
      <div class="big">${pendingPayments}</div>
    </div>
  `;
}

  function showProductDetail(sku){ selectedProductId = sku; renderProductDetail(); }

  function renderProductDetail(){
    const mount = byId("productDetailMount");
    if(!selectedProductId){
      mount.className = "muted";
      mount.textContent = "Aucune fiche selectionnee.";
      return;
    }
    const p = getProduct(selectedProductId);
    if(!p){
      mount.className = "muted";
      mount.innerHTML = `Produit introuvable pour SKU: <b>${selectedProductId}</b>`;
      return;
    }

    const variantLabel = getVariantLabel(p);

    const sizesHtml = p.sizes.map(s=>{
      const st = stockOf(p.id, s);
      const cls = st<=0 ? "bad" : (st<=2 ? "warn" : "ok");
      return `<span class="statusPill ${cls}">${formatVariantStockLabel(p, s)}: ${st}</span>`;
    }).join(" ");

    mount.className = "";
    mount.innerHTML = `
      <div class="productPage">
        <div class="bigImg">
          ${p.image_url ? `<img src="${p.image_url}" alt="${p.name}" style="width:100%;height:100%;object-fit:cover;border-radius:16px">` : ""}
          <div class="tag">${p.brand}</div><div class="tag">${p.id}</div>
        </div>

        <div class="box">
          <div class="section-title" style="margin:0 0 8px 0">
            <h3 style="margin:0;font-size:14px">${p.name}</h3>
            <span class="mini">${p.cat} • ${p.tag}</span>
          </div>
          <div class="badges">
            <span class="badge">${mode==="reseller" ? "Tarif revendeur" : "Tarif detail"}</span>
            <span class="badge">MOQ: ${p.moq}</span>
            <span class="badge">Stock par ${variantLabel.toLowerCase()}</span>
          </div>
          <div class="muted">${p.desc}</div>

          <div class="section-title" style="margin-top:12px">
            <h3 style="margin:0;font-size:13px">${variantLabel}s / variantes</h3>
            <span class="mini">stock live</span>
          </div>
          <div class="mini" style="line-height:2">${sizesHtml}</div>

          <div style="margin-top:12px">
            <div class="row"><span>Prix</span><strong>${money(priceOf(p))}</strong></div>
          </div>

          <div class="checkout-grid" style="margin-top:10px">
            <div>
              <label>${variantLabel}</label>
              <select id="pdSize">${p.sizes.map(s=>`<option value="${s}">${formatVariantValue(p, s)}</option>`).join("")}</select>
            </div>
            <div>
              <label>Quantite</label>
              <input class="text" id="pdQty" type="number" min="1" value="${mode==="reseller" ? p.moq : 1}" />
              <div class="hintline">${mode==="reseller" ? `MOQ revendeur : ${p.moq}` : "Pas de MOQ en detail."}</div>
            </div>
          </div>

          <div class="hero-row" style="margin-top:12px">
            <button class="btn primary" id="pdAddBtn">🛒 Ajouter au panier</button>
          </div>
        </div>
      </div>
    `;

    byId("pdAddBtn")?.addEventListener("click", ()=>{
      const size = normalizeVariantValue(byId("pdSize").value);
      const qty = parseInt(byId("pdQty").value, 10) || 1;
      if(mode==="reseller" && qty < p.moq){ alert(`MOQ revendeur = ${p.moq}`); return; }
      const v = validateStock(p.id, size, qty);
      if(!v.ok){ alert(v.msg); return; }
      addToCart(p.id, size, qty, "PRODUCT");
    });
  }

  function quickAdd(sku){
  const p = getProduct(sku);
  if(!p || !Array.isArray(p.sizes) || !p.sizes.length){
    alert("Ce produit n'a aucune option disponible.");
    return;
  }

  const size = normalizeVariantValue(p.sizes[Math.floor(p.sizes.length / 2)]);
  const qty = (mode === "reseller" ? p.moq : 1);

  const v = validateStock(sku, size, qty);
  if(!v.ok){ alert(v.msg); return; }

  addToCart(sku, size, qty, "QUICK");
}

  function addToCart(sku, size, qty, source){
  const option = normalizeVariantValue(size);
  const key = `${sku}__${option}__${source}`;
  const existing = cart.find(x => `${x.sku}__${x.size}__${x.source}` === key);

  if(existing) existing.qty += qty;
  else cart.push({sku, size: option, qty, source});

  renderCart();
}
  function updateQty(idx, delta){
    const item = cart[idx];
    const next = Math.max(1, item.qty + delta);
    const addDelta = next - item.qty;
    if(addDelta > 0){
      const v = validateStock(item.sku, item.size, addDelta);
      if(!v.ok){ alert(v.msg); return; }
    }
    item.qty = next;
    renderCart();
  }
  function removeItem(idx){ cart.splice(idx,1); renderCart(); }
  function clearCart(){ cart=[]; renderCart(); }

  function computeTotals(){
    let subtotal = 0;
    cart.forEach(i=>{
      const p = getProduct(i.sku);
      subtotal += priceOf(p) * i.qty;
    });
    const city = byId("cCity")?.value || "Douala";
    const quarter = byId("cQuarter")?.value || "Autre";
    const shipping = cart.length ? computeShipping(city, quarter) : 0;
    return {subtotal, shipping, total: subtotal+shipping};
  }

  function openCheckoutSuccessModal(orderNo, total){
  if(byId("successOrderNo")) byId("successOrderNo").textContent = orderNo || "—";
  if(byId("successOrderTotal")) byId("successOrderTotal").textContent = money(total || 0);
  if(byId("checkoutSuccessModal")) byId("checkoutSuccessModal").style.display = "flex";
  }

  function closeCheckoutSuccessModal(){
    if(byId("checkoutSuccessModal")) byId("checkoutSuccessModal").style.display = "none";
    }

async function loadResellerStats(){
  try{
    const res = await fetch("/api/reseller/me/stats/");
    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch(_) {}

    if(!res.ok || !data.ok){
      throw new Error(data.error || text.slice(0, 200) || "Erreur stats revendeur");
    }

    const s = data.stats || {};
    const box = byId("resellerKpiGrid");
    if(!box) return;

    box.innerHTML = `
      <div class="kpi">
        <div class="muted">Total commandes</div>
        <div class="big">${s.total_orders || 0}</div>
      </div>
      <div class="kpi">
        <div class="muted">Montant total</div>
        <div class="big">${money(s.total_amount || 0)}</div>
      </div>
      <div class="kpi">
        <div class="muted">Livrées</div>
        <div class="big">${s.delivered_orders || 0}</div>
      </div>
      <div class="kpi">
        <div class="muted">Panier moyen</div>
        <div class="big">${money(s.avg_order || 0)}</div>
      </div>
      <div class="kpi">
        <div class="muted">En cours</div>
        <div class="big">${s.active_orders || 0}</div>
      </div>
      <div class="kpi">
        <div class="muted">Paiements en attente</div>
        <div class="big">${s.pending_payments || 0}</div>
      </div>
    `;
  }catch(e){
    const box = byId("resellerKpiGrid");
    if(box){
      box.innerHTML = `<div class="muted">Erreur stats: ${e.message}</div>`;
    }
  }
}

  function renderCart(){
  const wrap = byId("cartItems");
  wrap.innerHTML = "";

  cart.forEach((i, idx)=>{
    const p = getProduct(i.sku);
    const div = document.createElement("div");
    div.className = "cart-item";
    div.innerHTML = `
      <div class="left">
        <div class="thumb"></div>
        <div>
          <p class="ci-title">${p ? p.name : (i.name || i.sku)}</p>
          <p class="ci-sub">
            ${i.sku} • ${getVariantLabel(p)} ${formatVariantValue(p, i.size)} • ${p ? money(priceOf(p)) : money(i.unit_price || 0)} •
            Stock ${formatVariantStockLabel(p, i.size)}: ${stockOf(i.sku,i.size)} • Source: ${i.source}
          </p>

          ${i.reorder_issue ? `
            <div class="mini" style="margin-top:6px; color:#b42318; font-weight:800;">
              ⚠ ${i.reorder_issue}
            </div>
          ` : ``}

          <div class="qty">
            <button aria-label="moins">−</button>
            <span>${i.qty}</span>
            <button aria-label="plus">+</button>
            <button class="btn small danger" style="margin-left:6px" aria-label="supprimer">Suppr.</button>
          </div>
        </div>
      </div>
      <div style="font-size:12px;font-weight:900">
        ${p ? money(priceOf(p) * i.qty) : money((i.unit_price || 0) * i.qty)}
      </div>
    `;

    const btns = div.querySelectorAll("button");
    btns[0].addEventListener("click", ()=>updateQty(idx,-1));
    btns[1].addEventListener("click", ()=>updateQty(idx,+1));
    btns[2].addEventListener("click", ()=>removeItem(idx));
    wrap.appendChild(div);
  });

  const {subtotal, shipping, total} = computeTotals();
  byId("subtotal").textContent = money(subtotal);
  byId("shipping").textContent = money(shipping);
  byId("total").textContent = money(total);

  if(byId("cCity") && byId("cQuarter")){
    const city = byId("cCity").value;
    const quarter = byId("cQuarter").value;
    byId("shipHint").textContent = cart.length ? `Livraison pour ${city}: base ${money(SHIPPING[city].base)} + quartier ${quarter}` : "";
    byId("quarterHint").textContent = cart.length ? `Total livraison: ${money(shipping)}` : "";
  }

  const hasIssues = cart.some(i => i.reorder_issue);
  if(byId("payNowBtn")){
    const btn = byId("payNowBtn");
    btn.disabled = hasIssues;
    btn.title = hasIssues
      ? "Corrige les articles signalés avant de passer au paiement."
      : "";

    btn.style.opacity = hasIssues ? "0.55" : "1";
    btn.style.cursor = hasIssues ? "not-allowed" : "pointer";
    btn.style.pointerEvents = hasIssues ? "none" : "auto";
  }

  byId("successBox").style.display = "none";
  renderProducts();
  renderProductDetail();
}

  function openCheckout(){
    if(cart.length===0){ alert("Panier vide."); return; }
    byId("checkoutSection").style.display = "block";
    byId("checkoutSection").scrollIntoView({behavior:"smooth", block:"start"});
    renderCart();
  }

async function payNow(){
  if(cart.length===0) return;

  const InvalidReorderItems = cart.find(i => i.reorder_issue);
  if(InvalidReorderItems){
    alert("Corrige les articles signalés dans le panier avant de passer au paiement.");
    return;
  }

  if(mode==="reseller"){
    const agg = {};
    cart.forEach(i=> agg[i.sku] = (agg[i.sku]||0) + i.qty);
    for(const sku in agg){
      const p = getProduct(sku);
      if(agg[sku] < p.moq){ alert(`MOQ non atteint pour ${sku}: minimum ${p.moq}`); return; }
    }
  }

  for(const i of cart){
    const v = validateStock(i.sku, i.size, i.qty);
    if(!v.ok){ alert(v.msg); return; }
  }

  const name = (byId("cName").value||"").trim();
  const phone = (byId("cPhone").value||"").trim();
  const city = byId("cCity").value;
  const quarter = byId("cQuarter").value;
  const addr = (byId("cAddr").value||"").trim();
  if(!name || !phone || !addr){ alert("Remplis Nom, Telephone, Adresse."); return; }

  const {subtotal, shipping, total} = computeTotals();

  const payload = {
    role, mode,
    customer: { name, phone, city, quarter, address: addr },
    pay_method: byId("cPay").value,
    shipping_fee: shipping,
    items: cart.map(i => ({
      sku: i.sku,
      size: i.size,
      qty: i.qty,
      source: i.source
    }))
  };

  const btn = byId("payNowBtn");
  const prevText = btn ? btn.textContent : "";
  if(btn){ btn.disabled = true; btn.textContent = "Traitement..."; }

  try{
    const csrf = getCookie("csrftoken");
    console.log("CHECKOUT PAYLOAD", JSON.stringify(payload, null, 2));
    const res = await fetch("/api/checkout/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf,
        "X-Requested-With": "XMLHttpRequest"
      },
      credentials: "same-origin",
      body: JSON.stringify(payload)
    });

    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch(_) {}

    if(!res.ok || !data.ok){
      alert(data.error || text.slice(0,200) || "Erreur checkout.");
      return;
    }

    const orderNo = data.orderNo;
    const finalTotal = total;

    if(byId("orderNo")) byId("orderNo").textContent = orderNo;
    if(byId("successBox")) byId("successBox").style.display = "block";

    openCheckoutSuccessModal(orderNo, finalTotal);

    cart = [];
    renderCart();

    await loadProductsFromApi();
    renderProducts();
    renderProductDetail();
    renderPacks();
    if(role==="admin") renderDashboard();

  }catch(e){
    alert("Erreur réseau / serveur.");
  }finally{
    if(btn){ btn.disabled = false; btn.textContent = prevText || "💳 Payer maintenant"; }
  }
}

 async function copyOrderNo(){
  const el = document.getElementById("orderNo");
  const no = (el ? el.textContent : "").trim();

  if(!no){
    alert("Aucun numéro.");
    return;
  }

  try{
    await navigator.clipboard.writeText(no);
    alert("Numéro copié ✅");
  }catch(e){
    // fallback si clipboard bloqué
    window.prompt("Copie le numéro:", no);
  }
}


async function renderTrackingFromApi(orderNo){
  const box = byId("trackResult");
  box.innerHTML = `<div class="note">Recherche...</div>`;

  const res = await fetch(`/api/track/${encodeURIComponent(orderNo)}/`);
  const data = await res.json();

  if(!res.ok || !data.ok){
    box.innerHTML = `<div class="note">❌ ${data.error || "Commande introuvable."}</div>`;
    return;
  }

  const o = data.order;

  // fallback si fmtMoney n’existe pas
  const money = (typeof fmtMoney === "function")
    ? fmtMoney
    : (n)=> `${Number(n||0).toLocaleString()} FCFA`;

  box.innerHTML = `
    <div class="card">
      <div class="row" style="justify-content:space-between; gap:12px;">
        <div>
          <div style="font-weight:800">${o.orderNo}</div>
          <div class="muted">${new Date(o.createdAt).toLocaleString()}</div>
        </div>
        <div class="pill">${o.status}</div>
      </div>

      <div class="hr"></div>

      <div class="muted">${o.customer.name} • ${o.customer.phone}</div>
      <div class="muted">${o.customer.city} / ${o.customer.quarter} • ${o.customer.address}</div>

      <div class="hr"></div>

      <div style="display:flex; flex-direction:column; gap:8px;">
        ${(o.items||[]).map(it=>`
          <div class="row" style="justify-content:space-between;">
            <div>
              <div style="font-weight:700">${it.name}</div>
              <div class="muted">${it.sku} • Option ${it.size} • x${it.qty}</div>
            </div>
            <div style="font-weight:800">${money(it.line_total)}</div>
          </div>
        `).join("")}
      </div>

      <div class="hr"></div>

      <div class="row" style="justify-content:space-between;"><div class="muted">Sous-total</div><div>${money(o.subtotal)}</div></div>
      <div class="row" style="justify-content:space-between;"><div class="muted">Livraison</div><div>${money(o.shipping)}</div></div>
      <div class="row" style="justify-content:space-between;"><div style="font-weight:900">Total</div><div style="font-weight:900">${money(o.total)}</div></div>
    </div>
  `;
}


  function getCurrentVariantStock(sku, size){
  return stockOf(sku, normalizeVariantValue(size));
}

function validateReorderCart(cartItems){
  const results = [];
  const agg = {};

  for(const item of cartItems){
    const sku = item.sku;
    const size = normalizeVariantValue(item.size);
    const qty = Number(item.qty || 0);
    const product = getProduct(sku);

    let issue = "";

    if(!product){
      issue = "Produit introuvable";
    } else {
      const check = validateStock(sku, size, qty);
      if(!check.ok){
        issue = check.msg || `Option ${size} indisponible`;
      }
    }

    agg[sku] = (agg[sku] || 0) + qty;

    results.push({
      ...item,
      reorder_issue: issue
    });
  }

  // MOQ revendeur par SKU
  for(let i = 0; i < results.length; i++){
    const item = results[i];
    const product = getProduct(item.sku);
    if(!product) continue;

    const moq = Number(product.moq || product.reseller_moq || 1);
    const totalSkuQty = Number(agg[item.sku] || 0);

    if(totalSkuQty < moq){
      const base = results[i].reorder_issue ? `${results[i].reorder_issue} • ` : "";
      results[i].reorder_issue = `${base}MOQ non atteint (${totalSkuQty}/${moq})`;
    }
  }

  return results;
}

  function resetDemo(){
    localStorage.removeItem(LS.ORDERS);
    localStorage.removeItem(LS.STOCK);
    localStorage.removeItem(LS.ROLE);
    initStockIfMissing();
    role = getRole();
    mode = (role==="reseller" ? "reseller" : "retail");
    cart = []; selectedProductId = null;
    syncRoleUI(); renderAll();
    alert("Reset OK.");
  }



  function renderPacks(){
    const grid = byId("packsGrid");
    if(!grid) return;
    grid.innerHTML = "";
    if(!packs.length){
      grid.innerHTML = `<div class="muted">Aucun pack disponible pour le moment.</div>`;
      return;
    }
    packs.forEach(pk=>{
      const p = getProduct(pk.sku);
      const sizes = Object.keys(pk.defaultDist);

      const distInputs = sizes.map(s=>{
        return `
          <div class="distCell">
            <strong>${pk.variant_label} ${s}</strong>
            <div class="mini">Stock: ${stockOf(pk.sku, s)}</div>
            <input class="text" type="number" min="0" value="${pk.defaultDist[s]}" data-pack="${pk.id}" data-size="${s}" />
          </div>
        `;
      }).join("");

      const totalDefault = sizes.reduce((a,s)=>a + (pk.defaultDist[s]||0), 0);

      const card = document.createElement("div");
      card.className = "packCard";
      card.innerHTML = `
        <div class="section-title" style="margin:0 0 6px 0">
          <h3 style="margin:0;font-size:14px">${pk.title}</h3>
          <span class="statusPill ok">${money(pk.packPrice)}</span>
        </div>
        <div class="mini">${p.name} • SKU: ${pk.sku} • Total defaut: <strong>${totalDefault}</strong></div>
        <div class="distGrid">${distInputs}</div>
        <div class="hero-row" style="margin-top:12px">
          <button class="btn primary" data-addpack="${pk.id}">➕ Ajouter ce pack</button>
          <button class="btn" data-resetpack="${pk.id}">↩️ Reset repartition</button>
        </div>
        <div class="hintline">Permission : seulement revendeur. MOQ vérifié avant ajout. Répartition par ${pk.variant_label.toLowerCase()}.</div>
      `;
      grid.appendChild(card);
    });

    grid.querySelectorAll("[data-addpack]").forEach(b=>b.addEventListener("click", ()=> addPackToCart(b.getAttribute("data-addpack"))));
    grid.querySelectorAll("[data-resetpack]").forEach(b=>b.addEventListener("click", ()=> resetPackDist(b.getAttribute("data-resetpack"))));
  }

  function resetPackDist(packId){
    const pk = packs.find(x=>x.id===packId);
    document.querySelectorAll(`input[data-pack="${packId}"]`).forEach(inp=>{
      const size = normalizeVariantValue(inp.getAttribute("data-size"));
      inp.value = pk.defaultDist[size] ?? 0;
    });
  }

  function readPackDist(packId){
    const inputs = document.querySelectorAll(`input[data-pack="${packId}"]`);
    const dist = {};
    inputs.forEach(inp=>{
      const size = normalizeVariantValue(inp.getAttribute("data-size"));
      dist[size] = Math.max(0, parseInt(inp.value,10) || 0);
    });
    const total = Object.values(dist).reduce((a,b)=>a+b,0);
    const pk = packs.find(x=>x.id===packId);
    return {dist, total, sku: pk.sku};
  }

  function addPackToCart(packId){
    const pk = packs.find(x=>x.id===packId);
    const {dist, total, sku} = readPackDist(packId);
    if(total<=0){ alert("Distribution vide."); return; }
    for(const sStr in dist){
      const size = normalizeVariantValue(sStr);
      const qty = dist[size];
      if(qty <= 0) continue;

      const v = validateStock(sku, size, qty);
      if(!v.ok){ alert(v.msg); return; }
    }
    const p = getProduct(sku);
    if(total < p.moq){ alert(`MOQ non atteint pour ${sku}: minimum ${p.moq}`); return; }
    for(const sStr in dist){
      const size = normalizeVariantValue(sStr);
      const qty = dist[size];
      if(qty <= 0) continue;
      addToCart(sku, size, qty, "PACK:"+packId);
    }
    alert("Pack ajoute ✅");
    goTab("shop");
  }

  function withinRange(dateIso, days){
    if(days==="ALL") return true;
    const d = new Date(dateIso).getTime();
    const now = Date.now();
    const ms = parseInt(days,10)*24*60*60*1000;
    return (now - d) <= ms;
  }
  
 async function renderInventory(){
  const res = await fetch("/api/admin/inventory/");

  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_) {
    throw new Error(text?.slice(0, 120) || "Inventory API invalid response");
  }

  if(!res.ok || !data.ok){
    throw new Error(data.error || "Inventory API error");
  }

  const tbody = byId("stockTable");
  if(!tbody) return;

  tbody.innerHTML = (data.results || []).map(p=>{
    const sizes = p.sizes || {};
    const sizeChips = Object.keys(sizes).sort((a,b)=>String(a).localeCompare(String(b), "fr", {numeric:true})).map(s=>{
      const qty = sizes[s];
      const low = qty <= 10;
      return `<span class="pill ${low ? "dangerPill" : ""}">${s}: ${qty}</span>`;
    }).join(" ");

    const actions = Object.keys(sizes).sort((a,b)=>String(a).localeCompare(String(b), "fr", {numeric:true})).map(s=>`
      <div style="display:flex; gap:6px; align-items:center; margin:4px 0;">
        <span class="muted" style="min-width:48px">${s}</span>
        <button class="btn small" data-action="stockAdj" data-sku="${p.sku}" data-size="${s}" data-delta="1">+1</button>
        <button class="btn small ghost" data-action="stockAdj" data-sku="${p.sku}" data-size="${s}" data-delta="-1">-1</button>
      </div>
    `).join("");

    return `
      <tr>
        <td><b>${p.sku}</b></td>
        <td>${p.name}</td>
        <td>${sizeChips || "<span class='muted'>—</span>"}</td>
        <td>${actions || "<span class='muted'>—</span>"}</td>
      </tr>
    `;
  }).join("");
}

async function fetchResellerApps(){
  const status = (byId("raStatusFilter")?.value ?? "pending");
  const url = `/api/admin/reseller/applications/${status ? `?status=${encodeURIComponent(status)}` : ""}`;
  const res = await fetch(url);
  const data = await res.json().catch(()=>({}));
  if(!res.ok || !data.ok) throw new Error(data.error || "Reseller applications API error");
  return data.results || [];
}

function pillClassForStatus(s){
  if(s === "approved") return "ok";
  if(s === "rejected") return "bad";
  return "warn"; // pending
}

async function renderResellerApps(){
  const tbody = byId("resellerAppsTable");
  if(!tbody) return;

  tbody.innerHTML = `<tr><td colspan="8" class="muted">Chargement...</td></tr>`;

  try{
    const list = await fetchResellerApps();
    if(list.length === 0){
      tbody.innerHTML = `<tr><td colspan="8" class="muted">Aucune demande.</td></tr>`;
      return;
    }

    tbody.innerHTML = list.map(a=>{
      const dt = a.created_at ? new Date(a.created_at).toLocaleString() : "";
      const u = a.user?.username || "";
      const st = a.status || "pending";
      const pill = pillClassForStatus(st);

      const actions = (st === "pending")
        ? `
          <button class="btn small primary" data-action="raApprove" data-id="${a.id}">Approuver</button>
          <button class="btn small danger" data-action="raReject" data-id="${a.id}">Refuser</button>
        `
        : `<span class="muted">—</span>`;

      return `
        <tr>
          <td>${dt}</td>
          <td><b>${u}</b></td>
          <td>${a.full_name || ""}</td>
          <td>${a.phone || ""}</td>
          <td>${a.city || ""}</td>
          <td style="text-align:right">${a.monthly_volume ?? 0}</td>
          <td><span class="pill ${pill}">${st}</span></td>
          <td>${actions}</td>
        </tr>
      `;
    }).join("");

  }catch(e){
    console.error(e);
    tbody.innerHTML = `<tr><td colspan="8" class="muted">Erreur: ${e.message}</td></tr>`;
  }
}

async function resellerAppAction(appId, action){
  const csrf = getCookie("csrftoken");

  const url = action === "approve"
    ? `/api/admin/reseller/applications/${encodeURIComponent(appId)}/approve/`
    : `/api/admin/reseller/applications/${encodeURIComponent(appId)}/reject/`;

  const res = await fetch(url, {
    method: "POST",
    headers: {
      "X-CSRFToken": csrf,
      "X-Requested-With": "XMLHttpRequest"
    },
    credentials: "same-origin"
  });

  const text = await res.text();
  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch (_) {}

  if(!res.ok || !data.ok){
    throw new Error(data.error || text.slice(0, 300) || "Action failed");
  }

  return data;
}

function renderOrdersAdminTable(list){
  const tbody = byId("ordersTable");
  if(!tbody) return;

  const rows = Array.isArray(list) ? list : [];

  const paymentFilter = (byId("paymentFilter")?.value || "ALL").toLowerCase();
  const statusFilter = (byId("statusFilter")?.value || "ALL").toLowerCase();
  const searchTerm = (byId("orderSearch")?.value || "").trim().toLowerCase();

  const nextMap = {
    received: "preparing",
    preparing: "shipped",
    shipped: "delivered",
    delivered: null
  };

  const labelMap = {
    received: "Préparer",
    preparing: "Expédier",
    shipped: "Livrer",
    delivered: "Terminé"
  };

  const filtered = rows.filter(o => {
    const pay = (o.payment_status || "").toLowerCase();
    const st = (o.status || "").toLowerCase();
    const haystack = `${o.orderNo || ""} ${o.name || ""} ${o.phone || ""} ${o.city || ""} ${o.quarter || ""}`.toLowerCase();

    const okPayment = (paymentFilter === "all") ? true : pay === paymentFilter;
    const okStatus = (statusFilter === "all") ? true : st === statusFilter;
    const okSearch = !searchTerm ? true : haystack.includes(searchTerm);

    return okPayment && okStatus && okSearch;
  });

  tbody.innerHTML = filtered.map(o=>{
    const st = (o.status || "").toLowerCase();
    const nextStatus = nextMap[st] || "";
    const canStop = (st === "received" || st === "preparing");

    const advanceBtn = nextStatus
      ? `<button class="btn small" data-action="nextStatus" data-order="${o.orderNo}" data-next="${nextStatus}">${labelMap[st] || "Avancer"}</button>`
      : `<button class="btn small ghost" disabled>✅ Terminé</button>`;

    const cancelBtn = canStop
      ? `<button class="btn small danger" data-action="setStatus" data-order="${o.orderNo}" data-status="cancelled">Annuler</button>`
      : "";

    const failBtn = canStop
      ? `<button class="btn small warn" data-action="setStatus" data-order="${o.orderNo}" data-status="failed">Échouer</button>`
      : "";

    const viewBtn = `<button class="btn small ghost" data-action="viewOrder" data-order="${o.orderNo}">Voir</button>`;
    const statusActions = adminPermissions.orders ? `${advanceBtn}${cancelBtn}${failBtn}` : "";
    const btnHtml = `<div class="hero-row" style="gap:6px; flex-wrap:wrap">${viewBtn}${statusActions}</div>`;
    return `
      <tr>
        <td><b>${o.orderNo || ""}</b></td>
        <td>${o.createdAt ? new Date(o.createdAt).toLocaleString() : ""}</td>
        <td>${o.name || ""}<div class="mini">${o.phone || ""}</div></td>
        <td>${o.city || ""} / ${o.quarter || ""}</td>
        <td style="text-align:right"><b>${money(o.total || 0)}</b></td>
        <td>${paymentBadge(o.payment_status)}</td>
        <td>
          <span class="mini" title="${o.payment_ref || ""}">
            ${o.payment_ref ? o.payment_ref.slice(0, 18) + (o.payment_ref.length > 18 ? "…" : "") : "—"}
          </span>
        </td>
        <td>${statusBadge(o.status)}</td>
        <td>${btnHtml}</td>
      </tr>`;
  }).join("");

  if(filtered.length === 0){
    tbody.innerHTML = `<tr><td colspan="9" class="muted">Aucune commande pour ce filtre.</td></tr>`;
  }
}

async function renderDashboard(){
  try{
    if(role !== "admin") return;

    const range = (byId("dashRange")?.value) || "7";
    const moneyFmt = (typeof fmtMoney === "function")
      ? fmtMoney
      : (n)=> `${Number(n||0).toLocaleString()} FCFA`;

    const safeJson = async (res) => {
      const text = await res.text();
      try {
        return text ? JSON.parse(text) : {};
      } catch (_) {
        throw new Error(text?.slice(0, 120) || "Réponse invalide du serveur");
      }
    };

    // ===== COMMANDES / PAIEMENTS =====
    if(adminPermissions.orders || adminPermissions.payments){
      const oRes = await fetch(`/api/admin/orders/`);
      const oData = await safeJson(oRes);

      if(!oRes.ok || !oData.ok){
        throw new Error(oData.error || "Orders API error");
      }

      adminOrdersCache = oData.results || [];
      renderOrdersAdminTable(adminOrdersCache);
    }else{
      if(byId("ordersTable")){
        byId("ordersTable").innerHTML =
          `<tr><td colspan="9" class="muted">Accès non autorisé.</td></tr>`;
      }
    }

    // ===== STATS + ANALYTICS =====
    if(adminPermissions.orders){
      const [sRes, aRes] = await Promise.all([
        fetch(`/api/admin/stats/?days=${encodeURIComponent(range)}`),
        fetch(`/api/admin/analytics/?days=${encodeURIComponent(range)}`)
      ]);

      const sData = await safeJson(sRes);
      const aData = await safeJson(aRes);

      if(!sRes.ok || !sData.ok){
        throw new Error(sData.error || "Stats API error");
      }
      if(!aRes.ok || !aData.ok){
        throw new Error(aData.error || "Analytics API error");
      }

      if(byId("kpiGrid")){
        byId("kpiGrid").innerHTML = `
          <div class="kpi"><div class="muted">Chiffre d'affaires</div><div class="big">${moneyFmt(sData.revenue||0)}</div></div>
          <div class="kpi"><div class="muted">Commandes</div><div class="big">${(sData.orders||0)}</div></div>
          <div class="kpi"><div class="muted">Panier moyen</div><div class="big">${moneyFmt(sData.avg_order||0)}</div></div>
        `;
      }

      if(byId("topProducts")){
        byId("topProducts").innerHTML = (aData.top_products || []).map(x=>`
          <div class="row" style="justify-content:space-between; padding:8px 0;">
            <div>
              <div style="font-weight:800">${x.product_name}</div>
              <div class="muted">${x.sku}</div>
            </div>
            <div class="pill">${x.qty}</div>
          </div>
        `).join("") || `<div class="muted">Aucune donnée</div>`;
      }

      if(byId("revenueByZone")){
        byId("revenueByZone").innerHTML = (aData.revenue_by_zone || []).map(z=>`
          <div class="row" style="justify-content:space-between; padding:8px 0;">
            <div><div style="font-weight:800">${z.city} — ${z.quarter}</div></div>
            <div style="font-weight:900">${moneyFmt(z.revenue)}</div>
          </div>
        `).join("") || `<div class="muted">Aucune donnée</div>`;
      }
    }else{
      if(byId("kpiGrid")) byId("kpiGrid").innerHTML = "";
      if(byId("topProducts")) byId("topProducts").innerHTML = "";
      if(byId("revenueByZone")) byId("revenueByZone").innerHTML = "";
    }

    // ===== INVENTAIRE =====
    if(adminPermissions.inventory){
      await renderInventory();
    }else{
      if(byId("stockTable")){
        byId("stockTable").innerHTML =
          `<tr><td colspan="4" class="muted">Accès non autorisé.</td></tr>`;
      }
    }

    // ===== REVENDEURS =====
    if(adminPermissions.resellers){
      await renderResellerApps();
    }else{
      if(byId("resellerAppsTable")){
        byId("resellerAppsTable").innerHTML =
          `<tr><td colspan="8" class="muted">Accès non autorisé.</td></tr>`;
      }
    }

  }catch(e){
    console.error("DASHBOARD ERROR:", e);
    alert(`Dashboard: ${e.message}`);
  }
}



  function renderBars(mount, dataObj, isQty, labelFn, valFn){
    mount.innerHTML = "";
    const entries = Object.entries(dataObj).sort((a,b)=>b[1]-a[1]).slice(0,6);
    if(entries.length===0){ mount.innerHTML = `<div class="muted" style="margin-top:10px">Aucune donnee.</div>`; return; }
    const max = Math.max(...entries.map(e=>e[1]));
    entries.forEach(([k,v])=>{
      const percent = max ? Math.round((v/max)*100) : 0;
      const row = document.createElement("div");
      row.className = "barRow";
      row.innerHTML = `
        <div class="barName">${labelFn(k)}</div>
        <div class="barTrack"><div class="barFill" style="width:${percent}%"></div></div>
        <div class="barVal">${valFn ? valFn(v) : (isQty ? v+" pcs" : v)}</div>
      `;
      mount.appendChild(row);
    });
  }

  function renderOrdersTable(){
    const tb = byId("ordersTable");
    tb.innerHTML = "";
    const orders = loadOrders();
    if(orders.length===0){
      const tr = document.createElement("tr");
      tr.innerHTML = `<td colspan="7" class="muted">Aucune commande.</td>`;
      tb.appendChild(tr);
      return;
    }
    orders.forEach(o=>{
      const tr = document.createElement("tr");
      const date = new Date(o.createdAt).toLocaleString("fr-FR");
      const status = ORDER_STEPS[o.statusIndex] || "Inconnu";
      tr.innerHTML = `
        <td><strong>${o.orderNo}</strong><div class="mini">${o.role} • ${o.mode}</div></td>
        <td>${date}</td>
        <td><strong>${o.customer.name}</strong><div class="mini">${o.customer.phone}</div></td>
        <td>${o.customer.city} / ${o.customer.quarter}</td>
        <td><strong>${money(o.total)}</strong><div class="mini">Liv: ${money(o.shipping)}</div></td>
        <td><span class="statusPill ${o.statusIndex>=3?'ok':(o.statusIndex>=1?'warn':'')}">${status}</span></td>
        <td>
          <div class="hero-row">
            <button class="btn small warn" data-next="${o.orderNo}">⏩ Statut +</button>
            <button class="btn small danger" data-del="${o.orderNo}">🗑️</button>
          </div>
        </td>
      `;
      tb.appendChild(tr);
    });
    tb.querySelectorAll("[data-next]").forEach(b=>b.addEventListener("click", ()=>{ bumpStatus(b.getAttribute("data-next")); renderDashboard(); }));
    tb.querySelectorAll("[data-del]").forEach(b=>b.addEventListener("click", ()=>{ deleteOrder(b.getAttribute("data-del")); renderDashboard(); }));
  }

  function bumpStatus(orderNo){
    const orders = loadOrders();
    const idx = orders.findIndex(x=>x.orderNo===orderNo);
    if(idx<0) return;
    orders[idx].statusIndex = Math.min(3, (orders[idx].statusIndex||0) + 1);
    saveOrders(orders);
  }
  function deleteOrder(orderNo){ saveOrders(loadOrders().filter(x=>x.orderNo!==orderNo)); }
  function deleteAllOrders(){ saveOrders([]); renderDashboard(); }

  function renderStockTable(){
    const tb = byId("stockTable");
    tb.innerHTML = "";
    products.forEach(p=>{
      const sizesHtml = p.sizes.map(s=>{
        const st = stockOf(p.id, s);
        const cls = st<=0 ? "bad" : (st<=2 ? "warn" : "ok");
        const label = getVariantLabel(p);
        return `<span class="statusPill ${cls}">${label} ${s}: ${st}</span>`;
      }).join(" ");
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${p.id}</strong><div class="mini">${p.brand}</div></td>
        <td>${p.name}</td>
        <td>${sizesHtml}</td>
        <td>
          <div class="hero-row">
            <button class="btn small" data-plus="${p.id}">+1 toutes options</button>
            <button class="btn small danger" data-minus="${p.id}">-1 toutes options</button>
          </div>
        </td>
      `;
      tb.appendChild(tr);
    });

    tb.querySelectorAll("[data-plus]").forEach(b=>b.addEventListener("click", ()=>{
      const sku = b.getAttribute("data-plus");
      const p = getProduct(sku);
      p.sizes.forEach(s=>adjustStock(sku, s, +1));
      renderProducts(); renderProductDetail(); renderPacks(); renderDashboard(); renderCart();
    }));
    tb.querySelectorAll("[data-minus]").forEach(b=>b.addEventListener("click", ()=>{
      const sku = b.getAttribute("data-minus");
      const p = getProduct(sku);
      p.sizes.forEach(s=>adjustStock(sku, s, -1));
      renderProducts(); renderProductDetail(); renderPacks(); renderDashboard(); renderCart();
    }));
  }

  function seedDemoOrders(){
    const now = Date.now();
    const demos = [
      {p: products[0], size: products[0].sizes[1], city:"Douala", quarter:"Akwa"},
      {p: products[1], size: products[1].sizes[2], city:"Yaounde", quarter:"Bastos"},
    ];
    const orders = loadOrders();
    demos.forEach((d,idx)=>{
      const shipping = computeShipping(d.city, d.quarter);
      const total = d.p.retail + shipping;
      const orderNo = "TK" + Math.floor(100000 + Math.random()*900000);
      orders.unshift({
        orderNo,
        createdAt: new Date(now - idx*86400000).toISOString(),
        role:"visitor", mode:"retail",
        statusIndex: idx,
        customer:{name:"Client Demo", phone:"6xx xx xx xx", city:d.city, quarter:d.quarter, addr:"Repere"},
        pay:"MTN Mobile Money",
        shipping, subtotal:d.p.retail, total,
        items:[{sku:d.p.id, name:d.p.name, size:d.size, qty:1, unit:d.p.retail, source:"SEED"}]
      });
    });
    saveOrders(orders);
    renderDashboard();
  }

  function exportCsv(){
    const orders = loadOrders();
    if(orders.length===0){ alert("Aucune commande."); return; }
    const rows = [];
    rows.push(["orderNo","createdAt","role","mode","customer_name","customer_phone","city","quarter","address","status","shipping","subtotal","total","pay","items"]);
    orders.forEach(o=>{
      const items = (o.items||[]).map(x=>`${x.sku}:${x.size}:${x.qty}`).join("|");
      rows.push([o.orderNo,o.createdAt,o.role,o.mode,o.customer.name,o.customer.phone,o.customer.city,o.customer.quarter,o.customer.addr,ORDER_STEPS[o.statusIndex]||"",o.shipping,o.subtotal||"",o.total,o.pay,items]);
    });
    const csv = rows.map(r => r.map(v=>{
      const s = String(v ?? "");
      if(s.includes(",") || s.includes('"') || s.includes("\n")) return `"${s.replace(/"/g,'""')}"`;
      return s;
    }).join(",")).join("\n");
    const blob = new Blob([csv], {type:"text/csv;charset=utf-8"});
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = "tchokos_orders_v5.csv";
    document.body.appendChild(a); a.click(); a.remove(); URL.revokeObjectURL(url);
  }

 function openLogin(){
  openAuthModal("login");
}

async function submitLoginFromModal(){
  const username = (byId("loginUsername")?.value || "").trim();
  const password = (byId("loginPassword")?.value || "").trim();

  if(!username || !password){
    showAuthNote("Nom d'utilisateur et mot de passe obligatoires.");
    return;
  }

  const btn = byId("submitLoginBtn");
  const prev = btn ? btn.textContent : "";
  if(btn){
    btn.disabled = true;
    btn.textContent = "Connexion...";
  }

  try{
    const data = await apiPost("/api/admin/login/", { username, password });

    if(!data.ok){
      showAuthNote(data.error || "Connexion impossible.");
      return;
    }

    await syncRoleFromBackend();
    await refreshResellerStatus();
    renderAll();
    closeAuthModal();

    if(role === "admin") renderDashboard();

  }catch(err){
    showAuthNote(err?.error || err?.message || "Erreur réseau / serveur.");
  }finally{
    if(btn){
      btn.disabled = false;
      btn.textContent = prev || "Se connecter";
    }
  }
}

async function submitRegisterFromModal(){
  const username = (byId("registerUsername")?.value || "").trim();
  const phone = (byId("registerPhone")?.value || "").trim();
  const password = (byId("registerPassword")?.value || "").trim();
  const password2 = (byId("registerPassword2")?.value || "").trim();

  if(!username || !phone || !password || !password2){
    showAuthNote("Tous les champs sont obligatoires.");
    return;
  }

  if(password !== password2){
    showAuthNote("Les mots de passe ne correspondent pas.");
    return;
  }

  if(password.length < 6){
    showAuthNote("Le mot de passe doit faire au moins 6 caractères.");
    return;
  }

  const btn = byId("submitRegisterBtn");
  const prev = btn ? btn.textContent : "";
  if(btn){
    btn.disabled = true;
    btn.textContent = "Création...";
  }

  try{
    const data = await apiPost("/api/admin/register/", {
      username,
      phone,
      password
    });

    if(!data.ok){
      showAuthNote(data.error || "Inscription impossible.");
      return;
    }

    await syncRoleFromBackend();
    await refreshResellerStatus();
    renderAll();
    closeAuthModal();

  }catch(err){
    showAuthNote(err?.error || err?.message || "Erreur réseau / serveur.");
  }finally{
    if(btn){
      btn.disabled = false;
      btn.textContent = prev || "Créer mon compte";
    }
  }
}


  (async function boot(){
  await loadProductsFromApi();   // charge les produits depuis Django
  initFilters();
  initCityQuarter();
  
  await syncRoleFromBackend();
  await refreshResellerStatus();
  renderAll();
  goTab("shop");
})();


  function renderAll(){
    renderProducts();
    renderProductDetail();
    renderCart();
    renderPacks();
    if(role==="admin") renderDashboard();
  }

  let resellerStatus = "none"; // none | pending | approved | rejected

function openResellerModal(){
  const isLoggedIn = byId("logoutBtn")?.style.display !== "none";

  if(!isLoggedIn){
    alert("Connecte-toi ou crée un compte avant d’envoyer une demande revendeur.");
    return;
  }

  if(role === "admin"){
    alert("Un admin ne peut pas postuler comme revendeur.");
    return;
  }

  if(role === "reseller"){
    alert("Ton compte est déjà revendeur.");
    return;
  }

  byId("resellerModal").style.display = "flex";
}

function closeResellerModal(){
  byId("resellerModal").style.display = "none";
}

function showResellerNote(msg){
  const n = byId("resellerStatusNote");
  n.style.display = "block";
  n.textContent = msg;
}

async function refreshResellerStatus(){
  const isLoggedIn = byId("logoutBtn")?.style.display !== "none";

  if(!isLoggedIn){
    resellerStatus = "none";
    const btn = byId("applyResellerBtn");
    if(btn){
      btn.style.display = (role === "admin" || role === "reseller") ? "none" : "inline-flex";
      btn.textContent = "🤝 Devenir revendeur";
      btn.disabled = false;
    }
    return;
  }

  try{
    const res = await fetch("/api/reseller/status/");
    const data = await res.json().catch(()=>({}));

    if(res.ok && data.ok){
      resellerStatus = data.status || "none";
    }else{
      resellerStatus = "none";
    }
  }catch(e){
    resellerStatus = "none";
  }

  const btn = byId("applyResellerBtn");
  if(!btn) return;

  if(role === "reseller" || role === "admin"){
    btn.style.display = "none";
    return;
  }

  btn.style.display = "inline-flex";

  if(resellerStatus === "pending"){
    btn.textContent = "⏳ Demande en attente";
    btn.disabled = false;
  }else if(resellerStatus === "approved"){
    btn.textContent = "✅ Revendeur approuvé";
    btn.disabled = false;
  }else if(resellerStatus === "rejected"){
    btn.textContent = "❌ Demande refusée (repostuler)";
    btn.disabled = false;
  }else{
    btn.textContent = "🤝 Devenir revendeur";
    btn.disabled = false;
  }
}

async function submitResellerApplication(){
  const full_name = (byId("raFullName").value || "").trim();
  const phone = (byId("raPhone").value || "").trim();
  const city = (byId("raCity").value || "").trim();
  const shop_name = (byId("raShop").value || "").trim();
  const instagram = (byId("raInsta").value || "").trim();
  const monthly_volume = parseInt(byId("raVolume").value || "0", 10) || 0;
  const message = (byId("raMsg").value || "").trim();

  if(!full_name || !phone){
    showResellerNote("Nom et téléphone obligatoires.");
    return;
  }

  const isLoggedIn = byId("logoutBtn")?.style.display !== "none";
  if(!isLoggedIn){
    showResellerNote("Connecte-toi ou crée un compte avant d’envoyer une demande revendeur.");
    return;
  }

  if(role === "admin"){
    showResellerNote("Un admin ne peut pas postuler.");
    return;
  }

  if(role === "reseller"){
    showResellerNote("Ton compte est déjà revendeur.");
    return;
  }

  const btn = byId("submitResellerBtn");
  const prev = btn ? btn.textContent : "";
  if(btn){
    btn.disabled = true;
    btn.textContent = "Envoi...";
  }

  try{
    const data = await apiPost("/api/reseller/apply/", {
      full_name,
      phone,
      city,
      shop_name,
      instagram,
      monthly_volume,
      message
    });

    if(!data.ok){
      showResellerNote(data.error || "Erreur. Réessaie.");
      return;
    }

    showResellerNote("✅ Demande envoyée. Statut: " + (data.status || "pending"));
    await refreshResellerStatus();

  }catch(err){
    showResellerNote(err?.error || err?.message || "Erreur réseau / serveur.");
  }finally{
    if(btn){
      btn.disabled = false;
      btn.textContent = prev || "Envoyer la demande";
    }
  }
}

 

  // Events
  byId("loginBtn")?.addEventListener("click", openLogin);
  byId("logoutBtn")?.addEventListener("click", logout);
  byId("tabShop")?.addEventListener("click", ()=>goTab("shop"));
  byId("tabReseller")?.addEventListener("click", ()=>goTab("reseller"));
  byId("tabTrack")?.addEventListener("click", ()=>goTab("track"));
  byId("tabAdmin")?.addEventListener("click", ()=>goTab("admin"));

  byId("search")?.addEventListener("input", (e)=>{ query = e.target.value || ""; renderProducts(); });
  byId("brandFilter")?.addEventListener("change", (e)=>{ brand = e.target.value; renderProducts(); });
  byId("catFilter")?.addEventListener("change", (e)=>{ cat = e.target.value; renderProducts(); });

  byId("checkoutBtn")?.addEventListener("click", openCheckout);
  byId("openCheckoutBtn")?.addEventListener("click", openCheckout);
  byId("payNowBtn")?.addEventListener("click", payNow);
  byId("copyOrderBtn")?.addEventListener("click", copyOrderNo);

  byId("clearCartBtn")?.addEventListener("click", clearCart);
  byId("goTrackBtn")?.addEventListener("click", ()=>goTab("track"));

  byId("trackBtn")?.addEventListener("click", ()=>{
    const no = (byId("trackInput").value||"").trim();
    if(!no){ alert("Entre un numero."); return; }
    renderTrackingFromApi(no);
  });

  byId("pasteBtn")?.addEventListener("click", async ()=>{
    try{
      const t = await navigator.clipboard.readText();
      if(t) byId("trackInput").value = t.trim();
    }catch(e){ alert("Collage bloque."); }
  });
  byId("resetDemoBtn")?.addEventListener("click", resetDemo);

  byId("dashRange")?.addEventListener("change", ()=> renderDashboard());
  byId("paymentFilter")?.addEventListener("change", ()=> {
  renderOrdersAdminTable(adminOrdersCache);
});
byId("statusFilter")?.addEventListener("change", ()=> {
  renderOrdersAdminTable(adminOrdersCache);
});

byId("orderSearch")?.addEventListener("input", ()=> {
  renderOrdersAdminTable(adminOrdersCache);
});
byId("refreshDashBtn")?.addEventListener("click", ()=> renderDashboard());
byId("seedDemoBtn")?.addEventListener("click", seedDemoOrders);
byId("exportCsvBtn")?.addEventListener("click", exportCsv);
byId("refreshAdminBtn")?.addEventListener("click", renderDashboard);
byId("ordersTable")?.addEventListener("click", async (e) => {
  const btnAny = e.target.closest("button[data-action]");
  if (!btnAny) return;

  const action = (btnAny.getAttribute("data-action") || "").toLowerCase();
  const orderNo = btnAny.getAttribute("data-order");

  // ✅ VOIR
  if (action === "vieworder") {
    if (orderNo) openOrderDetail(orderNo);
    return;
  }

  // ✅ NEXT (préparer/expédier/livrer)
  if (action === "nextstatus") {
    const next = (btnAny.getAttribute("data-next") || "").toLowerCase();
    if (!orderNo || !next) { alert("Bouton mal formé."); return; }

    const prev = btnAny.textContent;
    btnAny.disabled = true; btnAny.textContent = "…";
    try {
      const data = await apiPost(`/api/admin/order/${encodeURIComponent(orderNo)}/status/`, { status: next });
      if (!data.ok) { alert(data.error || "Erreur update statut."); return; }
      await renderDashboard();
    } catch (err) {
      alert(err?.error || err?.message || "Erreur réseau / serveur.");
    } finally {
      btnAny.disabled = false; btnAny.textContent = prev;
    }
    return;
  }

  // ✅ SET (annuler/échouer)
 if (action === "setstatus") {
  const status = (btnAny.getAttribute("data-status") || "").toLowerCase();
  if (!orderNo || !status) {
    alert("Bouton mal formé.");
    return;
  }

  let note = "";

  if (status === "cancelled") {
    note = prompt("Raison de l'annulation (optionnel) :", "") ?? "";
    if (!confirm(`Annuler la commande ${orderNo} ?`)) return;
  }

  if (status === "failed") {
    note = prompt("Raison de l'échec (obligatoire) :", "") ?? "";
    note = note.trim();

    if (!note) {
      alert("Une raison est obligatoire pour marquer la commande comme échouée.");
      return;
    }

    if (!confirm(`Marquer ${orderNo} comme ÉCHOUÉE ?`)) return;
  }

  const prev = btnAny.textContent;
  btnAny.disabled = true;
  btnAny.textContent = "…";

  try {
    const data = await apiPost(`/api/admin/order/${encodeURIComponent(orderNo)}/status/`, {
      status,
      note
    });

    if (!data.ok) {
      alert(data.error || "Erreur update statut.");
      return;
    }

    await renderDashboard();
    await openOrderDetail(orderNo);
  } catch (err) {
    alert(err?.error || err?.message || "Erreur réseau / serveur.");
  } finally {
    btnAny.disabled = false;
    btnAny.textContent = prev;
  }
  return;
}
});




byId("stockTable")?.addEventListener("click", async (e) => {
  const btn = e.target.closest("[data-action='stockAdj']");
  if (!btn) return;

  const sku = btn.getAttribute("data-sku");
  const size = btn.getAttribute("data-size");
  const delta = Number(btn.getAttribute("data-delta"));

  btn.disabled = true;

  try {
    const data = await apiPost("/api/admin/inventory/adjust/", { sku, size, delta });
    if (!data.ok) {
      alert(data.error || "Erreur stock.");
      return;
    }

    await renderInventory();
    await loadProductsFromApi();
    renderProducts();
    renderProductDetail();

  } catch (err) {
    alert(err?.error || err?.message || "Erreur réseau / serveur.");
  } finally {
    btn.disabled = false;
  }
});


  byId("deleteAllBtn")?.addEventListener("click", deleteAllOrders);

async function syncRoleFromBackend(){
  try{
    const res = await fetch("/api/admin/me/");
    const data = await res.json().catch(()=> ({}));

    if(data.authenticated){
      role = data.role || "visitor";
      adminPermissions = data.permissions || {
        super_admin: false,
        orders: false,
        payments: false,
        inventory: false,
        resellers: false,
      };

      if(byId("loginBtn")) byId("loginBtn").style.display = "none";
      if(byId("logoutBtn")) byId("logoutBtn").style.display = "inline-flex";
    }else{
      role = "visitor";
      adminPermissions = {
        super_admin: false,
        orders: false,
        payments: false,
        inventory: false,
        resellers: false,
      };

      if(byId("loginBtn")) byId("loginBtn").style.display = "inline-flex";
      if(byId("logoutBtn")) byId("logoutBtn").style.display = "none";
    }

    mode = (role === "reseller") ? "reseller" : "retail";
    syncRoleUI();
  }catch(e){
    role = "visitor";
    mode = "retail";
    adminPermissions = {
      super_admin: false,
      orders: false,
      payments: false,
      inventory: false,
      resellers: false,
    };

    if(byId("loginBtn")) byId("loginBtn").style.display = "inline-flex";
    if(byId("logoutBtn")) byId("logoutBtn").style.display = "none";
    syncRoleUI();
  }
}

byId("applyResellerBtn")?.addEventListener("click", async ()=>{
  await refreshResellerStatus();

  if(resellerStatus === "pending") showResellerNote("⏳ Ta demande est en attente.");
  else if(resellerStatus === "approved") showResellerNote("✅ Déjà approuvé. Déconnecte/reconnecte pour activer le rôle.");
  else if(resellerStatus === "rejected") showResellerNote("❌ Refusé. Tu peux modifier et renvoyer.");
  else if(byId("resellerStatusNote")) byId("resellerStatusNote").style.display = "none";

  openResellerModal();
});

byId("closeResellerModalBtn")?.addEventListener("click", closeResellerModal);
byId("cancelResellerBtn")?.addEventListener("click", closeResellerModal);
byId("submitResellerBtn")?.addEventListener("click", submitResellerApplication);

// fermer en cliquant sur l’overlay
byId("resellerModal")?.addEventListener("click", (e)=>{
  if(e.target.id === "resellerModal") closeResellerModal();
});

// Reseller Applications dashboard
byId("refreshResellerAppsBtn")?.addEventListener("click", renderResellerApps);
byId("raStatusFilter")?.addEventListener("change", renderResellerApps);

byId("resellerAppsTable")?.addEventListener("click", async (e)=>{
  const approveBtn = e.target.closest("[data-action='raApprove']");
  const rejectBtn = e.target.closest("[data-action='raReject']");
  const btn = approveBtn || rejectBtn;
  if(!btn) return;

  const id = btn.getAttribute("data-id");
  if(!id) return;

  try{
    if(approveBtn) await resellerAppAction(id, "approve");
    else await resellerAppAction(id, "reject");

    await renderResellerApps();
    // optionnel: refresh me/orders si tu veux
  }catch(err){
    alert("Erreur: " + err.message);
  }
});
function openResellerTerms(){
  const m = byId("resellerTermsModal");
  if(m) m.style.display = "block";
}
function closeResellerTerms(){
  const m = byId("resellerTermsModal");
  if(m) m.style.display = "none";
}

byId("openResellerTermsBtn")?.addEventListener("click", openResellerTerms);
byId("closeResellerTermsBtn")?.addEventListener("click", closeResellerTerms);

// clic sur fond = ferme
byId("resellerTermsModal")?.addEventListener("click", (e)=>{
  if(e.target && e.target.id === "resellerTermsModal") closeResellerTerms();
});

// bouton "Devenir revendeur" depuis ce modal
byId("goApplyResellerBtn")?.addEventListener("click", ()=>{
  closeResellerTerms();
  // si tu as déjà une fonction/btn qui ouvre le modal du formulaire:
  // openResellerApplyModal();
  // sinon, déclenche un bouton existant :
  const btn = document.getElementById("applyResellerBtn");
  if(btn) btn.click();
});

byId("closeOrderDetailBtn")?.addEventListener("click", ()=> byId("orderDetailModal").style.display="none");
byId("orderDetailModal")?.addEventListener("click",(e)=>{ if(e.target.id==="orderDetailModal") byId("orderDetailModal").style.display="none"; });
//byId("submitLoginBtn")?.addEventListener("click", submitLoginFromModal);
//byId("submitRegisterBtn")?.addEventListener("click", submitRegisterFromModal);

document.addEventListener("click", async (e) => {
  const btn = e.target.closest("button");
  if(!btn) return;

  const id = btn.id || "";

  if(id === "loginBtn"){
    openAuthModal("login");
    return;
  }

  if(id === "closeAuthModalBtn"){
    closeAuthModal();
    return;
  }

  if(id === "authTabLogin"){
    switchAuthTab("login");
    return;
  }

  if(id === "authTabRegister"){
    switchAuthTab("register");
    return;
  }

  if(id === "submitLoginBtn"){
    await submitLoginFromModal();
    return;
  }

  if(id === "submitRegisterBtn"){
    await submitRegisterFromModal();
    return;
  }
});

byId("authModal")?.addEventListener("click", (e)=>{
  if(e.target && e.target.id === "authModal"){
    closeAuthModal();
  }
});
byId("closeCheckoutSuccessBtn")?.addEventListener("click", closeCheckoutSuccessModal);

byId("checkoutSuccessModal")?.addEventListener("click", (e)=>{
  if(e.target && e.target.id === "checkoutSuccessModal"){
    closeCheckoutSuccessModal();
  }
});

byId("copySuccessOrderBtn")?.addEventListener("click", async ()=>{
  const no = (byId("successOrderNo")?.textContent || "").trim();
  if(!no) return;

  try{
    await navigator.clipboard.writeText(no);
    alert("Numéro copié ✅");
  }catch(e){
    window.prompt("Copie le numéro :", no);
  }
});

byId("goTrackSuccessBtn")?.addEventListener("click", ()=>{
  const no = (byId("successOrderNo")?.textContent || "").trim();
  closeCheckoutSuccessModal();
  goTab("track");
  if(byId("trackInput")) byId("trackInput").value = no;
  if(no) renderTrackingFromApi(no);
});

byId("refreshResellerOrdersBtn")?.addEventListener("click", renderResellerOrders);

byId("resellerStatusFilter")?.addEventListener("change", ()=> {
  renderResellerOrdersTable(resellerOrdersCache);
});

byId("resellerPaymentFilter")?.addEventListener("change", ()=> {
  renderResellerOrdersTable(resellerOrdersCache);
});

byId("resellerOrderSearch")?.addEventListener("input", ()=> {
  renderResellerOrdersTable(resellerOrdersCache);
});

byId("resellerOrdersTable")?.addEventListener("click", (e)=>{
  const btn = e.target.closest("button[data-action='viewResellerOrder']");
  if(!btn) return;
  const orderNo = btn.getAttribute("data-order");
  if(orderNo) openResellerOrderDetail(orderNo);
});

byId("closeResellerOrderDetailBtn")?.addEventListener("click", closeResellerOrderDetail);

byId("resellerOrderDetailModal")?.addEventListener("click", (e)=>{
  if(e.target.id === "resellerOrderDetailModal") closeResellerOrderDetail();
});

byId("resellerSortFilter")?.addEventListener("change", ()=> {
  renderResellerOrdersTable(resellerOrdersCache);
});

document.addEventListener("click", (e)=>{
  const btn = e.target.closest(".resellerTabBtn");
  if(!btn) return;
  const tab = btn.getAttribute("data-reseller-tab");
  if(tab) switchResellerTab(tab);
});





