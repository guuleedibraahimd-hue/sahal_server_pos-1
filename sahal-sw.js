/* Sahal Server — push notification service worker.
   Shows a system notification for every push (new order, food ready,
   staff chat) even when no Sahal tab is open. Served at /sahal-sw.js. */
self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (e) => e.waitUntil(self.clients.claim()));

self.addEventListener("push", (event) => {
    let d = {};
    try { d = event.data ? event.data.json() : {}; } catch (e) { d = { title: "Sahal Server", body: event.data ? event.data.text() : "" }; }
    const title = d.title || "Sahal Server";
    const opts = {
        body: d.body || "",
        icon: d.icon || "/static/logo.png",
        badge: "/static/logo.png",
        image: d.image || undefined,
        tag: d.tag || "sahal",
        renotify: true,
        requireInteraction: !!d.sticky,
        vibrate: d.kind === "order" ? [300, 120, 300, 120, 400] : [150, 80, 150],
        data: { url: d.url || "/" },
        timestamp: Date.now()
    };
    event.waitUntil(self.registration.showNotification(title, opts));
});

self.addEventListener("notificationclick", (event) => {
    event.notification.close();
    const url = (event.notification.data && event.notification.data.url) || "/";
    event.waitUntil((async () => {
        const all = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
        for (const c of all) {
            try {
                const u = new URL(c.url);
                if (u.pathname === new URL(url, self.location.origin).pathname) { await c.focus(); return; }
            } catch (e) {}
        }
        await self.clients.openWindow(url);
    })());
});
