/* ===========================================================
   PrepGrid — Navigation module
   Handles: sticky navbar, mobile drawer, modal open/close,
            auth UI, notes, floating tools, join popup
=========================================================== */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };

  /* ---------- sticky navbar ---------- */
  function initNavbar() {
    var nav = $('navbar');
    function onScroll() { if (nav) nav.classList.toggle('scrolled', window.scrollY > 10); }
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
  }

  /* ---------- mobile drawer ---------- */
  function initDrawer() {
    var hb = $('hamburger'), dOv = $('drawerOverlay'), dr = $('drawer'), dCl = $('drawerClose');
    if (!hb || !dr || !dOv) return;

    function openDrawer() { dr.classList.add('open'); dOv.classList.add('open'); hb.classList.add('open'); }
    function closeDrawer() { dr.classList.remove('open'); dOv.classList.remove('open'); hb.classList.remove('open'); }
    function toggleDrawer() { if (dr.classList.contains('open')) closeDrawer(); else openDrawer(); }

    hb.addEventListener('click', toggleDrawer);
    if (dCl) dCl.addEventListener('click', closeDrawer);
    dOv.addEventListener('click', closeDrawer);
    document.querySelectorAll('[data-nav]').forEach(function (el) { el.addEventListener('click', closeDrawer); });

    ['drawerJoin', 'drawerTgRow'].forEach(function (id) {
      var el = $(id); if (el) el.addEventListener('click', closeDrawer);
    });

    window.PGNav = { closeDrawer: closeDrawer, openDrawer: openDrawer };
  }

  /* ---------- modals ---------- */
  function openModal(m) { if (m) m.classList.add('active'); }
  function closeModal(m) { if (m) m.classList.remove('active'); }

  function initModals() {
    document.querySelectorAll('.modal-overlay').forEach(function (ov) {
      ov.addEventListener('click', function (e) { if (e.target === ov) ov.classList.remove('active'); });
    });
    document.addEventListener('keydown', function (e) {
      if (e.key === 'Escape') {
        document.querySelectorAll('.modal-overlay.active').forEach(function (m) { m.classList.remove('active'); });
      }
    });
  }

  /* ---------- auth ---------- */
  var activeUser = null;
  try { activeUser = localStorage.getItem('lxp_user'); } catch (e) {}

  if (!localStorage.getItem('user_sonic8307')) {
    localStorage.setItem('user_sonic8307', JSON.stringify({ pass: 'Sonic@#8307', nick: 'Admin Sonic', notes: [] }));
  }

  function updateAuthUI() {
    var at = $('navAuthText'), av = $('navAvatar'), lo = $('logoutBtn'), su = $('submitAuth');
    if (activeUser) {
      var ud = null;
      try { ud = JSON.parse(localStorage.getItem('user_' + activeUser)); } catch (e) {}
      var nick = (ud && ud.nick) || activeUser;
      var letter = (nick.replace(/[^a-zA-Z0-9]/g, '').charAt(0) || '?').toUpperCase();
      if (at) at.textContent = nick;
      if (av) av.textContent = letter;
      if (lo) lo.style.display = 'block';
      if (su) su.style.display = 'none';
      ['authGrpUser', 'authGrpPass', 'authGrpNick'].forEach(function (i) {
        var e = $(i); if (e) e.style.display = 'none';
      });
    } else {
      if (at) at.textContent = 'Login';
      if (av) av.textContent = '?';
      if (lo) lo.style.display = 'none';
      if (su) su.style.display = 'block';
      ['authGrpUser', 'authGrpPass', 'authGrpNick'].forEach(function (i) {
        var e = $(i); if (e) e.style.display = 'flex';
      });
    }
  }

  function initAuth() {
    var authModal = $('authModal');
    var notesModal = $('notesModal');

    if ($('authBtn')) $('authBtn').addEventListener('click', function () { openModal(authModal); });
    if ($('closeAuth')) $('closeAuth').addEventListener('click', function () { closeModal(authModal); });

    if ($('submitAuth')) $('submitAuth').addEventListener('click', function () {
      var user = ($('authUser').value || '').trim();
      var pass = ($('authPass').value || '').trim();
      var nick = ($('authNick').value || '').trim() || user;
      var msg = $('authMsg');

      if (!user || !pass) {
        if (msg) { msg.style.display = 'block'; msg.textContent = 'Enter valid details!'; }
        return;
      }
      var ex = localStorage.getItem('user_' + user);
      if (ex) {
        if (JSON.parse(ex).pass === pass) {
          activeUser = user;
          localStorage.setItem('lxp_user', user);
          closeModal(authModal);
          updateAuthUI();
        } else if (msg) {
          msg.style.display = 'block'; msg.textContent = 'Incorrect Password!';
        }
      } else {
        localStorage.setItem('user_' + user, JSON.stringify({ pass: pass, nick: nick, notes: [] }));
        activeUser = user;
        localStorage.setItem('lxp_user', user);
        closeModal(authModal);
        updateAuthUI();
      }
    });

    if ($('logoutBtn')) $('logoutBtn').addEventListener('click', function () {
      localStorage.removeItem('lxp_user');
      activeUser = null;
      closeModal(authModal);
      updateAuthUI();
    });

    if ($('closeNotes')) $('closeNotes').addEventListener('click', function () { closeModal(notesModal); });
    if ($('saveNoteBtn')) $('saveNoteBtn').addEventListener('click', function () {
      var t = ($('noteTitle').value || '').trim();
      var d = ($('noteDesc').value || '').trim();
      if (!t) return;
      var ud = JSON.parse(localStorage.getItem('user_' + activeUser));
      ud.notes.push({ title: t, desc: d, date: new Date().toLocaleDateString() });
      localStorage.setItem('user_' + activeUser, JSON.stringify(ud));
      $('noteTitle').value = '';
      $('noteDesc').value = '';
      renderNotes();
    });

    updateAuthUI();
  }

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (m) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[m];
    });
  }

  function renderNotes() {
    var list = $('notesList');
    if (!activeUser || !list) return;
    var ud = JSON.parse(localStorage.getItem('user_' + activeUser));
    if (!ud.notes || !ud.notes.length) {
      list.innerHTML = "<p style='font-size:.84rem;color:var(--ink-3);'>No saved records yet.</p>";
      return;
    }
    list.innerHTML = ud.notes.map(function (n) {
      return '<div class="note-card"><div class="note-meta"><span>Folder Record</span><span>' +
        esc(n.date) + '</span></div><h4>' + esc(n.title) + '</h4><p>' + esc(n.desc) + '</p></div>';
    }).reverse().join('');
  }

  /* ---------- join popup ---------- */
  function initJoinPopup() {
    var jm = $('joinModal');

    function showJoin() { if (jm) openModal(jm); }
    function hideJoin() { closeModal(jm); }

    if ($('joinClose')) $('joinClose').addEventListener('click', hideJoin);
    if ($('joinLater')) $('joinLater').addEventListener('click', hideJoin);
    if ($('joinGo')) $('joinGo').addEventListener('click', hideJoin);

    var joinSeen = false;
    try { joinSeen = sessionStorage.getItem('pg_join_shown') === '1'; } catch (e) {}

    window.addEventListener('load', function () {
      if (joinSeen) return;
      try { sessionStorage.setItem('pg_join_shown', '1'); } catch (e) {}
      setTimeout(showJoin, 800);
    });
  }

  /* ---------- floating tools ---------- */
  function initFloatingTools() {
    var tw = $('floatingToolWrapper'), ftb = $('floatingToolBtn'), tm = $('toolMenu');
    if (!tw || !ftb || !tm) return;

    var dragging = false, dragged = false, sx = 0, sy = 0, ix = 0, iy = 0;

    ftb.addEventListener('mousedown', ds);
    ftb.addEventListener('touchstart', ds, { passive: true });
    ftb.addEventListener('click', function () {
      if (dragged) return;
      tm.classList.toggle('open');
    });
    document.addEventListener('mousemove', dm);
    document.addEventListener('touchmove', dm, { passive: false });
    document.addEventListener('mouseup', de);
    document.addEventListener('touchend', de);

    function ds(e) {
      if (e.type === 'touchstart') { sx = e.touches[0].clientX; sy = e.touches[0].clientY; }
      else { sx = e.clientX; sy = e.clientY; }
      ix = tw.offsetLeft; iy = tw.offsetTop;
      dragging = true; dragged = false;
    }
    function dm(e) {
      if (!dragging) return;
      var cx, cy;
      if (e.type === 'touchmove') { cx = e.touches[0].clientX; cy = e.touches[0].clientY; }
      else { cx = e.clientX; cy = e.clientY; }
      if (Math.abs(cx - sx) > 5 || Math.abs(cy - sy) > 5) { e.preventDefault(); dragged = true; }
      tw.style.left = (ix + (cx - sx)) + 'px';
      tw.style.top = (iy + (cy - sy)) + 'px';
      tw.style.bottom = 'auto';
      tw.style.right = 'auto';
    }
    function de() { dragging = false; }

    if ($('btnHome')) $('btnHome').addEventListener('click', function () {
      window.scrollTo({ top: 0, behavior: 'smooth' });
      tm.classList.remove('open');
    });
    if ($('btnScreenshot')) $('btnScreenshot').addEventListener('click', function () {
      tm.classList.remove('open');
      setTimeout(function () { window.print(); }, 300);
    });
    if ($('btnNotes')) $('btnNotes').addEventListener('click', function () {
      tm.classList.remove('open');
      if (!activeUser) {
        alert('Please Login/Create Profile first to use Notes!');
        openModal($('authModal'));
        return;
      }
      openModal($('notesModal'));
      renderNotes();
    });
  }

  function init() {
    initNavbar();
    initDrawer();
    initModals();
    initAuth();
    initJoinPopup();
    initFloatingTools();
  }

  window.PGNav = window.PGNav || {};
  window.PGNav.init = init;
  window.PGNav.openModal = openModal;
  window.PGNav.closeModal = closeModal;
  window.PGNav.getActiveUser = function () { return activeUser; };
})();