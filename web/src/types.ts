export type Label = "concrete" | "vague" | "risk" | "context";

export interface Claim {
  ticker: string;
  fiscal_year: number;
  section: string;
  page: number;
  label: Label;
  label_source: string;
  sentence: string;
  url: string;
}

export interface FilingSummary {
  ticker: string;
  fiscal_year: number;
  ai_sentences: number;
  concrete: number;
  vague: number;
  risk: number;
  context: number;
  /** concrete / (concrete + vague), or null when there are too few claims to say */
  substance: number | null;
}

export interface Company extends FilingSummary {
  name: string;
  prev: FilingSummary | null;
  /** change in substance since the previous filing, in fractional points */
  delta: number | null;
}

export interface MethodResult {
  macro_f1: number;
  accuracy: number;
  per_class_f1: Record<Label, number>;
}

export interface Metrics {
  n: number;
  folds: number;
  results: Record<string, MethodResult>;
}

export interface SiteData {
  companies: Company[];
  claims: Claim[];
  metrics: Metrics;
  updated: string | null;
  live: boolean;
}
