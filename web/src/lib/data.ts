import type { Claim, Company, FilingSummary, Metrics, SiteData } from "../types";
import { companyName } from "./companies";

// Written by the AWS pipeline (see infra/). If CloudFront can't be reached
// the site falls back to the snapshot bundled in public/.
const LIVE_URL = "https://d3l6tnkvdksi5y.cloudfront.net/public/data.json";
const SNAPSHOT_URL = `${import.meta.env.BASE_URL}data.json`;

/** Below this many concrete+vague claims a substance score means nothing. */
export const MIN_CLAIMS = 5;

interface RawData {
  companies: Array<Record<string, unknown>>;
  claims: Claim[];
  metrics: Metrics;
  updated?: string;
}

function toSummary(raw: Record<string, unknown>): FilingSummary {
  const num = (k: string) => Number(raw[k] ?? 0);
  const concrete = num("concrete");
  const vague = num("vague");
  const sub = raw.substance;
  return {
    ticker: String(raw.ticker),
    fiscal_year: num("fiscal_year"),
    ai_sentences: num("ai_sentences"),
    concrete,
    vague,
    risk: num("risk"),
    context: num("context"),
    substance: concrete + vague >= MIN_CLAIMS && sub !== null && sub !== "" ? Number(sub) : null,
  };
}

/** Group filings by company: latest year, plus the one before it for comparison. */
export function toCompanies(rows: Array<Record<string, unknown>>): Company[] {
  const byTicker = new Map<string, FilingSummary[]>();
  for (const row of rows) {
    const s = toSummary(row);
    byTicker.set(s.ticker, [...(byTicker.get(s.ticker) ?? []), s]);
  }
  return [...byTicker.values()].map((filings) => {
    filings.sort((a, b) => a.fiscal_year - b.fiscal_year);
    const cur = filings[filings.length - 1];
    const prev = filings.length > 1 ? filings[filings.length - 2] : null;
    const delta = prev && cur.substance !== null && prev.substance !== null ? cur.substance - prev.substance : null;
    return { ...cur, name: companyName(cur.ticker), prev, delta };
  });
}

async function fetchJson(url: string): Promise<RawData> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`${url}: ${res.status}`);
  return res.json();
}

export async function loadData(): Promise<SiteData> {
  let raw: RawData;
  let live = true;
  try {
    raw = await fetchJson(LIVE_URL);
  } catch {
    raw = await fetchJson(SNAPSHOT_URL);
    live = false;
  }
  return {
    companies: toCompanies(raw.companies),
    claims: raw.claims.map((c) => ({ ...c, fiscal_year: Number(c.fiscal_year), page: Number(c.page) })),
    metrics: raw.metrics,
    updated: raw.updated ?? null,
    live,
  };
}

export const claimsFor = (data: SiteData, c: Company) =>
  data.claims.filter((x) => x.ticker === c.ticker && x.fiscal_year === c.fiscal_year);
