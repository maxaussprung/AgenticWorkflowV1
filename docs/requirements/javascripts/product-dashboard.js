// Product dashboard interactivity:
//  - show only the selected product (left nav -> #anchor; default = first product)
//  - sortable table columns (click a header)
(function () {
  function activate() {
    var sections = document.querySelectorAll('.rm-pd__product');
    if (!sections.length) return;
    var hash = (window.location.hash || '').replace('#', '');
    var target = hash ? document.getElementById(hash) : null;
    if (!target || !target.classList.contains('rm-pd__product')) target = sections[0];
    sections.forEach(function (s) { s.classList.toggle('is-active', s === target); });
    document.querySelectorAll('.rm-pd__nav a').forEach(function (a) {
      a.classList.toggle('is-active', a.getAttribute('href') === '#' + target.id);
    });
  }

  function setupSort() {
    document.querySelectorAll('.rm-pd__product table').forEach(function (t) {
      var ths = t.querySelectorAll('thead th');
      ths.forEach(function (th, idx) {
        th.addEventListener('click', function () {
          var asc = th.getAttribute('data-sort') !== 'asc';
          ths.forEach(function (h) { h.removeAttribute('data-sort'); });
          th.setAttribute('data-sort', asc ? 'asc' : 'desc');
          var tbody = t.querySelector('tbody');
          var rows = Array.prototype.slice.call(tbody.querySelectorAll('tr'));
          rows.sort(function (a, b) {
            var av = a.children[idx].textContent.trim().toLowerCase();
            var bv = b.children[idx].textContent.trim().toLowerCase();
            return asc ? av.localeCompare(bv) : bv.localeCompare(av);
          });
          rows.forEach(function (r) { tbody.appendChild(r); });
        });
      });
    });
  }

  function init() { activate(); setupSort(); }
  window.addEventListener('hashchange', activate);
  document.addEventListener('DOMContentLoaded', init);
  init();
})();
