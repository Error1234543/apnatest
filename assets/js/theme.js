/* ===========================================================
   PrepGrid — Theme module
   Handles: dark/light mode toggle, persistence, icon/label
=========================================================== */
(function () {
  'use strict';

  var html = document.documentElement;

  function isDark() {
    return html.getAttribute('data-theme') === 'dark';
  }

  function applyTheme(dark, persist) {
    html.setAttribute('data-theme', dark ? 'dark' : 'light');

    var ti = document.getElementById('themeIcon');
    if (ti) ti.className = dark ? 'fas fa-sun' : 'fas fa-moon';

    var tl = document.getElementById('themeLabel');
    if (tl) tl.textContent = dark ? 'Light Mode' : 'Dark Mode';

    var tp = document.getElementById('themePill');
    if (tp) {
      tp.classList.toggle('active', dark);
      tp.setAttribute('aria-checked', dark ? 'true' : 'false');
    }

    if (persist !== false) {
      try { localStorage.setItem('lxp-theme', dark ? 'dark' : 'light'); } catch (e) {}
    }
  }

  function init() {
    var saved = null;
    try { saved = localStorage.getItem('lxp-theme'); } catch (e) {}
    applyTheme(saved ? saved === 'dark' : false, false);

    var tb = document.getElementById('themeBtn');
    if (tb) tb.addEventListener('click', function () { applyTheme(!isDark()); });

    var tp = document.getElementById('themePill');
    if (tp) tp.addEventListener('click', function () { applyTheme(!isDark()); });
  }

  window.PGTheme = { init: init, applyTheme: applyTheme, isDark: isDark };
})();