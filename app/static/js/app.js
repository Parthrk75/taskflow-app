// Dark / light theme toggle
(function () {
  var btn = document.getElementById('theme-toggle');
  if (!btn) return;
  var icon = btn.querySelector('i');
  function sync() {
    var dark = document.documentElement.getAttribute('data-bs-theme') === 'dark';
    icon.className = dark ? 'bi bi-sun' : 'bi bi-moon-stars';
  }
  btn.addEventListener('click', function () {
    var next = document.documentElement.getAttribute('data-bs-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-bs-theme', next);
    localStorage.setItem('theme', next);
    sync();
  });
  sync();
})();

// Auto-dismiss flash messages
setTimeout(function () {
  document.querySelectorAll('.alert-dismissible').forEach(function (el) {
    bootstrap.Alert.getOrCreateInstance(el).close();
  });
}, 4000);
