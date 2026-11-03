// MiCodex: search (Go and Search, over every page's title) and Random Mibera. Everything else is plain HTML.
(function () {
  function index(done) {
    fetch('/search.json').then(function (r) { return r.json(); }).then(done);
  }
  function pad(n) { return ('000' + n).slice(-4); }

  // Go: a number goes to that Mibera, an exact title goes to its page, anything else to the results.
  var form = document.getElementById('searchform');
  if (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var q = form.q.value.trim();
      if (!q) return;
      var results = '/special/search?q=' + encodeURIComponent(q);
      if (e.submitter && e.submitter.name === 'fulltext') { location.href = results; return; }
      var n = q.replace(/^#/, '');
      if (/^\d{1,5}$/.test(n) && +n >= 1 && +n <= 10000) { location.href = '/miberas/' + pad(+n); return; }
      index(function (pages) {
        var low = q.toLowerCase();
        for (var i = 0; i < pages.length; i++) if (pages[i][0].toLowerCase() === low) { location.href = pages[i][1]; return; }
        location.href = results;
      });
    });
  }

  // The results page: every title with the words in it.
  var out = document.getElementById('searchresults');
  if (out) {
    var q = new URLSearchParams(location.search).get('q') || '';
    var low = q.toLowerCase().trim();
    document.querySelectorAll('.searchq').forEach(function (el) { el.textContent = q; });
    if (form) form.q.value = q;
    index(function (pages) {
      var hits = low ? pages.filter(function (p) { return p[0].toLowerCase().indexOf(low) !== -1; }) : [];
      if (!hits.length) { document.getElementById('searchnone').hidden = false; return; }
      document.getElementById('searchsome').hidden = false;
      hits.slice(0, 500).forEach(function (p) {
        var li = document.createElement('li');
        var a = document.createElement('a');
        a.href = p[1];
        a.textContent = p[0];
        li.appendChild(a);
        out.appendChild(li);
      });
    });
  }

  // Random Mibera.
  if (document.getElementById('randommibera')) {
    location.replace('/miberas/' + pad(1 + Math.floor(Math.random() * 10000)));
  }
})();
