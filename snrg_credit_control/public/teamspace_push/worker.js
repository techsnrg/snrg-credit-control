/* Scoped only to this asset directory; does not replace Desk's service worker. */
self.addEventListener('install', event => event.waitUntil(self.skipWaiting()));
self.addEventListener('activate', event => event.waitUntil(clients.claim()));
const line = (value, fallback, limit) => typeof value === 'string' && value.trim() ? value.replace(/\s+/g,' ').trim().slice(0,limit) : fallback;
function destination(value) {
  try {
    const url = new URL(typeof value === 'string' ? value : '/teamspace', self.location.origin);
    if (url.origin === self.location.origin && (url.pathname === '/teamspace' || url.pathname.startsWith('/desk/customer-interaction/'))) return url.pathname + url.search;
  } catch (_) { /* Invalid or external destinations fall back to Teamspace. */ }
  return '/teamspace';
}
self.addEventListener('push', event => {
  let payload = {};
  try { payload = event.data?.json() || {}; } catch (_) { /* Readable safe fallback. */ }
  event.waitUntil(self.registration.showNotification(line(payload.title, 'Teamspace update', 120), {
    body: line(payload.body, 'Open Teamspace to view this update.', 280),
    icon: '/assets/snrg_credit_control/images/teamspace.svg',
    tag: line(payload.tag, 'teamspace', 160),
    data: {url: destination(payload.url)},
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow(destination(event.notification.data?.url)));
});
