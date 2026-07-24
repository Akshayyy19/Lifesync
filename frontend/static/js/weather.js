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
  });
})();
