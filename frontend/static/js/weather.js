/**
 * LifeSync — weather.js
 * Animates the small inline sky scene on the weather page so a searched
 * city's condition is visible at a glance, not just described in text.
 * Reuses the same .sky-* CSS classes as the header (see theme.js/style.css).
 */
(function () {
  'use strict';

  function rand(min, max) {
    return Math.random() * (max - min) + min;
  }

  function el(className, styles) {
    const node = document.createElement('div');
    node.className = className;
    Object.assign(node.style, styles || {});
    return node;
  }

  function populate(scene) {
    const condition = (scene.dataset.condition || 'sunny').toLowerCase();
    const isDay = scene.dataset.isDay !== 'false';

    if (isDay) {
      scene.appendChild(el('sky-sun', { width: '46px', height: '46px', top: '12%', right: '10%' }));
    } else {
      scene.appendChild(el('sky-moon', { width: '34px', height: '34px', top: '14%', right: '12%' }));
      for (let i = 0; i < 18; i++) {
        scene.appendChild(el('sky-star', {
          left: rand(2, 98) + '%', top: rand(4, 80) + '%',
          animationDelay: rand(0, 3) + 's',
        }));
      }
    }

    const cloudCount = { cloudy: 4, rainy: 3, thunderstorm: 3, snowy: 2, misty: 5 }[condition] || 1;
    for (let i = 0; i < cloudCount; i++) {
      const width = rand(50, 100);
      scene.appendChild(el('sky-cloud', {
        width: width + 'px', height: (width * 0.4) + 'px',
        top: rand(10, 55) + '%', left: rand(-10, 85) + '%',
        animationDuration: rand(30, 55) + 's',
        animationDelay: '-' + rand(0, 30) + 's',
      }));
    }

    if (condition === 'rainy' || condition === 'thunderstorm') {
      for (let i = 0; i < 35; i++) {
        scene.appendChild(el('sky-raindrop', {
          left: rand(0, 100) + '%',
          animationDuration: rand(0.5, 0.9) + 's',
          animationDelay: rand(0, 1.5) + 's',
        }));
      }
    }

    if (condition === 'snowy') {
      for (let i = 0; i < 25; i++) {
        scene.appendChild(el('sky-snowflake', {
          left: rand(0, 100) + '%',
          animationDuration: rand(4, 7) + 's',
          animationDelay: rand(0, 4) + 's',
        }));
      }
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.sky-scene-inline').forEach(populate);
    initCityAutocomplete();
    initPinnedCities();
  });

  function initCityAutocomplete() {
    const input = document.getElementById('citySearchInput');
    const dropdown = document.getElementById('citySuggestionsDropdown');
    const form = document.getElementById('weatherSearchForm');
    if (!input || !dropdown) return;

    let debounceTimer = null;
    let selectedIndex = -1;

    input.addEventListener('input', function () {
      const q = input.value.trim();
      clearTimeout(debounceTimer);

      if (q.length < 2) {
        dropdown.style.display = 'none';
        dropdown.innerHTML = '';
        selectedIndex = -1;
        return;
      }

      debounceTimer = setTimeout(() => {
        fetch('/weather/api/suggest/?q=' + encodeURIComponent(q))
          .then(res => res.json())
          .then(data => {
            const results = data.results || [];
            if (results.length === 0) {
              dropdown.style.display = 'none';
              dropdown.innerHTML = '';
              return;
            }

            dropdown.innerHTML = results.map((item) => `
              <div class="autocomplete-item" data-city="${item.name}">
                <i class="bi bi-geo-alt-fill me-2 text-warning fs-6"></i>
                <div>
                  <div class="city-name">${item.name}</div>
                  <div class="city-sub">${item.display}</div>
                </div>
              </div>
            `).join('');
            dropdown.style.display = 'block';
            selectedIndex = -1;

            dropdown.querySelectorAll('.autocomplete-item').forEach(el => {
              el.addEventListener('click', function (e) {
                e.preventDefault();
                input.value = this.dataset.city;
                dropdown.style.display = 'none';
                if (form) form.submit();
              });
            });

          })
          .catch(() => {
            dropdown.style.display = 'none';
          });
      }, 200);
    });

    document.addEventListener('click', function (e) {
      if (!input.contains(e.target) && !dropdown.contains(e.target)) {
        dropdown.style.display = 'none';
      }
    });

    input.addEventListener('keydown', function (e) {
      const items = dropdown.querySelectorAll('.autocomplete-item');
      if (dropdown.style.display === 'block' && items.length > 0) {
        if (e.key === 'ArrowDown') {
          e.preventDefault();
          selectedIndex = (selectedIndex + 1) % items.length;
          highlightItem(items);
        } else if (e.key === 'ArrowUp') {
          e.preventDefault();
          selectedIndex = (selectedIndex - 1 + items.length) % items.length;
          highlightItem(items);
        } else if (e.key === 'Enter' && selectedIndex >= 0) {
          e.preventDefault();
          items[selectedIndex].click();
        } else if (e.key === 'Escape') {
          dropdown.style.display = 'none';
        }
      }
    });

    function highlightItem(items) {
      items.forEach((item, idx) => {
        if (idx === selectedIndex) {
          item.classList.add('active');
          item.scrollIntoView({ block: 'nearest' });
        } else {
          item.classList.remove('active');
        }
      });
    }
  }

  function initPinnedCities() {
    const modalEl = document.getElementById('addLocationModal');
    const modalInput = document.getElementById('modalCityInput');
    const searchInput = document.getElementById('citySearchInput');

    if (modalEl) {
      modalEl.addEventListener('shown.bs.modal', function () {
        if (modalInput) {
          if (searchInput && searchInput.value.trim()) {
            modalInput.value = searchInput.value.trim();
          }
          modalInput.focus();
        }
      });
    }
  }
})();








