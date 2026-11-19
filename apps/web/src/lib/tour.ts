import { useCallback, useState } from "react";

const KEY = "ledgeit-tour";
interface Pref { enabled: boolean; seen: boolean }

function read(): Pref {
  try {
    const p = JSON.parse(localStorage.getItem(KEY) ?? "null");
    if (p && typeof p.enabled === "boolean") return { enabled: p.enabled, seen: !!p.seen };
  } catch { /* unreadable or blocked storage: fall back to the first-visit default */ }
  return { enabled: true, seen: false };
}

function write(p: Pref) {
  try { localStorage.setItem(KEY, JSON.stringify(p)); } catch { /* private window: just don't persist */ }
}

/**
 * First-visit guided tutorial. It opens by itself once for a new browser while "enabled", and can be switched
 * off (never auto-opens again) or replayed at any time from the top bar.
 */
export function useTour() {
  const [pref, setPref] = useState<Pref>(read);
  const [running, setRunning] = useState(() => read().enabled && !read().seen);

  const save = useCallback((p: Pref) => { setPref(p); write(p); }, []);
  /** Close the tour. It counts as seen, so it will not pop up again on its own. */
  const finish = useCallback(() => { setRunning(false); save({ ...pref, seen: true }); }, [pref, save]);
  /** Switch the tutorial on (and show it now) or off (and close it). */
  const setEnabled = useCallback((on: boolean) => {
    save({ enabled: on, seen: pref.seen || !on });
    setRunning(on);
  }, [pref.seen, save]);

  return { enabled: pref.enabled, running, finish, setEnabled };
}
