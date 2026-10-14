// RFC 8785 JCS with the LEDGEIT "integers only" restriction (SPEC §1).

export type Json = null | boolean | number | string | Json[] | { [k: string]: Json };

function ser(v: unknown, path: string): string {
  if (v === null) return "null";
  if (typeof v === "boolean") return v ? "true" : "false";
  if (typeof v === "number") {
    if (!Number.isInteger(v)) throw new Error(`${path}: floats are not allowed in hashed payloads`);
    if (!Number.isSafeInteger(v)) throw new Error(`${path}: integer outside ±2^53-1`);
    return Object.is(v, -0) ? "0" : String(v);
  }
  if (typeof v === "string") return JSON.stringify(v);
  if (Array.isArray(v)) return "[" + v.map((x, i) => ser(x, `${path}[${i}]`)).join(",") + "]";
  if (typeof v === "object") {
    // Default JS string sort compares UTF-16 code units, exactly what RFC 8785 requires.
    const keys = Object.keys(v as object).sort();
    return (
      "{" +
      keys
        .filter((k) => (v as Record<string, unknown>)[k] !== undefined)
        .map((k) => JSON.stringify(k) + ":" + ser((v as Record<string, unknown>)[k], `${path}.${k}`))
        .join(",") +
      "}"
    );
  }
  throw new Error(`${path}: unsupported type ${typeof v}`);
}

export function canonicalString(value: unknown): string {
  return ser(value, "$");
}

export function canonicalize(value: unknown): Uint8Array {
  return new TextEncoder().encode(canonicalString(value));
}

/** Fixed-point decimal string, default 4 places (half-even on the decimal repr). */
export function fmtDecimal(value: number | string, places = 4): string {
  const s = typeof value === "number" ? value.toString() : value;
  const neg = s.startsWith("-");
  const [ip, fp = ""] = (neg ? s.slice(1) : s).split(".");
  if (fp.length <= places) return (neg ? "-" : "") + ip + "." + fp.padEnd(places, "0");
  let digits = BigInt(ip + fp.slice(0, places));
  const rest = fp.slice(places);
  const first = Number(rest[0]);
  const tailNonZero = /[1-9]/.test(rest.slice(1));
  if (first > 5 || (first === 5 && (tailNonZero || digits % 2n === 1n))) digits += 1n;
  const str = digits.toString().padStart(places + 1, "0");
  return (neg ? "-" : "") + str.slice(0, -places) + "." + str.slice(-places);
}

/** UTC ISO-8601 with milliseconds and Z. */
export function fmtTs(d: Date): string {
  return d.toISOString();
}
