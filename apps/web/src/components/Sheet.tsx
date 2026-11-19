import { X } from "lucide-react";
import { useEffect, useRef, type ReactNode } from "react";

/**
 * Bottom sheet that slides up over the live screen (think the Uber trip card). Esc, the backdrop and the
 * close button all dismiss it. `level` stacks a second sheet (an inspection) above a panel.
 */
export function Sheet({ title, onClose, children, level = 1, wide = false }: {
  title: ReactNode; onClose: () => void; children: ReactNode; level?: 1 | 2; wide?: boolean;
}) {
  const closeRef = useRef<HTMLButtonElement>(null);
  const ref = useRef<HTMLDivElement>(null);
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    closeRef.current?.focus();
    // Only the top-most sheet (the last one mounted) reacts to Esc.
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      const dialogs = document.querySelectorAll("[data-sheet]");
      if (dialogs[dialogs.length - 1] === ref.current) onCloseRef.current();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div ref={ref} data-sheet className={"fixed inset-0 " + (level === 2 ? "z-50" : "z-40")} role="dialog" aria-modal="true" aria-label={typeof title === "string" ? title : undefined}>
      <div className="sheet-backdrop absolute inset-0 bg-black/55 backdrop-blur-[2px]" onClick={onClose} />
      <div className={"sheet-panel absolute inset-x-0 bottom-0 mx-auto flex flex-col rounded-t-2xl bg-slate-50 shadow-2xl " +
        (level === 2 ? "h-[92dvh] " : "h-[88dvh] ") + (wide ? "max-w-7xl" : "max-w-6xl")}>
        <div className="flex shrink-0 items-center gap-3 border-b border-slate-200 px-4 pb-2.5 pt-2">
          <div className="absolute left-1/2 top-1.5 h-1 w-10 -translate-x-1/2 rounded-full bg-slate-300" aria-hidden />
          <h2 className="mt-2 flex-1 truncate text-sm font-semibold text-slate-800">{title}</h2>
          <button ref={closeRef} onClick={onClose} aria-label="Close" className="mt-2 rounded-full p-1.5 text-slate-500 hover:bg-slate-200 hover:text-slate-800">
            <X size={18} />
          </button>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-5 md:px-8">{children}</div>
      </div>
    </div>
  );
}
