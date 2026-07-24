/**
 * LifeSync — calendar.js
 * Lets users toggle which categories show on the month grid without a
 * page reload. Purely a display filter — every chip stays in the DOM.
 */
(function () {
  'use strict';

  document.addEventListener('DOMContentLoaded', function () {
    const table = document.querySelector('.calendar-table');
    const buttons = document.querySelectorAll('[data-calendar-filter]');
    if (!table || !buttons.length) return;

    buttons.forEach(function (button) {
      button.addEventListener('click', function () {
        const filter = button.dataset.calendarFilter;
        table.setAttribute('data-active-filter', filter);

        buttons.forEach(function (b) { b.classList.remove('active'); });
        button.classList.add('active');

        table.querySelectorAll('.mini-chip').forEach(function (chip) {
          const show = filter === 'all' || chip.dataset.category === filter;
          chip.style.display = show ? '' : 'none';
        });
      });
    });
  });
})();
