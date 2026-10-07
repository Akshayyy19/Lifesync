/**
 * LifeSync — theme.js
 *
 * Decouples User Theme Preference (Dark / Light / Auto) from Timeline (Day / Night),
 * and dynamically adapts the UI palette and animated sky scene to current weather conditions:
 * - Hot Summer Day (radiant solar flare, sun rays, heat shimmer particles)
 * - Sun & Rain Mix (sunshower: bright sun + clouds + gentle rain + rainbow arc)
 * - Rainy (storm clouds + falling rain streaks + splash ripples)
 * - Cloudy (multi-layered drifting clouds)
 * - Sunny / Clear Day (vibrant clear sky, glowing sun)
 * - Clear Night / Warm Night (luminous moon, twinkling stars, shooting star)
 * - Thunderstorm (thunderclouds, rain, realistic lightning flashes)
 * - Snowy (swaying snowflakes)
 * - Misty (undulating mist/fog bands)
 */
(function () {
  'use strict';

  function isTimelineDay() {
    const rawIsDay = (document.body.dataset.weatherIsDay || '').toLowerCase();
    if (rawIsDay === 'true') return true;
    if (rawIsDay === 'false') return false;

    // Check sunrise/sunset if provided (e.g. "6:15 AM", "6:47 PM")
    const hour = new Date().getHours();
    return hour >= 6 && hour < 18;
  }

  function resolveDarkMode(timelineIsDay) {
    const pref = (document.body.dataset.themePref || 'auto').toLowerCase();
    if (pref === 'day') return false;   // Force Light Mode
    if (pref === 'night') return true;  // Force Dark Mode
    return !timelineIsDay;              // Auto follows timeline
  }  function resolveCondition(timelineIsDay) {
    const override = (document.body.dataset.weatherOverride || '').toLowerCase().trim();
    if (override && override !== 'auto') {
      return override;
    }

    const raw = (document.body.dataset.weatherCondition || '').toLowerCase().trim();
    const known = [
      'hot-summer', 'sun-rain-mix', 'sunny', 'cloudy', 'rainy',
      'snowy', 'thunderstorm', 'misty', 'clear-night', 'hot-summer-night'
    ];
    if (known.includes(raw)) {
      if (raw === 'sunny' && !timelineIsDay) return 'clear-night';
      if (raw === 'clear-night' && timelineIsDay) return 'sunny';
      if (raw === 'hot-summer' && !timelineIsDay) return 'hot-summer-night';
      return raw;
    }

    const temp = parseFloat(document.body.dataset.weatherTemp);
    if (timelineIsDay) {
      if (!isNaN(temp) && temp >= 29) return 'hot-summer';
      return 'sunny';
    }
    return (!isNaN(temp) && temp >= 28) ? 'hot-summer-night' : 'clear-night';
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

  // --- Animation Builders ---

  function buildStars(scene, count) {
    for (let i = 0; i < count; i++) {
      scene.appendChild(el('sky-star', {
        left: rand(2, 98) + '%',
        top: rand(4, 85) + '%',
        animationDelay: rand(0, 3) + 's',
        animationDuration: rand(2.4, 4.2) + 's',
      }));
    }

    // Occasional shooting star
    const shootingStar = el('sky-shooting-star', {
      top: rand(10, 40) + '%',
      left: rand(10, 70) + '%',
    });
    scene.appendChild(shootingStar);
    const triggerShootingStar = () => {
      shootingStar.classList.remove('active');
      void shootingStar.offsetWidth;
      shootingStar.classList.add('active');
      setTimeout(triggerShootingStar, rand(7000, 14000));
    };
    setTimeout(triggerShootingStar, rand(2000, 5000));
  }

  function buildClouds(scene, count, isDarkSky) {
    for (let i = 0; i < count; i++) {
      const width = rand(90, 180);
      const isBackLayer = i % 2 === 0;
      scene.appendChild(el('sky-cloud' + (isBackLayer ? ' sky-cloud-back' : ''), {
        width: width + 'px',
        height: (width * 0.38) + 'px',
        top: rand(6, 60) + '%',
        left: rand(-15, 85) + '%',
        animationDuration: rand(isBackLayer ? 50 : 35, isBackLayer ? 85 : 60) + 's',
        animationDelay: '-' + rand(0, 45) + 's',
        opacity: isDarkSky ? (isBackLayer ? '0.2' : '0.35') : (isBackLayer ? '0.7' : '0.9'),
      }));
    }
  }

  function buildRain(scene, count, isSunShower) {
    for (let i = 0; i < count; i++) {
      scene.appendChild(el('sky-raindrop' + (isSunShower ? ' sky-raindrop-sun' : ''), {
        left: rand(0, 100) + '%',
        animationDuration: rand(isSunShower ? 0.7 : 0.45, isSunShower ? 1.1 : 0.8) + 's',
        animationDelay: rand(0, 1.8) + 's',
      }));
    }

    // Ground splash ripples
    const splashCount = isSunShower ? 6 : 14;
    for (let s = 0; s < splashCount; s++) {
      scene.appendChild(el('sky-rain-splash', {
        left: rand(2, 98) + '%',
        bottom: rand(2, 12) + 'px',
        animationDuration: rand(0.6, 1.2) + 's',
        animationDelay: rand(0, 2) + 's',
      }));
    }
  }

  function buildRainbow(scene) {
    const rainbow = el('sky-rainbow', {});
    scene.appendChild(rainbow);
  }

  function buildHotSun(scene) {
    // Rotating solar rays
    const raysWrap = el('sky-sun-rays', { top: '14%', right: '8%' });
    for (let r = 0; r < 8; r++) {
      const ray = el('sky-sun-ray', {
        transform: `rotate(${r * 45}deg)`,
      });
      raysWrap.appendChild(ray);
    }
    scene.appendChild(raysWrap);

    // Pulsing heat corona
    scene.appendChild(el('sky-sun-corona', { top: '14%', right: '8%' }));

    // Core blazing sun
    scene.appendChild(el('sky-sun sky-sun-hot', { top: '14%', right: '8%' }));

    // Heat shimmer dust particles
    for (let p = 0; p < 18; p++) {
      scene.appendChild(el('sky-heat-particle', {
        left: rand(5, 95) + '%',
        bottom: rand(0, 40) + '%',
        animationDuration: rand(3, 6) + 's',
        animationDelay: rand(0, 4) + 's',
      }));
    }

    // A few high, thin wispy clouds
    buildClouds(scene, 2, false);
  }

  function buildSnow(scene, count) {
    for (let i = 0; i < count; i++) {
      scene.appendChild(el('sky-snowflake', {
        left: rand(0, 100) + '%',
        animationDuration: rand(4.5, 8.5) + 's',
        animationDelay: rand(0, 5) + 's',
      }));
    }
  }

  function buildMisty(scene) {
    for (let m = 0; m < 4; m++) {
      scene.appendChild(el('sky-mist-band', {
        top: (15 + m * 20) + '%',
        animationDuration: rand(20, 35) + 's',
        animationDelay: '-' + (m * 5) + 's',
      }));
    }
  }

  function buildLightning(scene) {
    const flash = el('sky-lightning', {});
    scene.appendChild(flash);
    const strike = () => {
      flash.classList.remove('flash');
      void flash.offsetWidth;
      flash.classList.add('flash');
      setTimeout(strike, rand(4000, 8500));
    };
    setTimeout(strike, rand(1200, 3500));
  }

  function renderScene(scene, condition, timelineIsDay, isDarkMode) {
    scene.innerHTML = '';

    // Render celestial body based on timeline / condition
    const forceNightSky = (condition === 'clear-night' || condition === 'hot-summer-night');
    const effectiveIsDay = forceNightSky ? false : timelineIsDay;

    if (effectiveIsDay) {
      if (condition === 'hot-summer') {
        buildHotSun(scene);
      } else {
        scene.appendChild(el('sky-sun', { top: '14%', right: '8%' }));
      }
    } else {
      const isWarmNight = (condition === 'hot-summer-night');
      scene.appendChild(el('sky-moon' + (isWarmNight ? ' sky-moon-warm' : ''), { top: '16%', right: '10%' }));
      buildStars(scene, 42);
    }

    // Render weather condition overlay effects
    switch (condition) {
      case 'hot-summer':
        break;

      case 'hot-summer-night':
        for (let p = 0; p < 12; p++) {
          scene.appendChild(el('sky-heat-particle', {
            left: rand(5, 95) + '%',
            bottom: rand(0, 50) + '%',
            animationDuration: rand(4, 7) + 's',
            animationDelay: rand(0, 4) + 's',
          }));
        }
        buildClouds(scene, 1, true);
        break;

      case 'sun-rain-mix':
        buildClouds(scene, 3, isDarkMode);
        buildRain(scene, 35, true);
        buildRainbow(scene);
        break;

      case 'rainy':
        buildClouds(scene, 4, isDarkMode);
        buildRain(scene, 65, false);
        break;

      case 'thunderstorm':
        buildClouds(scene, 5, true);
        buildRain(scene, 55, false);
        buildLightning(scene);
        break;

      case 'cloudy':
        buildClouds(scene, 6, isDarkMode);
        break;

      case 'snowy':
        buildClouds(scene, 3, isDarkMode);
        buildSnow(scene, 40);
        break;

      case 'misty':
        buildClouds(scene, 3, isDarkMode);
        buildMisty(scene);
        break;

      default:
        buildClouds(scene, 2, isDarkMode);
        break;
    }
  }

  function updateThemeIcons(isDark) {
    document.querySelectorAll('.sky-theme-toggle').forEach(btn => {
      const icon = btn.querySelector('i');
      if (!icon) return;
      if (isDark) {
        icon.className = 'bi bi-moon-stars-fill';
        icon.style.color = '#7dd3fc';
        icon.style.filter = 'drop-shadow(0 0 5px rgba(56,189,248,0.85))';
        btn.setAttribute('title', 'Dark mode — click for light');
      } else {
        icon.className = 'bi bi-sun-fill';
        icon.style.color = '#fbbf24';
        icon.style.filter = 'drop-shadow(0 0 5px rgba(251,191,36,0.9))';
        btn.setAttribute('title', 'Light mode — click for dark');
      }
    });
  }
  window.updateThemeIcons = updateThemeIcons;

  function applyTheme() {
    const timelineIsDay = isTimelineDay();
    const isDarkMode = resolveDarkMode(timelineIsDay);
    const condition = resolveCondition(timelineIsDay);

    // 1. Maintain Selected Dark vs Light Theme
    document.body.classList.toggle('theme-night', isDarkMode);
    document.body.classList.toggle('theme-day', !isDarkMode);
    document.documentElement.setAttribute('data-bs-theme', isDarkMode ? 'dark' : 'light');

    // 2. Maintain Day vs Night Timeline
    document.body.classList.toggle('timeline-day', timelineIsDay);
    document.body.classList.toggle('timeline-night', !timelineIsDay);
    document.body.dataset.timeline = timelineIsDay ? 'day' : 'night';

    // 3. Set Weather Theme Classes on Body
    const allWeatherClasses = [
      'weather-hot-summer', 'weather-hot-summer-night', 'weather-sun-rain-mix',
      'weather-sunny', 'weather-clear-night', 'weather-cloudy',
      'weather-rainy', 'weather-thunderstorm', 'weather-snowy', 'weather-misty'
    ];
    allWeatherClasses.forEach(cls => document.body.classList.remove(cls));
    document.body.classList.add('weather-' + condition);
    document.body.dataset.weatherResolvedCondition = condition;

    // 4. Render Sky Scene
    const scene = document.getElementById('skyScene');
    if (scene) {
      renderScene(scene, condition, timelineIsDay, isDarkMode);
    }

    // 5. Update theme toggle icons
    updateThemeIcons(isDarkMode);
  }

  window.applyThemeScene = applyTheme;

  function getCookie(name) {
    const v = `; ${document.cookie}`, p = v.split(`; ${name}=`);
    return p.length === 2 ? p.pop().split(';').shift() : '';
  }

  function toggleThemeAction(e) {
    if (e) {
      e.preventDefault();
      e.stopPropagation();
    }
    const isCurrentlyDark = document.body.classList.contains('theme-night') ||
      document.documentElement.getAttribute('data-bs-theme') === 'dark';
    const newPref = isCurrentlyDark ? 'day' : 'night';

    try { localStorage.setItem('lifesync_theme_pref', newPref); } catch (_) {}
    document.body.dataset.themePref = newPref;

    applyTheme();

    document.querySelectorAll('.sky-theme-toggle').forEach(btn => {
      btn.classList.add('theme-toggle-spinning');
      setTimeout(() => btn.classList.remove('theme-toggle-spinning'), 420);
    });

    const csrf = getCookie('csrftoken');
    fetch('/accounts/toggle-theme/', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrf || '',
      },
      body: JSON.stringify({ theme: newPref }),
    }).catch(() => {});
  }

  function initTheme() {
    try {
      const saved = localStorage.getItem('lifesync_theme_pref');
      if (saved && (saved === 'day' || saved === 'night' || saved === 'auto')) {
        document.body.dataset.themePref = saved;
      }
    } catch (_) {}

    applyTheme();
  }

  // Document-level event delegation for theme toggles and weather experience buttons
  document.addEventListener('click', function (e) {
    const toggleBtn = e.target.closest('.sky-theme-toggle');
    if (toggleBtn) {
      toggleThemeAction(e);
      return;
    }

    const demoBtn = e.target.closest('.wx-demo-btn');
    if (demoBtn) {
      e.preventDefault();
      const effect = demoBtn.dataset.effect;
      document.body.dataset.weatherOverride = effect;
      const select = document.getElementById('weatherEffectSelect');
      if (select) select.value = effect;
      applyTheme();
    }
  });

  // Live change listener for Weather Effect Dropdown in Profile Settings
  document.addEventListener('change', function (e) {
    if (e.target && e.target.id === 'weatherEffectSelect') {
      document.body.dataset.weatherOverride = e.target.value;
      applyTheme();
    }
  });

  (function () {
    const style = document.createElement('style');
    style.textContent =
      '@keyframes themeToggleSpin{' +
        '0%{transform:scale(1) rotate(0deg);}' +
        '45%{transform:scale(0.80) rotate(165deg);}' +
        '100%{transform:scale(1) rotate(360deg);}' +
      '}' +
      '.theme-toggle-spinning{' +
        'animation:themeToggleSpin 0.42s cubic-bezier(0.34,1.56,0.64,1) both !important;' +
      '}';
    document.head.appendChild(style);
  })();

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initTheme);
  } else {
    initTheme();
  }

  setInterval(applyTheme, 3 * 60 * 1000);
})();
