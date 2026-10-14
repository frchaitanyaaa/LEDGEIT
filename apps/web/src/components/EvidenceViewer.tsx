import clsx from "clsx";
import { useState } from "react";
import type { InspectionDetail } from "../lib/types";
import { Hash } from "./ui";

export function EvidenceViewer({ ins }: { ins: InspectionDetail }) {
  const [mode, setMode] = useState<"image" | "heatmap">("image");
  const [boxes, setBoxes] = useState(true);
  const img = ins.evidence.find((e) => e.kind === "IMAGE");
  const heat = ins.evidence.find((e) => e.kind === "HEATMAP");
  const src = mode === "heatmap" && heat ? heat.url : img?.url;
  const w = img?.width ?? 200;
  const h = img?.height ?? 200;
  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center gap-2">
        {(["image", "heatmap"] as const).map((m) => (
          <button key={m} onClick={() => setMode(m)} disabled={m === "heatmap" && !heat}
            className={clsx("btn px-2.5 py-1 text-xs", mode === m ? "bg-ink-900 text-white" : "border border-slate-300 bg-white")}>
            {m === "image" ? "Original" : `Heatmap (${ins.explanation.method})`}
          </button>
        ))}
        <label className="ml-2 flex items-center gap-1.5 text-xs text-slate-600">
          <input type="checkbox" checked={boxes} onChange={(e) => setBoxes(e.target.checked)} /> boxes
        </label>
      </div>
      <div className="relative mx-auto w-full max-w-md overflow-hidden rounded-lg bg-slate-900" style={{ aspectRatio: `${w}/${h}` }}>
        {src && <img src={src} alt="inspection evidence" className="absolute inset-0 h-full w-full object-contain [image-rendering:pixelated]" />}
        {boxes && (
          <svg viewBox={`0 0 ${w} ${h}`} className="absolute inset-0 h-full w-full">
            {ins.explanation.boxes?.map((b, i) => (
              <g key={i}>
                <rect x={b.x1} y={b.y1} width={b.x2 - b.x1} height={b.y2 - b.y1} fill="none" stroke="#f43f5e" strokeWidth={Math.max(1, w / 150)} />
                <text x={b.x1 + 1} y={Math.max(8, b.y1 - 2)} fontSize={Math.max(7, w / 22)} fill="#fecdd3" fontFamily="monospace">{b.cls} {b.conf}</text>
              </g>
            ))}
          </svg>
        )}
      </div>
      <p className="mt-3 text-sm text-slate-700">{ins.explanation.summary}</p>
      <dl className="mt-3 grid grid-cols-[auto,1fr] gap-x-3 gap-y-1 text-xs">
        <dt className="text-slate-500">image sha256</dt><dd><Hash value={img?.sha256} /></dd>
        <dt className="text-slate-500">pHash</dt><dd className="font-mono">{img?.phash}</dd>
        <dt className="text-slate-500">heatmap sha256</dt><dd><Hash value={heat?.sha256} /></dd>
        <dt className="text-slate-500">size</dt><dd>{img?.width}×{img?.height} · {img ? (img.size_bytes / 1024).toFixed(1) : "?"} KB · {img?.mime_type}</dd>
      </dl>
    </div>
  );
}
