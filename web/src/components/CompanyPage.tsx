import { useMemo, useState } from "react";
import type { Claim, Label, SiteData } from "../types";
import { claimsFor } from "../lib/data";
import { logoUrl } from "../lib/companies";
import { COLOR_WORD } from "../lib/labels";
import { Highlight } from "./Highlight";

const ORDER: Label[] = ["vague", "concrete", "risk", "context"];
const tidy = (s: string) => s.replace(/^[\s•·\-–]+/, "");
const sectionName = (s: string) => (s === "Cover" ? "opening pages" : s.replace(/^Item (\w+)\. /, "Item $1, "));

export function CompanyPage({ data, ticker }: { data: SiteData; ticker: string }) {
  const company = data.companies.find((c) => c.ticker === ticker);
  const claims = useMemo(() => (company ? claimsFor(data, company) : []), [data, company]);
  const [hidden, setHidden] = useState<Set<Label>>(new Set());

  const byPage = useMemo(() => {
    const pages = new Map<number, Claim[]>();
    for (const c of claims) if (!hidden.has(c.label)) pages.set(c.page, [...(pages.get(c.page) ?? []), c]);
    return [...pages.entries()].sort(([a], [b]) => a - b);
  }, [claims, hidden]);

  if (!company) return <p>No filing for {ticker}. <a href="#/">Back to all filings</a></p>;

  const own = company.concrete + company.vague;
  const toggle = (l: Label) =>
    setHidden((h) => {
      const next = new Set(h);
      if (next.has(l)) next.delete(l);
      else next.add(l);
      return next;
    });

  return (
    <>
      <a className="back" href="#/">&larr; all filings</a>
      <article className="doc">
        <header className="doc-head">
          <img src={logoUrl(company.ticker)} alt="" width={32} height={32} />
          <div>
            <h1>{company.name}</h1>
            <div className="form">Form 10-K · fiscal {company.fiscal_year} · filed with the SEC</div>
          </div>
        </header>

        <p className="summary">
          {company.ai_sentences === 0 && <>{company.name} doesn't mention AI in this report.</>}
          {company.ai_sentences > 0 && own === 0 && (
            <>
              {company.ai_sentences} sentences about AI, and not one of them talks up {company.name}'s own AI. It's all
              risk warnings and background.
            </>
          )}
          {own > 0 && (
            <>
              {company.ai_sentences} sentences about AI. When {company.name} talks up its own AI,{" "}
              <Highlight label={company.concrete ? "concrete" : "risk"}>
                {company.concrete} of {own}
              </Highlight>{" "}
              say something you could actually check.
            </>
          )}
        </p>
        {company.prev && (
          <p className="sub">
            The year before: {company.prev.ai_sentences} AI sentences, {company.prev.concrete} green,{" "}
            {company.prev.vague} yellow.
          </p>
        )}

        <div className="filters">
          {ORDER.map((l) => {
            const n = claims.filter((c) => c.label === l).length;
            if (!n) return null;
            return (
              <button key={l} className={hidden.has(l) ? "off" : ""} onClick={() => toggle(l)}>
                <Highlight label={l}>{COLOR_WORD[l]}</Highlight> {n}
              </button>
            );
          })}
        </div>

        {byPage.map(([page, cs]) => (
          <section className="page" key={page}>
            <div className="pno">
              page {page}
              <small>{sectionName(cs[0].section)}</small>
            </div>
            <div>
              {cs.map((c) => (
                <p key={c.sentence}>
                  <Highlight label={c.label}>{tidy(c.sentence)}</Highlight>
                </p>
              ))}
              <a className="src" href={cs[0].url} target="_blank" rel="noopener">
                open the filing
              </a>
            </div>
          </section>
        ))}
      </article>
    </>
  );
}
