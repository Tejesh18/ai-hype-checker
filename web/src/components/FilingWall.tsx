import { useMemo, useState } from "react";
import type { SiteData } from "../types";
import { claimsFor } from "../lib/data";
import { notes } from "../lib/notes";
import { FilingSheet } from "./FilingSheet";
import { Legend } from "./Highlight";

export function FilingWall({ data }: { data: SiteData }) {
  const [query, setQuery] = useState("");
  const shown = useMemo(() => {
    const q = query.trim().toLowerCase();
    return data.companies
      .filter((c) => !q || c.name.toLowerCase().includes(q) || c.ticker.toLowerCase().startsWith(q))
      .sort((a, b) => b.ai_sentences - a.ai_sentences);
  }, [data, query]);

  return (
    <>
      <div className="intro">
        <p>
          Every big company says it's doing AI now. I wanted to know how much of that is real, so I went through what
          they actually told the SEC in their annual reports, sentence by sentence, with a highlighter.
        </p>
      </div>
      <Legend />
      <input
        className="find"
        type="search"
        placeholder="Find a company"
        aria-label="Find a company"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
      />
      <div className="wall">
        {shown.map((c) => (
          <FilingSheet key={c.ticker} company={c} claims={claimsFor(data, c)} />
        ))}
      </div>
      <div className="notes">
        <h3>Things I noticed</h3>
        {notes(data.companies).map((n) => (
          <p key={n.text}>
            {n.text} <a href={`#/c/${n.ticker}`}>See the filing &rarr;</a>
          </p>
        ))}
      </div>
    </>
  );
}
