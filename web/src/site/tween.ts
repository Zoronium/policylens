import type { Act } from "../stageshow/kit";

// A number that ticks up in small steps from the script, like a live token meter. Plain text in a
// fixed-width box, so nothing in the layout moves while it counts.
export async function tween<S>(a: Act<S>, key: keyof S, from: number, to: number, ms: number, step = 40) {
  const n = Math.max(1, Math.round(ms / step));
  for (let i = 1; i <= n; i++) {
    const t = i / n;
    a.put({ [key]: Math.round(from + (to - from) * (1 - Math.pow(1 - t, 3))) } as Partial<S>);
    await a.wait(step);
  }
}

export const fmt = (n: number) => n.toLocaleString("en-IN");
