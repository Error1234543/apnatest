/* ===========================================================
   PrepGrid — Folders module
   Loads data/folders.json and renders folder cards.
   To add a new folder: edit data/folders.json only.
=========================================================== */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };

  var CAT_COLOR = {
    'NEET': '#7c3aed',
    'GUJCET': '#ea580c',
    'JEE': '#2563eb',
    'Board': '#059669',
    'Tests': '#d97706',
    'PYQs': '#2563eb',
    'Notes': '#7c3aed'
  };

  var foldersData = [];
  var coreGrid = null;
  var allCards = [];

  function setStat(el, target) {
    if (!el) return;
    var started = false;
    function run() {
      if (started) return;
      started = true;
      var cur = 0;
      var step = Math.max(1, Math.round(target / 22));
      var t = setInterval(function () {
        cur += step;
        if (cur >= target) { cur = target; clearInterval(t); }
        el.textContent = cur;
      }, 18);
    }
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (es) {
        es.forEach(function (e) { if (e.isIntersecting) { run(); io.unobserve(e.target); } });
      }, { threshold: 0.3 });
      io.observe(el);
    } else run();
  }

  function observeReveals() {
    var els = document.querySelectorAll('.reveal');
    if ('IntersectionObserver' in window) {
      var io = new IntersectionObserver(function (en) {
        en.forEach(function (e) {
          if (e.isIntersecting) { e.target.classList.add('in-view'); io.unobserve(e.target); }
        });
      }, { threshold: 0.08 });
      els.forEach(function (el) { io.observe(el); });
    } else {
      els.forEach(function (el) { el.classList.add('in-view'); });
    }
  }

  function renderCards() {
    if (!coreGrid) return;

    var html = foldersData.map(function (f, i) {
      var badge = f.badge
        ? '<span class="c-badge ' + f.badge + '">' + (f.badge === 'new' ? 'New' : 'Updated') + '</span>'
        : '';
      var chips = (f.chips || []).map(function (c) { return '<span class="c-chip">' + c + '</span>'; }).join('');
      var col = (f.category && CAT_COLOR[f.category]) ? CAT_COLOR[f.category] : 'var(--brand)';
      var icon = f.icon || 'fas fa-folder';

      return '' +
        '<div class="deck reveal" style="transition-delay:' + (i % 8) * 45 + 'ms">' +
          '<a href="' + f.url + '" class="card p-3d" data-search="' + (f.search || '') + '" data-cat="' + (f.category || '') + '" style="--ac:' + col + '">' +
            '<span class="f-tab"></span>' +
            '<span class="sweep"></span>' +
            '<span class="open-spinner"><span class="open-spinner-inner"></span></span>' +
            '<span class="c-top"><span class="c-cat"><span class="dot" style="background:' + col + '"></span>' + (f.category || 'Space') + '</span>' + badge + '</span>' +
            '<span class="c-ico" style="color:' + (f.iconColor || 'var(--brand)') + '"><i class="' + icon + '"></i></span>' +
            '<span class="c-t">' + f.title + '</span>' +
            '<span class="c-d">' + f.description + '</span>' +
            (chips ? '<span class="c-chips">' + chips + '</span>' : '') +
            '<span class="c-foot"><span class="c-cta">Enter Space <i class="fas fa-arrow-right"></i></span><span class="c-open"><i class="fas fa-lock-open" style="font-size:.6rem;margin-right:4px"></i>Free</span></span>' +
          '</a>' +
        '</div>';
    }).join('');

    var stdGrid = $('stdGrid');
    if (stdGrid) stdGrid.innerHTML = '';
    coreGrid.innerHTML = html;

    allCards = Array.prototype.slice.call(coreGrid.querySelectorAll('.card'));

    /* stats */
    setStat($('statSpaces'), foldersData.length);
    var streams = {};
    foldersData.forEach(function (f) {
      if (['NEET', 'GUJCET', 'JEE', 'Board'].indexOf(f.category) !== -1) streams[f.category] = 1;
    });
    setStat($('statStreams'), Object.keys(streams).length);
    setStat($('statZones'), foldersData.filter(function (f) {
      return f.category === 'Tests' || f.category === 'PYQs';
    }).length);

    wireTilt();
    observeReveals();

    /* notify search module */
    if (window.PGSearch && window.PGSearch.registerCards) {
      window.PGSearch.registerCards(allCards);
    }
  }

  /* spatial pointer parallax — desktop only */
  function wireTilt() {
    if (!window.matchMedia || !matchMedia('(hover:hover) and (pointer:fine)').matches) return;
    if (matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    var raf = null;

    coreGrid.addEventListener('mouseleave', function () {
      if (raf) cancelAnimationFrame(raf);
      resetAll();
    });
    coreGrid.addEventListener('mousemove', function (e) {
      var t = e.target.closest ? e.target.closest('.card') : null;
      if (!t || t.classList.contains('opening')) { resetAll(); return; }
      if (raf) cancelAnimationFrame(raf);
      raf = requestAnimationFrame(function () {
        var r = t.getBoundingClientRect();
        var rx = ((e.clientY - r.top) / r.height - 0.5) * -6;
        var ry = ((e.clientX - r.left) / r.width - 0.5) * 7;
        t.style.transform = 'perspective(900px) rotateX(' + rx.toFixed(2) + 'deg) rotateY(' + ry.toFixed(2) + 'deg) translateY(-6px)';
      });
    });
  }

  function resetAll() {
    if (!coreGrid) return;
    Array.prototype.forEach.call(coreGrid.querySelectorAll('.card'), function (c) {
      if (!c.classList.contains('opening')) c.style.transform = '';
    });
  }

  /* premium folder opening interaction */
  function initCardOpening() {
    var navLocked = false;
    var navTimeout = null;

    coreGrid.addEventListener('click', function (e) {
      var card = e.target.closest('.card');
      if (!card) return;
      if (e.target.closest('.open-spinner')) return;

      if (navLocked || card.classList.contains('opening')) { e.preventDefault(); return; }
      e.preventDefault();
      navLocked = true;

      var href = card.getAttribute('href');
      if (!href) { navLocked = false; return; }

      var reduceMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      card.classList.add('opening');
      void card.offsetWidth;

      var spinnerTimer = setTimeout(function () {
        var sp = card.querySelector('.open-spinner');
        if (sp) sp.style.display = 'grid';
      }, 350);

      var delay = reduceMotion ? 0 : 380;
      navTimeout = setTimeout(function () {
        clearTimeout(spinnerTimer);
        window.location.href = href;
      }, delay);

      setTimeout(function () {
        if (!document.hidden) {
          navLocked = false;
          card.classList.remove('opening');
          var sp = card.querySelector('.open-spinner');
          if (sp) sp.style.display = 'none';
          clearTimeout(spinnerTimer);
          if (navTimeout) clearTimeout(navTimeout);
        }
      }, 4500);
    });

    window.addEventListener('pageshow', function () {
      navLocked = false;
      if (coreGrid) {
        Array.prototype.forEach.call(coreGrid.querySelectorAll('.card'), function (c) {
          c.classList.remove('opening');
          var sp = c.querySelector('.open-spinner');
          if (sp) sp.style.display = 'none';
        });
      }
      if (navTimeout) clearTimeout(navTimeout);
    });
  }

  /* professional fallback if folders.json fails */
  function showLoadError(err) {
    console.error('[PrepGrid] Failed to load data/folders.json:', err);
    if (!coreGrid) return;
    coreGrid.innerHTML =
      '<div class="no-res show" style="grid-column:1/-1">' +
        '<div class="nr-ico"><i class="fas fa-triangle-exclamation"></i></div>' +
        '<p>Unable to load study spaces right now.</p>' +
        '<small>Please refresh the page. If the problem persists, contact support on Telegram.</small>' +
      '</div>';
  }

  function loadFolders() {
    coreGrid = $('coreGrid');
    if (!coreGrid) return;

    fetch('data/folders.json', { cache: 'no-cache' })
      .then(function (res) {
        if (!res.ok) throw new Error('HTTP ' + res.status + ' while fetching folders.json');
        return res.json();
      })
      .then(function (data) {
        if (!Array.isArray(data)) throw new Error('folders.json is not an array');
        foldersData = data;
        renderCards();
        initCardOpening();
      })
      .catch(showLoadError);
  }

  window.PGFolders = { load: loadFolders };
})();