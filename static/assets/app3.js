const SHIPPING = {
    "Douala": { base: 1500, quarters: {"Akwa":500, "Bonamoussadi":700, "Deido":600, "Logpom":900, "PK14":1200, "Autre":1400} },
    "Yaounde":{ base: 2500, quarters: {"Bastos":900, "Mvan":700, "Nlongkak":800, "Emana":900, "Autre":1200} },
    "Kribi":  { base: 2000, quarters: {"Centre":700, "Beach":900, "Autre":1100} },
    "Bafoussam": { base: 3000, quarters: {"Centre":800, "Autre":1200} },
    "Autre": { base: 4000, quarters: {"Autre":1000} }
  };
  const ORDER_STEPS = ["Commande recue","Preparation","Expediee","Livree"];
  const LS = { STOCK:"tchokos_v5_stock_by_size", ORDERS:"tchokos_v5_orders" };


  let products = []; 
  async function loadProductsFromApi(){
  const res = await fetch("/api/products/");
  const data = await res.json();

  stockMap = {};
  products = (data.results || []).map(p => {
    // stock par taille depuis backend
    stockMap[p.sku] = {};
    (p.variants || []).forEach(v => {
      stockMap[p.sku][v.size] = Number(v.stock_qty ?? 0);
    });

    return {
      id: p.sku,
      brand: p.brand || "",
      name: p.name || "",
      cat: p.category || "",
      tag: p.tag || "",
      desc: p.description || "",
      sizes: (p.variants || []).map(v => v.size),
      retail: p.retail_price || 0,
      reseller: p.reseller_price || 0,
      moq: p.reseller_moq || 1
    };
  });
}



  const packs = [
    { id:"PK-NIKE-12", title:"Carton Nike Air (12 paires)", sku:"NK-AIR-01", packPrice: 150000, defaultDist: {39:2,40:2,41:3,42:3,43:1,44:1} },
    { id:"PK-JORDAN-6", title:"Carton Jordan Retro (6 paires)", sku:"JD-RET-07", packPrice: 96000, defaultDist: {40:1,41:1,42:2,43:1,44:1} },
  ];

  let role = "visitor"; // visitor / reseller / admin
  let mode = "retail"; // retail / reseller
  let isAuthenticated = false;
  let currentUser = null;
  let afterAuthAction = null; // ex: "reseller"
  let cart = [];
  let selectedProductId = null;
  let query = "", brand = "ALL", cat = "ALL";

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
    const btn = byId("becomeResellerBtn");
    if(btn) btn.style.display = (role === "visitor") ? "inline-flex" : "none";
    byId("roleLabel").textContent = role==="visitor" ? "Visiteur" : (role==="reseller" ? "Revendeur" : "Admin");
    byId("modeLabel").textContent = mode==="reseller" ? "Revendeur" : "Detail";
    byId("resellerGate").style.display = (role==="reseller" ? "none" : "block");
    byId("resellerPanel").style.display = (role==="reseller" ? "block" : "none");
    byId("adminGate").style.display = (role==="admin" ? "none" : "block");
    byId("adminPanel").style.display = (role==="admin" ? "block" : "none");

    // Devenir revendeur: visible seulement si role=visitor
    const applyBtn = byId("applyResellerBtn");
    if(applyBtn){
      const canSee = (role === "visitor");
      applyBtn.style.display = canSee ? "inline-flex" : "none";
      applyBtn.textContent = (!isAuthenticated && canSee)
        ? "🤝 Devenir revendeur (connexion)"
        : "🤝 Devenir revendeur";
    }

  }

  function totalStockOfSku(sku){
  const sizes = stockMap?.[sku] || {};
  return Object.values(sizes).reduce((a,b)=>a+Number(b||0),0);
}

  function adjustStock(sku, size, delta){
  stockMap[sku] = stockMap[sku] || {};
  const cur = Number(stockMap[sku][size] ?? 0);
  stockMap[sku][size] = Math.max(0, cur + delta);
}

  function validateStock(sku, size, qty){
    const available = stockOf(sku, size);
    if(qty > available) return {ok:false, msg:`Stock insuffisant pour ${sku} taille ${size}. Dispo: ${available}`};
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

  function renderProducts(){
    const grid = byId("productGrid");
    grid.innerHTML = "";
    const list = filteredProducts();
    byId("resultCount").textContent = `${list.length} produit(s)`;
    list.forEach(p=>{
      const totalSt = totalStockOfSku(p.id);
      const statusClass = totalSt<=0 ? "bad" : (totalSt<=6 ? "warn" : "ok");
      const card = document.createElement("div");
      card.className = "card";
      card.innerHTML = `
        <div class="img">
          <div class="tag">${p.tag}</div>
          <div class="statusPill ${statusClass}">${totalSt} stock total</div>
        </div>
        <div class="content">
          <div class="title">
            <div>
              <h4>${p.name}</h4>
              <div class="code">${p.brand} • ${p.id} • ${p.cat}<br/>MOQ revendeur: ${p.moq}</div>
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

    grid.querySelectorAll("[data-detail]").forEach(b=>{
      b.addEventListener("click", ()=> showProductDetail(b.getAttribute("data-detail")));
    });
    grid.querySelectorAll("[data-quick]").forEach(b=>{
      b.addEventListener("click", ()=> quickAdd(b.getAttribute("data-quick")));
    });
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
    const sizesHtml = p.sizes.map(s=>{
      const st = stockOf(p.id, s);
      const cls = st<=0 ? "bad" : (st<=2 ? "warn" : "ok");
      return `<span class="statusPill ${cls}">T${s}: ${st}</span>`;
    }).join(" ");

    mount.className = "";
    mount.innerHTML = `
      <div class="productPage">
        <div class="bigImg"><div class="tag">${p.brand}</div><div class="tag">${p.id}</div></div>
        <div class="box">
          <div class="section-title" style="margin:0 0 8px 0">
            <h3 style="margin:0;font-size:14px">${p.name}</h3>
            <span class="mini">${p.cat} • ${p.tag}</span>
          </div>
          <div class="badges">
            <span class="badge">${mode==="reseller" ? "Tarif revendeur" : "Tarif detail"}</span>
            <span class="badge">MOQ: ${p.moq}</span>
            <span class="badge">Stock par taille</span>
          </div>
          <div class="muted">${p.desc}</div>

          <div class="section-title" style="margin-top:12px">
            <h3 style="margin:0;font-size:13px">Tailles (variantes)</h3>
            <span class="mini">stock live</span>
          </div>
          <div class="mini" style="line-height:2">${sizesHtml}</div>

          <div style="margin-top:12px">
            <div class="row"><span>Prix</span><strong>${money(priceOf(p))}</strong></div>
          </div>

          <div class="checkout-grid" style="margin-top:10px">
            <div><label>Taille</label><select id="pdSize">${p.sizes.map(s=>`<option value="${s}">${s}</option>`).join("")}</select></div>
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

    byId("pdAddBtn").addEventListener("click", ()=>{
      const size = parseInt(byId("pdSize").value, 10);
      const qty = parseInt(byId("pdQty").value, 10) || 1;
      if(mode==="reseller" && qty < p.moq){ alert(`MOQ revendeur = ${p.moq}`); return; }
      const v = validateStock(p.id, size, qty);
      if(!v.ok){ alert(v.msg); return; }
      addToCart(p.id, size, qty, "PRODUCT");
    });
  }

  function quickAdd(sku){
    const p = getProduct(sku);
    const size = p.sizes[Math.floor(p.sizes.length/2)];
    const qty = (mode==="reseller" ? p.moq : 1);
    const v = validateStock(sku, size, qty);
    if(!v.ok){ alert(v.msg); return; }
    addToCart(sku, size, qty, "QUICK");
  }

  function addToCart(sku, size, qty, source){
    const key = `${sku}__${size}__${source}`;
    const existing = cart.find(x => `${x.sku}__${x.size}__${x.source}` === key);
    if(existing) existing.qty += qty;
    else cart.push({sku, size, qty, source});
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
            <p class="ci-title">${p.name}</p>
            <p class="ci-sub">${i.sku} • Taille ${i.size} • ${money(priceOf(p))} • Stock T${i.size}: ${stockOf(i.sku,i.size)} • Source: ${i.source}</p>
            <div class="qty">
              <button aria-label="moins">−</button>
              <span>${i.qty}</span>
              <button aria-label="plus">+</button>
              <button class="btn small danger" style="margin-left:6px" aria-label="supprimer">Suppr.</button>
            </div>
          </div>
        </div>
        <div style="font-size:12px;font-weight:900">${money(priceOf(p)*i.qty)}</div>
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

  // MOQ revendeur (inchangé)
  if(mode==="reseller"){
    const agg = {};
    cart.forEach(i=> agg[i.sku] = (agg[i.sku]||0) + i.qty);
    for(const sku in agg){
      const p = getProduct(sku);
      if(agg[sku] < p.moq){ alert(`MOQ non atteint pour ${sku}: minimum ${p.moq}`); return; }
    }
  }

  // Validation stock (sur stockMap backend) - inchangé
  for(const i of cart){
    const v = validateStock(i.sku, i.size, i.qty);
    if(!v.ok){ alert(v.msg); return; }
  }

  // Champs client (inchangé)
  const name = (byId("cName").value||"").trim();
  const phone = (byId("cPhone").value||"").trim();
  const city = byId("cCity").value;
  const quarter = byId("cQuarter").value;
  const addr = (byId("cAddr").value||"").trim();
  if(!name || !phone || !addr){ alert("Remplis Nom, Telephone, Adresse."); return; }

  // Totaux
  const {subtotal, shipping, total} = computeTotals();

  // Payload vers Django
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
    const csrf = document.querySelector('meta[name="csrf-token"]').getAttribute("content");
    const res = await fetch("/api/checkout/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf
      },
      body: JSON.stringify(payload)
    });

    const data = await res.json().catch(()=> ({}));

    if(!res.ok || !data.ok){
      alert(data.error || "Erreur checkout.");
      return;
    }

    // Succès -> affiche orderNo renvoyé par Django
    const orderNo = data.orderNo;

    byId("orderNo").textContent = orderNo;
    byId("successBox").style.display = "block";

    // Vide panier
    cart = [];
    renderCart();

    // Recharge produits + stock réels depuis backend
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
              <div class="muted">${it.sku} • T${it.size} • x${it.qty}</div>
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
    packs.forEach(pk=>{
      const p = getProduct(pk.sku);
      const sizes = Object.keys(pk.defaultDist).map(x=>parseInt(x,10)).sort((a,b)=>a-b);

      const distInputs = sizes.map(s=>{
        return `
          <div class="distCell">
            <strong>T${s}</strong>
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
        <div class="hintline">Permission : seulement revendeur. MOQ verifie avant ajout.</div>
      `;
      grid.appendChild(card);
    });

    grid.querySelectorAll("[data-addpack]").forEach(b=>b.addEventListener("click", ()=> addPackToCart(b.getAttribute("data-addpack"))));
    grid.querySelectorAll("[data-resetpack]").forEach(b=>b.addEventListener("click", ()=> resetPackDist(b.getAttribute("data-resetpack"))));
  }

  function resetPackDist(packId){
    const pk = packs.find(x=>x.id===packId);
    document.querySelectorAll(`input[data-pack="${packId}"]`).forEach(inp=>{
      const size = parseInt(inp.getAttribute("data-size"),10);
      inp.value = pk.defaultDist[size] ?? 0;
    });
  }

  function readPackDist(packId){
    const inputs = document.querySelectorAll(`input[data-pack="${packId}"]`);
    const dist = {};
    inputs.forEach(inp=>{
      const size = parseInt(inp.getAttribute("data-size"),10);
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
      const size = parseInt(sStr,10);
      const qty = dist[size];
      if(qty<=0) continue;
      const v = validateStock(sku, size, qty);
      if(!v.ok){ alert(v.msg); return; }
    }
    const p = getProduct(sku);
    if(total < p.moq){ alert(`MOQ non atteint pour ${sku}: minimum ${p.moq}`); return; }
    for(const sStr in dist){
      const size = parseInt(sStr,10);
      const qty = dist[size];
      if(qty<=0) continue;
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
  }async function renderInventory(){
  const res = await fetch("/api/admin/inventory/");
  const data = await res.json();
  if(!res.ok || !data.ok) throw new Error(data.error || "Inventory API error");

  const tbody = byId("stockTable");
  if(!tbody) return;

  tbody.innerHTML = (data.results || []).map(p=>{
    const sizes = p.sizes || {};
    const sizeChips = Object.keys(sizes).sort((a,b)=>Number(a)-Number(b)).map(s=>{
      const qty = sizes[s];
      const low = qty <= 10;
      return `<span class="pill ${low ? "dangerPill" : ""}">T${s}: ${qty}</span>`;
    }).join(" ");

    const actions = Object.keys(sizes).sort((a,b)=>Number(a)-Number(b)).map(s=>`
      <div style="display:flex; gap:6px; align-items:center; margin:4px 0;">
        <span class="muted" style="min-width:48px">T${s}</span>
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
  const csrf =
    (document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")) ||
    (byId("csrfToken")?.value) || "";

  const url = action === "approve"
    ? `/api/admin/reseller/applications/${encodeURIComponent(appId)}/approve/`
    : `/api/admin/reseller/applications/${encodeURIComponent(appId)}/reject/`;

  const res = await fetch(url, {
    method: "POST",
    headers: { "X-CSRFToken": csrf }
  });

  const data = await res.json().catch(()=>({}));
  if(!res.ok || !data.ok) throw new Error(data.error || "Action failed");
  return data;
}

async function renderDashboard(){
  try{
    const range = (byId("dashRange")?.value) || "7";

    // fallback money si fmtMoney n'existe pas
    const money = (typeof fmtMoney === "function")
      ? fmtMoney
      : (n)=> `${Number(n||0).toLocaleString()} FCFA`;

    // fetch stats + orders
    const sRes = await fetch(`/api/admin/stats/?days=${encodeURIComponent(range)}`);
    const sData = await sRes.json();

    const oRes = await fetch(`/api/admin/orders/`);
    const oData = await oRes.json();

    const aRes = await fetch(`/api/admin/analytics/?days=${encodeURIComponent(range)}`);
    const aData = await aRes.json();


    if(!sRes.ok || !sData.ok) throw new Error(sData.error || "Stats API error");
    if(!oRes.ok || !oData.ok) throw new Error(oData.error || "Orders API error");

    // KPIs
    const kpiGrid = byId("kpiGrid");
    if(kpiGrid){
      kpiGrid.innerHTML = `
        <div class="kpi"><div class="muted">Chiffre d'affaires</div><div class="big">${money(sData.revenue||0)}</div></div>
        <div class="kpi"><div class="muted">Commandes</div><div class="big">${(sData.orders||0)}</div></div>
        <div class="kpi"><div class="muted">Panier moyen</div><div class="big">${money(sData.avg_order||0)}</div></div>
      `;
    }
    await renderResellerApps();

    // Next status buttons
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

    // Orders table
    const tbody = byId("ordersTable");
    if(tbody){
      tbody.innerHTML = (oData.results || []).map(o=>{
        const next = nextMap[o.status] || "";
        const btnHtml = next
          ? `<button class="btn small" data-action="nextStatus" data-order="${o.orderNo}" data-next="${next}">
               ${labelMap[o.status] || "Avancer"}
             </button>`
          : `<button class="btn small ghost" disabled>✅ Terminé</button>`;

        return `
          <tr>
            <td><b>${o.orderNo || ""}</b></td>
            <td>${o.createdAt ? new Date(o.createdAt).toLocaleString() : ""}</td>
            <td>${o.customer || ""}</td>
            <td>${o.zone || ""}</td>
            <td style="text-align:right"><b>${money(o.total || 0)}</b></td>
            <td>${o.status || ""}</td>
            <td>${btnHtml}</td>
          </tr>
        `;
        
      }).join("");
      await renderInventory();
    }

    
    // placeholders (étape 9 remplira vraiment ces blocs)
    byId("topProducts").innerHTML = (aData.top_products || []).map(x=>`
  <div class="row" style="justify-content:space-between; padding:8px 0;">
    <div>
      <div style="font-weight:800">${x.product_name}</div>
      <div class="muted">${x.sku}</div>
    </div>
    <div class="pill">${x.qty}</div>
  </div>
`).join("") || `<div class="muted">Aucune donnée</div>`;

byId("revenueByZone").innerHTML = (aData.revenue_by_zone || []).map(z=>`
  <div class="row" style="justify-content:space-between; padding:8px 0;">
    <div>
      <div style="font-weight:800">${z.city} — ${z.quarter}</div>
    </div>
    <div style="font-weight:900">${money(z.revenue)}</div>
  </div>
`).join("") || `<div class="muted">Aucune donnée</div>`;


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
        return `<span class="statusPill ${cls}">T${s}:${st}</span>`;
      }).join(" ");
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td><strong>${p.id}</strong><div class="mini">${p.brand}</div></td>
        <td>${p.name}</td>
        <td>${sizesHtml}</td>
        <td>
          <div class="hero-row">
            <button class="btn small" data-plus="${p.id}">+1 toutes tailles</button>
            <button class="btn small danger" data-minus="${p.id}">-1 toutes tailles</button>
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

  async function openLogin(){
  const username = prompt("Username Django (ex: admin) ?");
  if(!username) return;

  const password = prompt("Password ?");
  if(!password) return;

  const csrf =
    (document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")) ||
    (byId("csrfToken")?.value) || "";

  try{
    const res = await fetch("/api/admin/login/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf
      },
      body: JSON.stringify({ username, password })
    });

    const data = await res.json().catch(()=> ({}));
    if(!res.ok || !data.ok){
      alert(data.error || "Login impossible.");
      return;
    }

    await syncRoleFromBackend();
    renderAll();
    if(role === "admin") renderDashboard();

  }catch(e){
    alert("Erreur réseau.");
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
  // Admin/Revendeur n'a rien à faire ici
  if(role !== "visitor") return;

  // Non connecté -> passe par Auth d'abord
  if(!isAuthenticated){
    openAuthModal("reseller");
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

  // UI bouton
  const btn = byId("applyResellerBtn");
  if(!btn) return;

  if(role === "reseller"){
    btn.style.display = "none";
    return;
  }
  btn.style.display = "inline-flex";

  if(resellerStatus === "pending"){
    btn.textContent = "⏳ Demande en attente";
    btn.disabled = false; // tu peux laisser cliquable pour voir le statut
  }else if(resellerStatus === "approved"){
    btn.textContent = "✅ Revendeur approuvé (reconnecte)";
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

  const csrf = (byId("csrfToken")?.value) || "";

  const btn = byId("submitResellerBtn");
  const prev = btn.textContent;
  btn.disabled = true;
  btn.textContent = "Envoi...";

  try{
    const res = await fetch("/api/reseller/apply/", {
      method: "POST",
      headers: {
        "Content-Type":"application/json",
        "X-CSRFToken": csrf
      },
      body: JSON.stringify({ full_name, phone, city, shop_name, instagram, monthly_volume, message })
    });

    const data = await res.json().catch(()=>({}));
    if(!res.ok || !data.ok){
      showResellerNote(data.error || "Erreur. Réessaie.");
      return;
    }

    showResellerNote("✅ Demande envoyée. Statut: " + data.status);
    await refreshResellerStatus();

  }catch(e){
    showResellerNote("Erreur réseau.");
  }finally{
    btn.disabled = false;
    btn.textContent = prev;
  }
}

 

  // Events
  byId("loginBtn").addEventListener("click", ()=> openAuthModal(null));
  byId("logoutBtn").addEventListener("click", logout);
  byId("tabShop").addEventListener("click", ()=>goTab("shop"));
  byId("tabReseller").addEventListener("click", ()=>goTab("reseller"));
  byId("tabTrack").addEventListener("click", ()=>goTab("track"));
  byId("tabAdmin").addEventListener("click", ()=>goTab("admin"));

  byId("search").addEventListener("input", (e)=>{ query = e.target.value || ""; renderProducts(); });
  byId("brandFilter").addEventListener("change", (e)=>{ brand = e.target.value; renderProducts(); });
  byId("catFilter").addEventListener("change", (e)=>{ cat = e.target.value; renderProducts(); });

  byId("checkoutBtn").addEventListener("click", openCheckout);
  byId("openCheckoutBtn").addEventListener("click", openCheckout);
  byId("payNowBtn").addEventListener("click", payNow);
  byId("copyOrderBtn").addEventListener("click", copyOrderNo);

  byId("clearCartBtn").addEventListener("click", clearCart);
  byId("goTrackBtn").addEventListener("click", ()=>goTab("track"));

  byId("trackBtn").addEventListener("click", ()=>{
    const no = (byId("trackInput").value||"").trim();
    if(!no){ alert("Entre un numero."); return; }
    renderTrackingFromApi(no);
  });

  byId("pasteBtn").addEventListener("click", async ()=>{
    try{
      const t = await navigator.clipboard.readText();
      if(t) byId("trackInput").value = t.trim();
    }catch(e){ alert("Collage bloque."); }
  });
  byId("resetDemoBtn").addEventListener("click", resetDemo);

  byId("dashRange").addEventListener("change", ()=> renderDashboard());
  byId("refreshDashBtn").addEventListener("click", ()=> renderDashboard());
  byId("seedDemoBtn").addEventListener("click", seedDemoOrders);
  byId("exportCsvBtn").addEventListener("click", exportCsv);
  byId("refreshAdminBtn").addEventListener("click", renderDashboard);
  byId("ordersTable").addEventListener("click", async (e)=>{
  const btn = e.target.closest("[data-action='nextStatus']");
  if(!btn) return;

  const orderNo = btn.getAttribute("data-order");
  const next = btn.getAttribute("data-next");
  if(!orderNo || !next) { alert("Bouton mal formé (order/next manquant)."); return; }

  const csrf =
    (document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")) ||
    (byId("csrfToken")?.value) || "";

  try{
    const res = await fetch(`/api/admin/order/${encodeURIComponent(orderNo)}/status/`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf
      },
      body: JSON.stringify({status: next})
    });

    const text = await res.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch(_) {}

    if(!res.ok || !data.ok){
      alert(`Erreur ${res.status} : ${data.error || text.slice(0,200) || "update statut"}`);
      return;
    }

    await renderDashboard();
  }catch(err){
    alert("Erreur réseau.");
  }
});

byId("stockTable").addEventListener("click", async (e)=>{
  const btn = e.target.closest("[data-action='stockAdj']");
  if(!btn) return;

  const sku = btn.getAttribute("data-sku");
  const size = btn.getAttribute("data-size");
  const delta = Number(btn.getAttribute("data-delta"));

  const csrf =
    (document.querySelector('meta[name="csrf-token"]')?.getAttribute("content")) ||
    (byId("csrfToken")?.value) || "";

  try{
    const res = await fetch("/api/admin/inventory/adjust/", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRFToken": csrf
      },
      body: JSON.stringify({sku, size, delta})
    });

    const data = await res.json().catch(()=> ({}));
    if(!res.ok || !data.ok){
      alert(data.error || "Erreur stock.");
      return;
    }

    // refresh inventory + produits (stock boutique)
    await renderInventory();
    await loadProductsFromApi();
    renderProducts();
    renderProductDetail();

  }catch(err){
    alert("Erreur réseau.");
  }
});

  byId("deleteAllBtn").addEventListener("click", deleteAllOrders);

async function syncRoleFromBackend(){
  try{
    const res = await fetch("/api/admin/me/");
    const data = await res.json().catch(()=> ({}));

    isAuthenticated = !!data.authenticated;
    currentUser = data.username || null;

    if(isAuthenticated){
      role = data.role || "visitor";
      byId("roleLabel").textContent = role;
      byId("loginBtn").style.display = "none";
      byId("logoutBtn").style.display = "inline-flex";
    }else{
      role = "visitor";
      byId("roleLabel").textContent = "Visiteur";
      byId("loginBtn").style.display = "inline-flex";
      byId("logoutBtn").style.display = "none";
    }

    mode = (role === "reseller") ? "reseller" : "retail";
    syncRoleUI();
  }catch(e){
    // si l'API tombe, on reste en visitor
    isAuthenticated = false;
    currentUser = null;
    role = "visitor";
    mode = "retail";
    syncRoleUI();
  }
}byId("applyResellerBtn").addEventListener("click", async ()=>{
  if(role !== "visitor") return;

  // pas connecté -> login / création compte
  if(!isAuthenticated){
    openAuthModal("reseller");
    return;
  }

  await refreshResellerStatus();

  // Si jamais tu n'as encore rien soumis -> montre d'abord les conditions
  if(resellerStatus === "none"){
    openResellerTerms();
    return;
  }

  // Sinon, on affiche le statut dans le modal
  if(resellerStatus === "pending") showResellerNote("⏳ Ta demande est en attente de validation.");
  else if(resellerStatus === "approved") showResellerNote("✅ Demande approuvée. Si ton rôle n'a pas changé, fais Logout puis Login.");
  else if(resellerStatus === "rejected") showResellerNote("❌ Refusé. Tu peux corriger et renvoyer.");
  else byId("resellerStatusNote").style.display = "none";

  openResellerModal();
});

byId("closeResellerModalBtn").addEventListener("click", closeResellerModal);
byId("cancelResellerBtn").addEventListener("click", closeResellerModal);
byId("submitResellerBtn").addEventListener("click", submitResellerApplication);

// fermer en cliquant sur l’overlay
byId("resellerModal").addEventListener("click", (e)=>{
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
  openResellerModal();
});

// Auth modal events
byId("closeAuthModalBtn")?.addEventListener("click", closeAuthModal);
byId("authCancelBtn")?.addEventListener("click", closeAuthModal);
byId("authTabLogin")?.addEventListener("click", ()=> setAuthMode("login"));
byId("authTabRegister")?.addEventListener("click", ()=> setAuthMode("register"));
byId("authSubmitBtn")?.addEventListener("click", submitAuth);

// Enter key submits in auth modal
["authLoginUsername","authLoginPassword","authRegUsername","authRegEmail","authRegPassword1","authRegPassword2"].forEach(id=>{
  const el = byId(id);
  if(!el) return;
  el.addEventListener("keydown", (e)=>{
    if(e.key === "Enter"){ e.preventDefault(); submitAuth(); }
  });
});
