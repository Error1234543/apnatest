/* ===========================================================
   PrepGrid — Application bootstrap
   Wires modules together and handles the initial loader.
=========================================================== */
(function () {
  'use strict';

  function hideLoader() {
    var l = document.getElementById('loader');
    if (l) l.classList.add('hide');
  }

  function init() {
    /* loader */
    window.addEventListener('load', function () {
      setTimeout(hideLoader, 450);
    });
    /* safety net: never leave the loader stuck */
    setTimeout(hideLoader, 3500);

    /* theme first (visual) */
    if (window.PGTheme && window.PGTheme.init) window.PGTheme.init();

    /* navigation (drawer, modals, auth, floating tools, join popup) */
    if (window.PGNav && window.PGNav.init) window.PGNav.init();

    /* search wiring (needs DOM, but cards are injected later) */
    if (window.PGSearch && window.PGSearch.init) window.PGSearch.init();

    /* folders: fetch JSON and render cards */
    if (window.PGFolders && window.PGFolders.load) window.PGFolders.load();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();