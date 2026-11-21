// Loaded in <head> of every UI page, before it paints: apply the saved theme
// (Auto / Light / Dark) so the page never flashes in the wrong colours. A file,
// not an inline script, because the Content-Security-Policy allows no inline script.
try {
  const t = localStorage.getItem("tut.theme");
  if (t === "light" || t === "dark") document.documentElement.dataset.theme = t;
} catch {}
