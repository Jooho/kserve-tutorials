// Click a picture of a tutorial or an explainer: it opens at full size in a
// dialog on the same page (Esc, the close button or a click outside closes it).
// README pictures are links to themselves (<a target="_blank"><img>): in the UI
// the link's target is removed when the page is cleaned, so without this a
// click replaced the whole page with the image.
(() => {
  const SCOPE = "#doc img, .explainer-doc img";
  let dlg;

  function dialog() {
    if (dlg) return dlg;
    dlg = document.createElement("dialog");
    dlg.className = "zoom";
    dlg.setAttribute("aria-label", "Picture at full size");
    dlg.innerHTML =
      '<button type="button" class="zoom-close" aria-label="Close picture">Close</button>' +
      '<div class="zoom-scroll"><img alt=""></div>';
    dlg.addEventListener("click", (e) => {
      // the dialog element itself is the backdrop area; the picture is inside .zoom-scroll
      if (e.target === dlg || e.target.closest(".zoom-close")) dlg.close();
    });
    document.body.appendChild(dlg);
    return dlg;
  }

  document.addEventListener("click", (e) => {
    const img = e.target.closest(SCOPE);
    if (!img || e.target.closest("dialog.zoom")) return;
    if (e.ctrlKey || e.metaKey || e.shiftKey || e.button !== 0) return;   // let "open in new tab" work
    e.preventDefault();
    const d = dialog(), big = d.querySelector("img");
    big.src = img.currentSrc || img.src;
    big.alt = img.alt || "";
    d.showModal();
    d.querySelector(".zoom-close").focus();
  });

  // Enter on the link around a picture does the same as a click (keyboard users).
  document.addEventListener("keydown", (e) => {
    if (e.key !== "Enter") return;
    const a = e.target.closest && e.target.closest("#doc a, .explainer-doc a");
    const img = a && a.querySelector(":scope > img");
    if (img) { e.preventDefault(); img.click(); }
  });
})();
