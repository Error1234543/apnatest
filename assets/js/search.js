/* ===========================================================
   PrepGrid — Search & category filter module
   Reads cards from DOM (rendered by folders.js)
=========================================================== */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };

  var allCards = [];
  var currentCat = 'All';
  var currentQuery = '';
  var noRes = null;
  var catWrap = null;
  var catOrder = [];
  var CAT_COLOR = {
    'NEET': '#7c3aed',
    'GUJCET': '#ea580c',
    'JEE': '#2563eb',
    'Board': '#059669',
    'Tests': '#d97706',
    'PYQs': '#2563eb',
    'Notes': '#7c3aed'
  };

  function buildCategoryPills() {
    catWrap = $('catFilters');
    if (!catWrap) return;

    var seen = {};
    catOrder = [];
    allCards.forEach(function (c) {
      var cat = c.getAttribute('data-cat');
      if (cat && !seen[cat]) { seen[cat] = 1; catOrder.push(cat); }
    });

    var ph = '<button class="cat-pill active" data-cat="All"><i class="fas fa-th-large"></i>All</button>';
    catOrder.forEach(function (c) {
      ph += '<button class="cat-pill" data-cat="' + c + '"><i class="fas fa-folder"></i>' + c + '</button>';
    });
    catWrap.innerHTML = ph;

    catWrap.querySelectorAll('.cat-pill').forEach(function (b) {
      b.addEventListener('click', function () {
        catWrap.querySelectorAll('.cat-pill').forEach(function (x) { x.classList.remove('active'); });
        b.classList.add('active');
        currentCat = b.getAttribute('data-cat');
        filterCards(currentQuery);
      });
    });
  }

  function filterCards(q) {
    q = (q || '').trim().toLowerCase();
    currentQuery = q;
    var visible = 0;

    allCards.forEach(function (c) {
      var catOk = currentCat === 'All' || c.getAttribute('data-cat') === currentCat;
      var hay = (c.getAttribute('data-search') || c.textContent).toLowerCase();
      var qOk = !q || hay.indexOf(q) !== -1;
      var show = catOk && qOk;
      c.style.display = show ? '' : 'none';
      if (show) visible++;
    });

    if (noRes) noRes.classList.toggle('show', visible === 0 && (q || currentCat !== 'All'));
  }

  function syncSearch(v) {
    var navSearch = $('navSearch');
    var heroInp = $('heroSearch');
    if (navSearch) navSearch.value = v;
    if (heroInp) heroInp.value = v;
    filterCards(v);
  }

  function init() {
    noRes = $('noRes');

    var navSearch = $('navSearch');
    var heroInp = $('heroSearch');
    if (navSearch) navSearch.addEventListener('input', function () { syncSearch(this.value); });
    if (heroInp) heroInp.addEventListener('input', function () { syncSearch(this.value); });

    var goBtn = $('searchGoBtn');
    if (goBtn) goBtn.addEventListener('click', function () {
      syncSearch(heroInp ? heroInp.value : '');
      var s = $('resources');
      if (s) s.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });
  }

  /* Called by folders.js once cards are rendered */
  function registerCards(cards) {
    allCards = cards || [];
    buildCategoryPills();
    filterCards('');
  }

  window.PGSearch = { init: init, registerCards: registerCards, filterCards: filterCards, syncSearch: syncSearch };
})();