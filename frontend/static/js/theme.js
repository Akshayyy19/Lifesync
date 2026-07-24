/**
 * LifeSync — theme.js
 *
 * Decides whether the app should look like "day" or "night" right now,
 * then populates the .sky-scene layer inside the header with lightweight
 * animated elements that match the current weather condition (when known).
 *
 * Day/night source of truth:
 *   - body[data-theme-pref] = "day" | "night" -> always that theme
 *   - body[data-theme-pref] = "auto" (default) -> based on the visitor's
 *     local clock (06:00–18:00 = day)
 *
 * Weather condition source of truth:
 *   - body[data-weather-condition], populated by the dashboard view from
 *     the live OpenWeatherMap response. Empty on pages that don't fetch
 *     weather — those just get a neutral clear sky for the current time.
 */
(function () {
  'use strict';

  function isDaytimeNow() {
    const hour = new Date().getHours();
    return hour >= 6 && hour < 18;
  }

  function resolveIsDay() {
    const pref = document.body.dataset.themePref || 'auto';
    if (pref === 'day') return true;
    if (pref === 'night') return false;
    return isDaytimeNow();
  }

  function resolveCondition(isDay) {
    const raw = (document.body.dataset.weatherCondition || '').toLowerCase();
    const known = ['sunny', 'cloudy', 'rainy', 'snowy', 'thunderstorm', 'misty', 'clear-night'];
    if (known.includes(raw)) return raw;
    return isDay ? 'sunny' : 'clear-night';
  }

  function rand(min, max) {
    return Math.random() * (max - min) + min;
  }

  function el(className, styles) {
    const node = document.createElement('div');
    node.className = className;
    Object.assign(node.style, styles || {});
    return node;
  }

  function buildStars(scene, count) {
    for (let i = 0; i < count; i++) {
      scene.appendChild(el('sky-star', {
        left: rand(2, 98) + '%',
        top: rand(4, 85) + '%',
        animationDelay: rand(0, 3) + 's',
        animationDuration: rand(2.4, 4.2) + 's',
      }));
    }
  }

  function buildClouds(scene, count) {
    for (let i = 0; i < count; i++) {
      const width = rand(70, 150);
      scene.appendChild(el('sky-cloud', {
        width: width + 'px',
        height: (width * 0.4) + 'px',
        top: rand(8, 55) + '%',
        left: rand(-10, 90) + '%',
        animationDuration: rand(38, 70) + 's',
        animationDelay: '-' + rand(0, 40) + 's',
      }));
    }
  }

  function buildRain(scene, count) {
    for (let i = 0; i < count; i++) {
      scene.appendChild(el('sky-raindrop', {
        left: rand(0, 100) + '%',
        animationDuration: rand(0.5, 0.9) + 's',
        animationDelay: rand(0, 1.5) + 's',
      }));
    }
  }

  function buildSnow(scene, count) {
    for (let i = 0; i < count; i++) {
      scene.appendChild(el('sky-snowflake', {
        left: rand(0, 100) + '%',
        animationDuration: rand(4, 8) + 's',
        animationDelay: rand(0, 5) + 's',
      }));
    }
  }

  function buildLightning(scene) {
    const flash = el('sky-lightning', {});
    scene.appendChild(flash);
    const strike = () => {
      flash.classList.remove('flash');
      // Force reflow so the animation can restart.
      void flash.offsetWidth;
      flash.classList.add('flash');
      setTimeout(strike, rand(4000, 9000));
    };
    setTimeout(strike, rand(1500, 4000));
  }

  function renderScene(scene, condition, isDay) {
    scene.innerHTML = '';

    if (isDay) {
      scene.appendChild(el('sky-sun', { top: '14%', right: '8%' }));
    } else {
      scene.appendChild(el('sky-moon', { top: '16%', right: '10%' }));
      buildStars(scene, 45);
    }

    switch (condition) {
      case 'cloudy':
        buildClouds(scene, 5);
        break;
      case 'rainy':
        buildClouds(scene, 3);
        buildRain(scene, 60);
        break;
      case 'thunderstorm':
        buildClouds(scene, 4);
        buildRain(scene, 50);
        buildLightning(scene);
        break;
      case 'snowy':
        buildClouds(scene, 3);
        buildSnow(scene, 40);
        break;
      case 'misty':
        buildClouds(scene, 6);
        break;
      default:
        // sunny / clear-night — a couple of stray clouds keeps it lively.
        buildClouds(scene, 2);
    }
  }

  function applyTheme() {
    const isDay = resolveIsDay();
    document.body.classList.toggle('theme-day', isDay);
    document.body.classList.toggle('theme-night', !isDay);
    document.documentElement.setAttribute('data-bs-theme', isDay ? 'light' : 'dark');

    const scene = document.getElementById('skyScene');
    if (scene) {
      renderScene(scene, resolveCondition(isDay), isDay);
    }
  }

  document.addEventListener('DOMContentLoaded', applyTheme);

  // Re-check every few minutes in case someone leaves a tab open across
  // the day/night boundary while theme_preference is "auto".
  setInterval(applyTheme, 5 * 60 * 1000);
})();
