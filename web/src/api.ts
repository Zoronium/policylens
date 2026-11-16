// Money crosses the wire as decimal strings and stays strings until Intl formats them.

export interface Cited<T> {
  value: T | null;
  source_page: number | null;
  source_quote: string | null;
  confidence: number;
  quote_verified: boolean | null;
  needs_review: boolean;
}

export interface DailyCap {
  kind: "flat" | "pct_si";
  amount: string;
}
export interface SubLimit {
  procedure: string;
  limit: string;
}
export interface SpecificWait {
  illness: string;
  months: number;
}

export interface PolicyCoverage {
  sum_insured: Cited<string>;
  room_rent_cap: Cited<DailyCap>;
  icu_cap: Cited<DailyCap>;
  co_pay_pct: Cited<string>;
  deductible: Cited<string>;
  sub_limits: Cited<SubLimit>[];
  waiting_periods: {
    initial_days: Cited<number>;
    pre_existing_months: Cited<number>;
    specific_illness: Cited<SpecificWait>[];
  };
  exclusions: Cited<string>[];
  network_only: Cited<boolean>;
  warnings: string[];
}

export interface Policy {
  id: string;
  created_at: string;
  source_name: string | null;
  model: string;
  pages: string[];
  coverage: PolicyCoverage;
  needs_human_review: boolean;
  review_fields: string[];
}

export interface Charges {
  room: string;
  icu: string;
  doctor: string;
  ot: string;
  pharmacy: string;
  diagnostics: string;
  consumables: string;
  other: string;
}

export interface Scenario {
  procedure: string;
  days_admitted: number;
  room_rent_per_day: string;
  icu_days: number;
  charges: Charges;
  policy_age_days: number;
  is_pre_existing: boolean;
  sum_insured_used: string;
}

export interface AuditStep {
  step: number;
  name: string;
  rule: string;
  outcome: "applied" | "skipped" | "rejected";
  before: string;
  after: string;
  note: string;
}

export interface Estimate {
  status: "payable" | "rejected";
  total_billed: string;
  payable: string;
  patient_pays: string;
  rejection_reason: string | null;
  trail: AuditStep[];
}

export interface Sample {
  name: string;
  text: string;
}

export class ApiError extends Error {
  status = 0;
}

// The session token (one hour) lives in sessionStorage: gone when the tab closes, never in a URL.
const TOKEN_KEY = "pl_session";
function readToken(): { token: string; exp: number } | null {
  try {
    const t = JSON.parse(sessionStorage.getItem(TOKEN_KEY) ?? "null");
    return t && t.exp * 1000 > Date.now() ? t : null;
  } catch {
    return null;
  }
}
export const hasSession = () => readToken() !== null;
const clearSession = () => {
  try {
    sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable */
  }
};

async function call<T>(url: string, init: RequestInit = {}): Promise<T> {
  let r: Response;
  const session = readToken();
  if (session) init = { ...init, headers: { ...init.headers, Authorization: `Bearer ${session.token}` } };
  try {
    r = await fetch(url, init);
  } catch {
    throw new ApiError("Cannot reach the API. Is the server running on port 8000?");
  }
  if (r.status === 401) clearSession();
  if (!r.ok) {
    let detail = `Request failed (${r.status}).`;
    try {
      const body = await r.json();
      if (typeof body.detail === "string") detail = body.detail;
      else if (Array.isArray(body.detail))
        detail = body.detail.map((d: { loc: string[]; msg: string }) => `${d.loc.slice(1).join(".")}: ${d.msg}`).join("; ");
    } catch {
      /* keep the generic message */
    }
    const err = new ApiError(detail);
    err.status = r.status;
    throw err;
  }
  return r.json() as Promise<T>;
}

export const api = {
  health: () => call<{ ok: boolean; llm_configured: boolean; auth_required: boolean }>("/health"),
  login: async (code: string) => {
    const r = await call<{ token: string; expires_at: number }>("/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    try {
      sessionStorage.setItem(TOKEN_KEY, JSON.stringify({ token: r.token, exp: r.expires_at }));
    } catch {
      /* storage unavailable: the code will be asked for again */
    }
  },
  samples: () => call<Sample[]>("/samples"),
  getPolicy: (id: string) => call<Policy>(`/policies/${id}`),
  createPolicy: (form: FormData) => call<Policy>("/policies", { method: "POST", body: form }),
  estimate: (policy_id: string, scenario: Scenario) =>
    call<Estimate>("/estimate", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ policy_id, scenario }),
    }),
};
