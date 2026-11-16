// Recorded from one real run on 2026-11-16: the Harbor Shield sample (samples/01_harbor_shield_basic.txt)
// through openai/gpt-oss-120b on Groq, then the rules engine on a cataract bill. The demos replay
// these numbers and these words; nothing here is made up for effect.

export const RUN = {
  model: "gpt-oss-120b",
  provider: "Groq",
  date: "16 Nov 2026",
  promptTokens: 1051,
  reasoningTokens: 863,
  answerTokens: 687, // 1,550 completion tokens, 863 of them reasoning
  totalTokens: 2601,
  seconds: 4.2,
  pages: 3,
} as const;

// Verbatim lines from the model's own reasoning for that run (cut, never reworded).
export const THINKING = [
  "Sum insured: Rs. 5,00,000 per policy year => 500000. source page 1, quote.",
  "Co_pay_pct: 10% => 10. source page 1.",
  "Cataract surgery limited to Rs. 40,000 per eye. Procedure name lower-case \"cataract\". limit 40000. source page 2 quote.",
] as const;

// Lines of the synthetic policy the model cited, with the page it cited.
export const DOC = [
  { page: 1, text: "Sum insured: Rs. 5,00,000 per policy year" },
  { page: 1, text: "Co-payment: You pay 10% of every admissible claim" },
  { page: 2, text: "Cataract surgery is limited to Rs. 40,000 per eye" },
] as const;

// What the model returned for those lines (values after the server parsed and checked them).
export const FIELDS = [
  { label: "Sum insured", value: "₹5,00,000", page: 1 },
  { label: "Co-payment", value: "10%", page: 1 },
  { label: "Cataract limit", value: "₹40,000", page: 2 },
] as const;

// The engine's real trail for: cataract, 3 days, room ₹8,000/day, total bill ₹91,000.
// `amount` is what remained after the step.
export const TRAIL = [
  { name: "Bill as submitted", note: "Sum of itemised charges", amount: 91000, delta: 0 },
  { name: "Waiting period", note: "Policy age 800 days, cataract wait 730", amount: 91000, delta: 0 },
  { name: "Exclusions", note: "Cataract is not excluded", amount: 91000, delta: 0 },
  { name: "Room rent cap", note: "Cap ₹5,000 / room ₹8,000 = 0.6250", amount: 65875, delta: -25125 },
  { name: "Sub-limit", note: "Cataract limit ₹40,000", amount: 40000, delta: -25875 },
  { name: "Co-payment", note: "10%: insurer pays 90%", amount: 36000, delta: -4000 },
] as const;

export const PAYOUT = 36000;
export const BILL = 91000;

export const inr = (n: number) => `₹${n.toLocaleString("en-IN")}`;

// Headline numbers from evals/results.json (run 2026-11-16, 10 synthetic policies).
export const EVALS = {
  accuracy: "99.8%",
  citations: "98.1%",
  citationCount: 157,
  flagged: "3.6%",
  policies: 10,
  fields: 110,
} as const;
