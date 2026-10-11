(function () {
  var preference = 'light';
  try { preference = localStorage.getItem('reclipd-theme') || 'light'; } catch (_) {}
  if (!['light','dark','system'].includes(preference)) preference = 'light';
  var dark = preference === 'dark' || (preference === 'system' && window.matchMedia('(prefers-color-scheme: dark)').matches);
  document.documentElement.dataset.theme = dark ? 'dark' : 'light';
  document.documentElement.style.colorScheme = dark ? 'dark' : 'light';
})();
