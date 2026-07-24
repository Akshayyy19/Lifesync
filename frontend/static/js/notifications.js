/**
 * LifeSync — notifications.js
 * Purely cosmetic: fades a notification out before the "mark as read"
 * link is followed. If JS is disabled the link still works instantly.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-mark-read-link]').forEach(function (link) {
      link.addEventListener('click', function (event) {
        const item = link.closest('.notification-item');
        if (!item) return;
        event.preventDefault();
        item.style.transition = 'opacity .25s ease';
        item.style.opacity = '0.35';
        setTimeout(function () { window.location.href = link.href; }, 180);
      });
    });
  });
})();
