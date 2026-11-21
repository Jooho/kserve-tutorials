// Terminal colours and text size, shared by the main page (app.js) and the ⧉
// terminal tab (shell.js). Colours follow the page theme (Auto / Light / Dark,
// localStorage "tut.theme"); both palettes keep every ANSI colour readable on
// their background (xterm's defaults put yellow and white on white).
"use strict";
const TUT_TERM = (() => {
  const THEMES = {
    dark: { background: "#1b2029", foreground: "#e6e9ef", cursor: "#e6e9ef", selectionBackground: "#3b4558",
      black: "#3b4252", red: "#ff7b72", green: "#7ee787", yellow: "#f2cc60", blue: "#79c0ff", magenta: "#d2a8ff",
      cyan: "#76e3ea", white: "#e6e9ef", brightBlack: "#8b93a5", brightRed: "#ffa198", brightGreen: "#aff5b4",
      brightYellow: "#f8e3a1", brightBlue: "#a5d6ff", brightMagenta: "#e2c5ff", brightCyan: "#b3f0ff", brightWhite: "#ffffff" },
    light: { background: "#ffffff", foreground: "#1f2328", cursor: "#1f2328", selectionBackground: "#c8d7fa",
      black: "#1f2328", red: "#cf222e", green: "#116329", yellow: "#7d4e00", blue: "#0550ae", magenta: "#8250df",
      cyan: "#1b7c83", white: "#6e7781", brightBlack: "#57606a", brightRed: "#a40e26", brightGreen: "#1a7f37",
      brightYellow: "#633c01", brightBlue: "#0969da", brightMagenta: "#6639ba", brightCyan: "#3192aa", brightWhite: "#8c959f" },
  };
  const get = (k, d) => { try { return localStorage.getItem(k) ?? d; } catch { return d; } };
  const media = matchMedia("(prefers-color-scheme: dark)");
  const choice = () => { const t = get("tut.theme", "auto"); return t === "light" || t === "dark" ? t : "auto"; };
  const isDark = () => choice() === "dark" || (choice() === "auto" && media.matches);
  return {
    THEMES, media, choice, isDark,
    theme: () => THEMES[isDark() ? "dark" : "light"],
    fontSize: () => Math.min(28, Math.max(10, +get("tut.termfs", 14) || 14)),
    // <html data-theme> for the page's CSS, from the saved choice
    applyPageTheme() {
      const t = choice();
      if (t === "auto") delete document.documentElement.dataset.theme;
      else document.documentElement.dataset.theme = t;
    },
  };
})();
