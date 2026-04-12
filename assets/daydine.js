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
