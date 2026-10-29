// user_menu.js — the menu under the user's name (top right of every page).
//
// Every page has its own copy of the nav bar, so instead of editing eight
// copies of the badge, each page loads this one file. It finds the
// "G. Phani" badge inside .nav and turns it into a click menu. On a page
// whose nav has no badge (graph.html), it adds one, so the menu is everywhere.
//
// Menu items: builder/admin tools, kept out of the operator tabs on purpose.

(function () {
  var USER_NAME = 'G. Phani';
  var USER_INITIALS = 'GP';
  var ITEMS = [
    { label: 'Evals', icon: '📊', href: '/admin/evals' },
  ];

  function findBadge(nav) {
    var spans = nav.querySelectorAll('span');
    for (var i = 0; i < spans.length; i++) {
      if (spans[i].textContent.trim() === USER_NAME) return spans[i].parentElement;
    }
    return null;
  }

  function makeBadge(nav) {
    var right = nav.lastElementChild;
    var b = document.createElement('div');
    b.style.cssText = 'display:flex;align-items:center;gap:6px;background:#0f172a;padding:4px 10px;border-radius:6px';
    b.innerHTML =
      '<div style="width:22px;height:22px;border-radius:50%;background:#7c3aed;display:flex;align-items:center;' +
      'justify-content:center;font-size:9px;font-weight:700;color:#fff;flex-shrink:0">' + USER_INITIALS + '</div>' +
      '<span style="font-size:11px;color:#e2e8f0;font-weight:500;white-space:nowrap">' + USER_NAME + '</span>';
    right.appendChild(b);
    return b;
  }

  function go(href) {
    // The Ask page keeps the open conversation when you leave it.
    if (typeof window.saveConversation === 'function') {
      try { window.saveConversation(); } catch (e) { /* never block navigation */ }
    }
    window.location.href = href;
  }

  function init() {
    var nav = document.querySelector('.nav');
    if (!nav) return;
    var badge = findBadge(nav) || makeBadge(nav);

    badge.style.cursor = 'pointer';
    badge.style.position = 'relative';
    badge.setAttribute('role', 'button');
    badge.setAttribute('aria-haspopup', 'true');
    badge.setAttribute('aria-expanded', 'false');
    badge.title = 'Menu';

    var caret = document.createElement('span');
    caret.textContent = '▾';
    caret.style.cssText = 'font-size:10px;color:#94a3b8;margin-left:2px';
    badge.appendChild(caret);

    var menu = document.createElement('div');
    menu.style.cssText =
      'display:none;position:absolute;right:0;top:calc(100% + 6px);min-width:160px;background:#fff;' +
      'border:1px solid #e2e8f0;border-radius:8px;box-shadow:0 8px 24px rgba(15,23,42,.15);padding:4px;z-index:1000';
    ITEMS.forEach(function (it) {
      var a = document.createElement('a');
      a.href = it.href;
      a.innerHTML = '<span style="width:18px;display:inline-block">' + it.icon + '</span>' + it.label;
      var here = window.location.pathname === it.href;
      a.style.cssText =
        'display:flex;align-items:center;gap:6px;padding:7px 10px;font-size:12px;border-radius:6px;' +
        'text-decoration:none;font-family:inherit;' +
        (here ? 'color:#4f46e5;font-weight:600;background:#eef2ff' : 'color:#334155');
      a.addEventListener('mouseenter', function () { if (!here) a.style.background = '#f1f5f9'; });
      a.addEventListener('mouseleave', function () { if (!here) a.style.background = ''; });
      a.addEventListener('click', function (e) { e.preventDefault(); go(it.href); });
      menu.appendChild(a);
    });
    badge.appendChild(menu);

    function setOpen(open) {
      menu.style.display = open ? 'block' : 'none';
      badge.setAttribute('aria-expanded', open ? 'true' : 'false');
    }
    badge.addEventListener('click', function (e) {
      if (menu.contains(e.target)) return;
      e.stopPropagation();
      setOpen(menu.style.display !== 'block');
    });
    document.addEventListener('click', function () { setOpen(false); });
    document.addEventListener('keydown', function (e) { if (e.key === 'Escape') setOpen(false); });
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init);
  else init();
})();
