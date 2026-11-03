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

  // Pictures: clicking one opens its image page, as on a 2004 wiki. Pictures that already link somewhere keep it.
  var imagePage = document.getElementById('imagepage');
  if (!imagePage) {
    var here = location.pathname;
    var title = document.title.replace(/ - [^-]+$/, '');
    document.querySelectorAll('#bodyContent img').forEach(function (img) {
      if (img.closest('a') || !/^https:\/\//.test(img.src)) return;
      var a = document.createElement('a');
      a.className = 'image';
      a.href = '/special/image?src=' + encodeURIComponent(img.src) + '&title=' + encodeURIComponent(title) + '&from=' + encodeURIComponent(here) + (img.alt ? '&alt=' + encodeURIComponent(img.alt) : '');
      img.parentNode.insertBefore(a, img);
      a.appendChild(img);
    });
  }

  // The image page: the picture large, its full-size file, and the page it came from.
  if (imagePage) {
    var p = new URLSearchParams(location.search);
    var src = p.get('src') || '';
    if (/^https:\/\//.test(src)) {
      var file = decodeURIComponent(src.split('?')[0].split('/').pop() || '');
      var name = imagePage.getAttribute('data-prefix') + ':' + (p.get('alt') || file);
      document.querySelector('h1.firstHeading').textContent = name;
      document.title = name + ' - ' + document.title.split(' - ').pop();
      var pic = document.getElementById('imagefile');
      pic.alt = p.get('alt') || file;
      pic.src = src;
      document.getElementById('imagefull').href = src;
      document.getElementById('imagefulltext').href = src;
      pic.addEventListener('load', function () {
        var words = document.getElementById('imagesize').getAttribute('data-words');
        document.getElementById('imagesize').textContent = '(' + words.replace('@@W@@', pic.naturalWidth.toLocaleString('en-US')).replace('@@H@@', pic.naturalHeight.toLocaleString('en-US')) + ')';
      });
      var from = p.get('from') || '';
      var back = document.getElementById('imagefrom');
      if (/^\/(?!\/)/.test(from)) { back.href = from; back.textContent = p.get('title') || from; }
      else back.parentNode.parentNode.hidden = true;
    }
  }

  // Random Mibera.
  if (document.getElementById('randommibera')) {
    location.replace('/miberas/' + pad(1 + Math.floor(Math.random() * 10000)));
  }
})();
