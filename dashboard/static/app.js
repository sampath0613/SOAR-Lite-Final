(() => {
  const autoRefreshSection = document.querySelector("[data-auto-refresh]");

  if (!autoRefreshSection) {
    return;
  }

  const seconds = Number(autoRefreshSection.getAttribute("data-auto-refresh"));
  if (!Number.isFinite(seconds) || seconds <= 0) {
    return;
  }

  setInterval(() => {
    window.location.reload();
  }, seconds * 1000);
})();
