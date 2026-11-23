/* =========================================================
   SAHAL APP LAYER — shared by every restaurant portal.
   Include once:  <script src="/static/sahal_app.js" defer></script>
   Configure on <body>:
     data-rid="…"                restaurant id
     data-role="cashier|waiter|admin|kitchen"   (for notifications)
     data-nav=".sidebar .sb-link"  sidebar items to mirror on phones
     data-nav-logout="a.logout"   optional logout link
     data-nav-primary="dashboard,neworder,orders"  optional: which go in the bar
     data-accent="#2f6fed"        optional colour
   ========================================================= */
(function(){
    "use strict";
    const body = document.body;
    const RID = body.dataset.rid || "";
    const ROLE = body.dataset.role || "";
    const MOBILE_Q = window.matchMedia("(max-width: 860px)");
    const LS = {
        get(k, d){ try{ const v = localStorage.getItem(k); return v === null ? d : v; }catch(e){ return d; } },
        set(k, v){ try{ localStorage.setItem(k, v); }catch(e){} }
    };
    document.documentElement.classList.add("sa-root");

    // Tell the server which portal this page is (a waiter and a cashier can
    // be logged in side by side in the same browser).
    if(ROLE === "waiter" || ROLE === "cashier"){
        const _fetch = window.fetch.bind(window);
        window.fetch = function(input, init){
            try{
                const url = typeof input === "string" ? input : (input && input.url) || "";
                if(url.startsWith("/") || url.startsWith(location.origin)){
                    init = Object.assign({}, init || {});
                    const h = new Headers(init.headers || (typeof input !== "string" && input.headers) || {});
                    if(!h.has("X-Sahal-Role")) h.set("X-Sahal-Role", ROLE);
                    init.headers = h;
                }
            }catch(e){}
            return _fetch(input, init);
        };
    }
    if(body.dataset.accent) document.documentElement.style.setProperty("--sa-accent", body.dataset.accent);

    /* =====================================================
       🔊 SOUNDS — real audio files, decoded once, played via
       WebAudio (loud + instant). Browsers only allow sound after
       the first tap on the page, so we unlock on any tap.
       ===================================================== */
    const SV = "v3";
    const SOUND_URLS = { order: "/static/sounds/new_order.wav?" + SV, ready: "/static/sounds/ready.wav?" + SV, chat: "/static/sounds/chat.wav?" + SV };
    let ctx = null; const buffers = {}; let unlocked = false;
    function soundOn(){ return LS.get("sa_sound", "on") !== "off"; }
    function ensureCtx(){
        if(!ctx){ try{ ctx = new (window.AudioContext || window.webkitAudioContext)(); }catch(e){ return null; } }
        if(ctx.state === "suspended") ctx.resume().catch(() => {});
        return ctx;
    }
    function loadSounds(){
        const c = ensureCtx(); if(!c) return;
        Object.entries(SOUND_URLS).forEach(([k, url]) => {
            if(buffers[k]) return;
            fetch(url).then(r => r.arrayBuffer()).then(a => new Promise((res, rej) => c.decodeAudioData(a, res, rej)))
                .then(b => { buffers[k] = b; }).catch(() => {});
        });
    }
    function unlock(){
        if(unlocked) return; unlocked = true;
        ensureCtx(); loadSounds();
        // play a silent blip so iOS fully unlocks
        try{ const c = ctx, b = c.createBuffer(1, 1, 22050), s = c.createBufferSource(); s.buffer = b; s.connect(c.destination); s.start(0); }catch(e){}
    }
    ["pointerdown", "touchstart", "keydown", "click"].forEach(ev => document.addEventListener(ev, unlock, { passive:true }));

    // LOUD: the sound is amplified (x2.6) through a limiter, so it is much
    // louder than a normal web sound but never distorts/crackles.
    let master = null;
    function out(c){
        if(master) return master;
        const comp = c.createDynamicsCompressor();
        comp.threshold.value = -12; comp.knee.value = 6; comp.ratio.value = 14; comp.attack.value = 0.002; comp.release.value = 0.2;
        const g = c.createGain(); g.gain.value = 2.6;
        g.connect(comp); comp.connect(c.destination);
        master = g; return master;
    }
    function play(name){
        if(!soundOn()) return;
        const c = ensureCtx();
        if(c && buffers[name]){
            try{
                const src = c.createBufferSource();
                src.buffer = buffers[name]; src.connect(out(c)); src.start(0);
                return;
            }catch(e){}
        }
        try{ const a = new Audio(SOUND_URLS[name] || SOUND_URLS.order); a.volume = 1; a.play().catch(() => {}); }catch(e){}
    }
    // New orders keep ringing (3×) until someone taps the screen / the alert.
    let ringTimer = null, ringLeft = 0;
    function stopRing(){ clearInterval(ringTimer); ringTimer = null; ringLeft = 0; }
    function ring(){
        stopRing(); play("order"); ringLeft = 2;
        ringTimer = setInterval(() => { if(ringLeft-- <= 0){ stopRing(); return; } play("order"); }, 3200);
    }
    ["pointerdown", "keydown"].forEach(ev => document.addEventListener(ev, () => { if(ringTimer) stopRing(); }, { passive:true }));

    /* =====================================================
       🔔 BANNER ALERTS
       ===================================================== */
    let bannerEl = null, bannerTimer = null, titleTimer = null;
    const baseTitle = document.title;
    function banner(kind, icon, title, text, onClick){
        if(!bannerEl){
            bannerEl = document.createElement("div");
            bannerEl.className = "sa-banner";
            bannerEl.innerHTML = '<div class="sa-bi"></div><div><div class="sa-bt"></div><div class="sa-bb"></div></div><div class="sa-bx">✕</div>';
            document.body.appendChild(bannerEl);
        }
        bannerEl.className = "sa-banner " + (kind || "");
        bannerEl.querySelector(".sa-bi").textContent = icon || "🔔";
        bannerEl.querySelector(".sa-bt").textContent = title || "";
        bannerEl.querySelector(".sa-bb").textContent = text || "";
        bannerEl.onclick = () => { bannerEl.classList.remove("show"); if(onClick) onClick(); };
        void bannerEl.offsetWidth;
        bannerEl.classList.add("show");
        clearTimeout(bannerTimer); bannerTimer = setTimeout(() => bannerEl.classList.remove("show"), 7000);
        // flash the tab title
        clearInterval(titleTimer); let n = 0;
        titleTimer = setInterval(() => { document.title = (n++ % 2) ? baseTitle : ("🔔 " + title); if(n > 9){ clearInterval(titleTimer); document.title = baseTitle; } }, 900);
    }
    function localNotify(title, text, tag){
        // Only when the page is in the background AND web push isn't
        // delivering for this device (otherwise the user would get two).
        if(!document.hidden || pushActive) return;
        if(!("Notification" in window) || Notification.permission !== "granted") return;
        try{ new Notification(title, { body: text, icon: "/static/logo.png", tag: tag || "sahal", renotify: true }); }catch(e){}
    }
    function vibrate(p){ try{ if(navigator.vibrate) navigator.vibrate(p); }catch(e){} }

    /* =====================================================
       📲 WEB PUSH — notifications even when the browser /
       app is closed (Android, Windows, Mac; iPhone after
       "Add to Home Screen").
       ===================================================== */
    let pushActive = false;
    function b64ToUint8(b64){
        const pad = "=".repeat((4 - b64.length % 4) % 4);
        const raw = atob((b64 + pad).replace(/-/g, "+").replace(/_/g, "/"));
        return Uint8Array.from([...raw].map(c => c.charCodeAt(0)));
    }
    async function getReg(){
        if(!("serviceWorker" in navigator)) return null;
        try{ return await navigator.serviceWorker.register("/sahal-sw.js", { scope: "/sahal-push/" }); }catch(e){ return null; }
    }
    let pushError = "";
    async function subscribePush(){
        pushError = "";
        if(!RID){ pushError = "no-rid"; return false; }
        if(!("serviceWorker" in navigator) || !("PushManager" in window)){ pushError = "Browser-kan push ma taageero (iPhone: Add to Home Screen kadib app-ka ka fur)."; return false; }
        if(Notification.permission !== "granted"){ pushError = "permission"; return false; }
        const reg = await getReg(); if(!reg){ pushError = "Service worker (/sahal-sw.js) lama helin — hubi in static/sahal-sw.js la upload gareeyay."; return false; }
        try{
            // NOTE: navigator.serviceWorker.ready only resolves for a worker that
            // controls THIS page — ours lives at /sahal-push/, so wait for it directly.
            if(!reg.active){
                const sw = reg.installing || reg.waiting;
                if(sw) await new Promise((res) => {
                    if(sw.state === "activated") return res();
                    sw.addEventListener("statechange", () => { if(sw.state === "activated") res(); });
                    setTimeout(res, 8000);
                });
            }
            let sub = await reg.pushManager.getSubscription();
            if(!sub){
                const k = await fetch("/api/push/vapid").then(r => r.json()).catch(() => ({}));
                if(!k.success){ pushError = "Server-ka: pywebpush kuma rakibna (ku dar requirements.txt kadib redeploy)."; return false; }
                sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: b64ToUint8(k.public_key) });
            }
            const r = await fetch(`/api/push/subscribe/${encodeURIComponent(RID)}`, {
                method: "POST", headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ subscription: sub.toJSON(), role: ROLE })
            }).then(r => r.json()).catch(() => ({}));
            pushActive = !!r.success;
            if(!pushActive) pushError = r.error || "Server-ka ma diiwaan gelin qalabkan.";
            return pushActive;
        }catch(e){
            const m = String(e && e.message || e);
            pushError = /permission denied|incognito|private/i.test(m)
                ? "Incognito / Private window-ka push kuma shaqeeyo — ka fur Chrome caadi ah (ama app-ka la rakibay)."
                : "Push subscribe failed: " + m;
            return false;
        }
    }
    async function enableNotifications(){
        unlock();
        if(!("Notification" in window)){ alert("Browser-kan notifications ma taageero. Isticmaal Chrome."); return false; }
        let perm = Notification.permission;
        if(perm === "default"){
            try{
                perm = await new Promise((res) => {
                    const r = Notification.requestPermission(res);   // old Safari uses the callback
                    if(r && r.then) r.then(res);
                });
            }catch(e){}
        }
        if(perm !== "granted"){
            alert(perm === "denied"
                ? "Notifications waa la xiray (Blocked).\n\nKombuyuutar: riix 🔒 ama 🔕 (bidixda/midigta URL-ka) → Notifications → Allow, kadib refresh.\nAndroid: ⋮ → Settings → Site settings → Notifications → Allow."
                : "Browser-ku ma soo bandhigin su'aasha 'Allow'.\n\nRiix calaamadda 🔕 ama 🔒 ee ku taal URL-ka (address bar) → Notifications → Allow, kadib refresh bogga.");
            refreshNotifyButtons();
            return false;
        }
        LS.set("sa_notify", "on");
        const ok = await Promise.race([subscribePush(), new Promise(r => setTimeout(() => { pushError = pushError || "Push service-ka ma jawaabin (internet?)"; r(false); }, 15000))]);
        hideEnable();
        renderSheetExtras(); refreshNotifyButtons();
        if(!ok && pushError && pushError !== "permission"){
            banner("chat", "⚠️", "Notifications: qalabkan waa shidan yahay", "Laakiin marka browser-ku xiran yahay ma iman doonaan: " + pushError);
            return true;
        }
        return true;
    }
    function notifyState(){
        if(!("Notification" in window)) return "unsupported";
        if(Notification.permission === "denied") return "blocked";
        if(Notification.permission === "granted" && LS.get("sa_notify", "on") !== "off") return "on";
        return "off";
    }
    function refreshNotifyButtons(){
        const st = notifyState();
        document.querySelectorAll("[data-sa-notify]").forEach(b => {
            b.classList.toggle("on", st === "on");
            b.classList.toggle("blocked", st === "blocked");
            const lbl = { on: "Notifications ON", off: "Shid Notifications", blocked: "Notifications Blocked", unsupported: "No Notifications" }[st];
            b.innerHTML = `<span class="sa-n-ic">${st === "on" ? "🔔" : "🔕"}</span><span class="sa-n-lb">${lbl}</span>`;
            b.title = lbl;
        });
    }
    async function onNotifyButton(){
        unlock();
        const st = notifyState();
        if(st === "unsupported"){ alert("Browser-kan notifications ma taageero. Isticmaal Google Chrome (iPhone: Safari → Share → Add to Home Screen, kadib app-ka ka fur)."); return; }
        if(st === "blocked"){
            alert("Notifications waa la xiray (Blocked).\n\nSi aad u furto:\n• Kombuyuutar: riix 🔒 (bidixda URL-ka) → Notifications → Allow, kadib refresh.\n• Android Chrome: ⋮ → Settings → Site settings → Notifications → sahalserver.com → Allow.\n• iPhone: Settings → Notifications → app-ka → Allow.");
            return;
        }
        if(st === "on"){
            if(confirm("Ma rabtaa inaad damiso notifications-ka qalabkan?")) await disableNotifications();
        } else {
            document.querySelectorAll("[data-sa-notify]").forEach(b => { b.innerHTML = '<span class="sa-n-ic">⏳</span><span class="sa-n-lb">Shidaya…</span>'; });
            const ok = await enableNotifications();
            if(ok && pushActive){ banner("ready", "🔔", "Notifications waa shidan yihiin ✅", "Dalab cusub, diyaar iyo chat ayaa kuu imaanaya xitaa marka browser-ku xiran yahay"); play("ready"); }
        }
        refreshNotifyButtons();
    }
    document.addEventListener("click", (e) => {
        const b = e.target.closest && e.target.closest("[data-sa-notify]");
        if(b){ e.preventDefault(); onNotifyButton(); }
    });

    async function disableNotifications(){
        LS.set("sa_notify", "off");
        try{
            const reg = await navigator.serviceWorker.getRegistration("/sahal-push/");
            const sub = reg && await reg.pushManager.getSubscription();
            if(sub){
                await fetch(`/api/push/unsubscribe/${encodeURIComponent(RID)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ endpoint: sub.endpoint }) }).catch(() => {});
                await sub.unsubscribe();
            }
        }catch(e){}
        pushActive = false; renderSheetExtras(); refreshNotifyButtons();
    }

    // "Turn on sound & notifications" pill (once per device until accepted/dismissed)
    let enableEl = null;
    function showEnable(){
        if(enableEl || !RID) return;
        if(LS.get("sa_enable_dismissed", "") === "1") return;
        if("Notification" in window && Notification.permission === "granted") return;
        enableEl = document.createElement("button");
        enableEl.className = "sa-enable";
        enableEl.innerHTML = '🔔 Shid cod-ka &amp; notifications <span class="sa-x" title="Close">✕</span>';
        enableEl.addEventListener("click", (e) => {
            if(e.target.classList.contains("sa-x")){ LS.set("sa_enable_dismissed", "1"); hideEnable(); return; }
            enableNotifications();
        });
        document.body.appendChild(enableEl);
    }
    function hideEnable(){ if(enableEl){ enableEl.remove(); enableEl = null; } }

    /* =====================================================
       📱 BOTTOM NAVIGATION — mirrors the sidebar on phones.
       The first items go in the bar; the rest in "More".
       ===================================================== */
    const navSel = body.dataset.nav || "";
    const logoutSel = body.dataset.navLogout || "";
    const primaryKeys = (body.dataset.navPrimary || "").split(",").map(s => s.trim()).filter(Boolean);
    let barEl = null, sheetEl = null, sheetBg = null, extrasEl = null;

    function navItems(){
        if(!navSel) return [];
        const seen = new Set();
        return Array.from(document.querySelectorAll(navSel)).filter(el => {
            const key = keyOf(el);
            if(seen.has(key)) return false; seen.add(key); return true;
        });
    }
    function keyOf(el){ return el.dataset.page || el.dataset.saKey || el.getAttribute("href") || labelOf(el); }
    function labelOf(el){
        if(el.dataset.saLabel) return el.dataset.saLabel;
        const c = el.cloneNode(true);
        c.querySelectorAll(".badge, .sa-badge, svg, .icon").forEach(n => n.remove());
        let t = c.textContent.replace(/\s+/g, " ").trim();
        t = t.replace(/^[^\p{L}\p{N}]+/u, "").trim();
        return t || "Menu";
    }
    function iconOf(el){
        if(el.dataset.saIcon) return el.dataset.saIcon;
        const svg = el.querySelector("svg");
        if(svg) return svg.outerHTML;
        const ic = el.querySelector(".icon, .ic");
        if(ic && ic.textContent.trim()) return ic.textContent.trim();
        const m = el.textContent.trim().match(/^[^\p{L}\p{N}\s]+/u);
        return m ? m[0] : "•";
    }
    function badgeOf(el){
        const b = el.querySelector(".badge, [data-sa-badge]");
        const t = b ? b.textContent.trim() : "";
        return t && t !== "0" ? t : "";
    }
    function isActive(el){ return el.classList.contains("active"); }

    function buildNav(){
        const items = navItems();
        if(!items.length){ body.classList.remove("sa-mobile"); return; }
        let primary = [];
        if(primaryKeys.length){
            primaryKeys.forEach(k => { const it = items.find(i => keyOf(i) === k || (i.dataset.page === k)); if(it) primary.push(it); });
        }
        if(!primary.length) primary = items.slice(0, items.length <= 5 ? 5 : 4);
        if(items.length > 5 && primary.length > 4) primary = primary.slice(0, 4);
        const rest = items.filter(i => !primary.includes(i));
        const needMore = rest.length > 0 || true;   // "More" always holds settings (sound, notifications, install, logout)

        if(!barEl){
            barEl = document.createElement("nav");
            barEl.className = "sa-bottom-nav";
            document.body.appendChild(barEl);
        }
        barEl.innerHTML = "";
        primary.forEach(el => barEl.appendChild(tabFor(el, "sa-tab")));
        if(needMore){
            const more = document.createElement("button");
            more.type = "button"; more.className = "sa-tab" + (rest.some(isActive) ? " active" : "");
            const totalBadge = rest.reduce((s, el) => s + (parseInt(badgeOf(el)) || 0), 0);
            more.innerHTML = `<span class="sa-ic">☰</span><span class="sa-lb">More</span>${totalBadge ? `<span class="sa-badge">${totalBadge}</span>` : ""}`;
            more.addEventListener("click", openSheet);
            barEl.appendChild(more);
        }
        buildSheet(rest);
    }
    function tabFor(el, cls){
        const b = document.createElement(el.tagName === "A" && el.getAttribute("href") && !el.getAttribute("href").startsWith("#") && !el.onclick ? "a" : "button");
        if(b.tagName === "A"){ b.href = el.getAttribute("href"); if(el.target) b.target = el.target; }
        else b.type = "button";
        b.className = cls + (isActive(el) ? " active" : "");
        const badge = badgeOf(el);
        b.innerHTML = `<span class="sa-ic">${iconOf(el)}</span><span class="sa-lb"></span>${badge ? `<span class="sa-badge">${badge}</span>` : ""}`;
        b.querySelector(".sa-lb").textContent = labelOf(el);
        if(b.tagName !== "A"){
            b.addEventListener("click", (e) => { e.preventDefault(); closeSheet(); el.click(); setTimeout(syncActive, 30); });
        } else {
            b.addEventListener("click", () => closeSheet());
        }
        b._src = el;
        return b;
    }
    function buildSheet(rest){
        if(!sheetEl){
            sheetBg = document.createElement("div"); sheetBg.className = "sa-sheet-bg"; sheetBg.addEventListener("click", closeSheet);
            sheetEl = document.createElement("div"); sheetEl.className = "sa-sheet";
            document.body.appendChild(sheetBg); document.body.appendChild(sheetEl);
        }
        sheetEl.innerHTML = '<div class="sa-grip"></div>';
        if(rest.length){
            const h = document.createElement("h4"); h.textContent = "Menu"; sheetEl.appendChild(h);
            const g = document.createElement("div"); g.className = "sa-grid";
            rest.forEach(el => g.appendChild(tabFor(el, "sa-gi")));
            sheetEl.appendChild(g);
        }
        const h2 = document.createElement("h4"); h2.textContent = "Settings"; sheetEl.appendChild(h2);
        extrasEl = document.createElement("div"); sheetEl.appendChild(extrasEl);
        renderSheetExtras();
    }
    let deferredInstall = null;
    window.addEventListener("beforeinstallprompt", (e) => { e.preventDefault(); deferredInstall = e; renderSheetExtras(); });
    function renderSheetExtras(){
        if(!extrasEl) return;
        extrasEl.innerHTML = "";
        const add = (html, fn, cls) => {
            const b = document.createElement("button"); b.type = "button"; b.className = "sa-row " + (cls || "");
            b.innerHTML = html; b.addEventListener("click", fn); extrasEl.appendChild(b);
        };
        add(`🔊 Cod-ka (sound)<span class="sa-sub">${soundOn() ? "ON" : "OFF"}</span>`, () => {
            LS.set("sa_sound", soundOn() ? "off" : "on"); unlock(); if(soundOn()) play("order"); renderSheetExtras();
        });
        const granted = ("Notification" in window) && Notification.permission === "granted";
        const notifOn = granted && LS.get("sa_notify", "on") !== "off";
        add(`🔔 Notifications<span class="sa-sub">${notifOn ? "ON" : "OFF"}</span>`, () => { notifOn ? disableNotifications() : enableNotifications(); });
        add(`🧪 Tijaabi alert-ka<span class="sa-sub">Test</span>`, () => { unlock(); closeSheet(); SahalApp.newOrderAlert("Test: Table 1", "1× Shaah — sidaan ayuu dalab cusub u imaanayaa"); });
        if(deferredInstall){
            add(`📲 Install App<span class="sa-sub">Home screen</span>`, async () => { deferredInstall.prompt(); try{ await deferredInstall.userChoice; }catch(e){} deferredInstall = null; renderSheetExtras(); });
        } else if(/iphone|ipad/i.test(navigator.userAgent) && !navigator.standalone){
            add(`📲 Install App<span class="sa-sub">Share → Add to Home Screen</span>`, () => alert("iPhone: Safari ku fur, riix Share (□↑) → 'Add to Home Screen'. Kadib notifications-ku way shaqaynayaan."));
        }
        const lo = logoutSel ? document.querySelector(logoutSel) : null;
        if(lo){
            add(`🚪 Logout`, () => { if(lo.href) location.href = lo.href; else lo.click(); }, "danger");
        }
    }
    function openSheet(){ if(!sheetEl) return; renderSheetExtras(); sheetBg.classList.add("open"); sheetEl.classList.add("open"); }
    function closeSheet(){ if(!sheetEl) return; sheetBg.classList.remove("open"); sheetEl.classList.remove("open"); }

    function syncActive(){ if(body.classList.contains("sa-mobile")) buildNav(); }
    let rebuildT = null;
    function scheduleRebuild(){ clearTimeout(rebuildT); rebuildT = setTimeout(syncActive, 60); }

    function applyMode(){
        const mobile = MOBILE_Q.matches && !!navSel;
        body.classList.toggle("sa-mobile", mobile);
        if(mobile) buildNav();
        else closeSheet();
    }
    if(MOBILE_Q.addEventListener) MOBILE_Q.addEventListener("change", applyMode); else MOBILE_Q.addListener(applyMode);

    // keep the bar in sync when the page swaps badges / active states
    const mo = new MutationObserver((muts) => {
        for(const m of muts){
            const t = m.target.nodeType === 1 ? m.target : m.target.parentElement;
            if(!t) continue;
            if(t.closest && (t.closest(".sa-bottom-nav") || t.closest(".sa-sheet") || t.closest(".sa-banner"))) continue;
            if(navSel && (t.matches(navSel) || t.closest(navSel) || t.querySelector && t.querySelector(navSel))){ scheduleRebuild(); return; }
        }
    });

    /* =====================================================
       💬 STAFF CHAT unread badge on any [data-chat-link]
       ===================================================== */
    let chatV = null;
    function chatLastRead(){ return LS.get(`sa_chat_read_${RID}`, ""); }
    async function checkChat(){
        const links = document.querySelectorAll("[data-chat-link]");
        if(!links.length || !RID) return;
        try{
            const d = await fetch(`/api/chat/${encodeURIComponent(RID)}/unread?as=${encodeURIComponent(ROLE)}&since=${encodeURIComponent(chatLastRead())}`, { cache: "no-store" }).then(r => r.json());
            if(!d.success) return;
            if(!chatLastRead() && d.server_now){ LS.set(`sa_chat_read_${RID}`, d.server_now); }
            links.forEach(l => {
                let b = l.querySelector("[data-sa-badge]");
                if(d.unread > 0){
                    if(!b){ b = document.createElement("span"); b.className = "badge"; b.setAttribute("data-sa-badge", ""); b.style.cssText = "margin-left:auto;background:#ef4444;color:#fff;font-size:10px;font-weight:800;padding:2px 7px;border-radius:10px;"; l.appendChild(b); }
                    b.textContent = d.unread > 99 ? "99+" : d.unread;
                } else if(b){ b.remove(); }
            });
            if(chatV !== null && d.v !== chatV && d.last && d.last.mine === false && d.unread > 0){
                play("chat"); vibrate(80);
                banner("chat", "💬", d.last.sender || "Staff Chat", d.last.preview || "", () => { const l = links[0]; if(l) l.click(); });
                localNotify("💬 " + (d.last.sender || "Staff Chat"), d.last.preview || "", "chat");
            }
            chatV = d.v;
        }catch(e){}
    }

    /* =====================================================
       PUBLIC API
       ===================================================== */
    window.SahalApp = {
        play, banner, unlock, enableNotifications, disableNotifications,
        newOrderAlert(title, text, onClick){
            ring(); vibrate([300, 120, 300, 120, 500]);
            banner("", "🔔", title || "Dalab cusub!", text || "", () => { stopRing(); if(onClick) onClick(); });
            localNotify("🔔 " + (title || "Dalab cusub!"), text || "", "order");
        },
        readyAlert(title, text){
            play("ready"); vibrate([120, 60, 120]);
            banner("ready", "✅", title || "Diyaar!", text || "");
            localNotify("✅ " + (title || "Diyaar!"), text || "", "ready");
        },
        chatRead(){ LS.set(`sa_chat_read_${RID}`, new Date().toISOString()); checkChat(); },
        refreshNav: syncActive
    };

    let inited = false;
    document.addEventListener("DOMContentLoaded", init);
    if(document.readyState !== "loading") init();
    function init(){
        if(inited) return; inited = true;
        applyMode();
        refreshNotifyButtons();
        mo.observe(document.body, { subtree: true, childList: true, attributes: true, attributeFilter: ["class"], characterData: true });
        if(RID){
            setTimeout(showEnable, 1500);
            if(("Notification" in window) && Notification.permission === "granted" && LS.get("sa_notify", "on") !== "off") subscribePush();
            if(document.querySelector("[data-chat-link]")){ checkChat(); setInterval(checkChat, 4000); }
        }
    }
})();
