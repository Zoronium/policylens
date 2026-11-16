const inr0 = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Indian digit grouping: 300000 -> 3,00,000. Takes decimal strings, so no float rounding. */
export function inr(value: string | number, fixed = false): string {
  const s = String(value);
  const whole = /^-?\d+(\.0+)?$/.test(s);
  return (fixed || !whole ? inr2 : inr0).format(s as unknown as number);
}

export const rupee = "₹";

export function months(m: number): string {
  if (m % 12 === 0 && m >= 12) return `${m / 12} ${m === 12 ? "year" : "years"}`;
  return `${m} ${m === 1 ? "month" : "months"}`;
}

export function days(d: number): string {
  return `${d} ${d === 1 ? "day" : "days"}`;
}

export function pct(conf: number): string {
  return `${Math.round(conf * 100)}%`;
}

const toPaise = (s: string): bigint => {
  const [w, f = ""] = s.split(".");
  return BigInt(w + (f + "00").slice(0, 2));
};

/** before - after in exact paise, as a non-negative decimal string plus a direction. */
export function drop(before: string, after: string): { down: boolean; abs: string } {
  const d = toPaise(before) - toPaise(after);
  const a = d < 0n ? -d : d;
  return { down: d > 0n, abs: `${a / 100n}.${(a % 100n).toString().padStart(2, "0")}` };
}
