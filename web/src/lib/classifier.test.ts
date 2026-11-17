import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { Classifier, mentionsAI, splitSentences, type TfidfModel } from "./classifier";
import { toCompanies } from "./data";

// parity.json is written by `aiwash site`: every labeled sentence and what
// scikit-learn predicts for it.
const model = JSON.parse(readFileSync("public/model.json", "utf8")) as TfidfModel;
const parity = JSON.parse(readFileSync("src/lib/__fixtures__/parity.json", "utf8")) as { texts: string[]; sklearn: string[] };

describe("Classifier", () => {
  it("agrees with scikit-learn on every labeled sentence", () => {
    const clf = new Classifier(model);
    const mismatches = parity.texts.filter((t, i) => clf.predict(t) !== parity.sklearn[i]);
    expect(mismatches).toEqual([]);
  });
});

describe("mentionsAI", () => {
  it("matches the acronym only as a word, case-sensitively", () => {
    expect(mentionsAI("We use AI in stores.")).toBe(true);
    expect(mentionsAI("We maintain our said aims.")).toBe(false);
    expect(mentionsAI("Machine learning models")).toBe(true);
  });
});

describe("splitSentences", () => {
  it("splits on sentence ends", () => {
    expect(splitSentences("One here. Two there.")).toEqual(["One here.", "Two there."]);
  });
});

describe("toCompanies", () => {
  const row = (ticker: string, year: number, concrete: number, vague: number) => ({
    ticker, fiscal_year: year, ai_sentences: concrete + vague, concrete, vague, risk: 0, context: 0,
    substance: concrete + vague ? concrete / (concrete + vague) : null,
  });

  it("keeps the latest filing and compares it to the year before", () => {
    const [c] = toCompanies([row("TSLA", 2024, 6, 2), row("TSLA", 2025, 10, 17)]);
    expect(c.fiscal_year).toBe(2025);
    expect(c.prev?.fiscal_year).toBe(2024);
    expect(c.delta).toBeCloseTo(10 / 27 - 0.75);
  });

  it("refuses to score a company with fewer than 5 claims", () => {
    const [c] = toCompanies([row("KO", 2025, 0, 1)]);
    expect(c.substance).toBeNull();
  });
});
