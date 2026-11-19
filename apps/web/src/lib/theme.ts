import { useCallback, useEffect, useState } from "react";

export type Theme = "light" | "dark";
const KEY = "ledgeit-theme";

function read(): Theme {
  try { return localStorage.getItem(KEY) === "dark" ? "dark" : "light"; } catch { return "light"; }
}

/** Light (blue/white) is the default; dark (charcoal) is remembered per browser. */
export function useTheme() {
  const [theme, setTheme] = useState<Theme>(read);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    try { localStorage.setItem(KEY, theme); } catch { /* private window: just don't persist */ }
  }, [theme]);
  const toggle = useCallback(() => setTheme((t) => (t === "dark" ? "light" : "dark")), []);
  return { theme, toggle };
}
