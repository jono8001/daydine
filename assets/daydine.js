// Shared nav behaviour: scroll-linked shadow + mobile sensible defaults
(function () {
  const nav = document.querySelector('.nav');
  if (!nav) return;
  let ticking = false;
  function onScroll() {
    if (!ticking) {
      window.requestAnimationFrame(() => {
        nav.classList.toggle('scrolled', window.scrollY > 8);
        ticking = false;
      });
      ticking = true;
    }
  }
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });
})();

// Page-specific nav CTA: diner pages → rankings, operator pages → reports
(function () {
  var pt = document.body.dataset.pageType;
  var btn = document.querySelector('.nav-cta');
  if (pt === 'diner' && btn) {
    btn.textContent = 'Explore Rankings \u2192';
    btn.href = '/rankings';
  }
})();

// Mobile hamburger toggle
(function () {
  var toggle = document.querySelector('.nav-toggle');
  var links = document.querySelector('.nav-links');
  if (!toggle || !links) return;
  toggle.addEventListener('click', function () {
    var open = links.classList.toggle('open');
    toggle.setAttribute('aria-expanded', String(open));
  });
  // Close on link click
  links.querySelectorAll('a').forEach(function (a) {
    a.addEventListener('click', function () {
      links.classList.remove('open');
      toggle.setAttribute('aria-expanded', 'false');
    });
  });
})();
