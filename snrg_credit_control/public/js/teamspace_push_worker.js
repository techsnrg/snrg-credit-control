/* Scoped only to this asset directory; does not replace Desk's service worker. */
self.addEventListener('push', event => {
  let payload = {};
  try { payload = event.data?.json() || {}; } catch (_) { /* Generic safe fallback. */ }
  event.waitUntil(self.registration.showNotification('Teamspace', {
    body: 'You have a new Teamspace update.',
    icon: '/assets/snrg_credit_control/images/teamspace.svg',
    tag: typeof payload.tag === 'string' ? payload.tag : 'teamspace',
    data: {url: '/teamspace'},
  }));
});
self.addEventListener('notificationclick', event => {
  event.notification.close();
  event.waitUntil(clients.openWindow('/teamspace'));
});
