import type { Claim, Company } from "../types";
import { logoUrl } from "../lib/companies";

/** A filing drawn as a page of highlighter strokes, one per AI sentence, in document order. */
export function FilingSheet({ company, claims }: { company: Company; claims: Claim[] }) {
  const tally = company.ai_sentences
    ? `${company.ai_sentences} AI sentences, ${company.concrete} green`
    : "doesn't mention AI";
  return (
    <a className="sheet" href={`#/c/${company.ticker}`}>
      <div className="who">
        <img src={logoUrl(company.ticker)} alt="" width={20} height={20} />
        {company.name}
      </div>
      <div className="form">10-K · fiscal {company.fiscal_year}</div>
      <div className="strokes">
        {claims.slice(0, 60).map((c, i) => (
          // stroke length varies with the sentence so the page doesn't look ruled
          <i key={i} className={c.label} style={{ width: `${35 + ((c.sentence.length * 7) % 65)}%` }} />
        ))}
      </div>
      <div className="tally">{tally}</div>
    </a>
  );
}
