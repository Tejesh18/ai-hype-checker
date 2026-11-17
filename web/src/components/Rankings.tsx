import { useMemo, useState } from "react";
import type { Company, SiteData } from "../types";
import { logoUrl } from "../lib/companies";

type Key = "name" | "ai_sentences" | "concrete" | "vague" | "risk" | "substance" | "delta";

const COLUMNS: Array<{ key: Key; label: string; numeric?: boolean; wide?: boolean }> = [
  { key: "name", label: "Company" },
  { key: "ai_sentences", label: "AI sentences", numeric: true },
  { key: "concrete", label: "Green", numeric: true },
  { key: "vague", label: "Yellow", numeric: true },
  { key: "risk", label: "Red", numeric: true, wide: true },
  { key: "substance", label: "Substance", numeric: true },
  { key: "delta", label: "vs last year", numeric: true, wide: true },
];

function compare(a: Company, b: Company, key: Key): number {
  const x = a[key];
  const y = b[key];
  if (x === null) return 1; // nulls always last
  if (y === null) return -1;
  return typeof x === "string" ? x.localeCompare(y as string) : (x as number) - (y as number);
}

export function Rankings({ data }: { data: SiteData }) {
  const [key, setKey] = useState<Key>("ai_sentences");
  const [desc, setDesc] = useState(true);
  const rows = useMemo(
    () => [...data.companies].sort((a, b) => (compare(a, b, key) || 0) * (desc && a[key] !== null && b[key] !== null ? -1 : 1)),
    [data, key, desc],
  );
  const sortBy = (k: Key) => {
    setDesc(k === key ? !desc : k !== "name");
    setKey(k);
  };

  return (
    <div className="plain">
      <h2>Rankings</h2>
      <p className="sub">
        Substance is green ÷ (green + yellow): of the times a company talks up its own AI, how often it says something
        you could check. Red and underlined sentences don't count either way. Under 5 claims, no score.
      </p>
      <table>
        <thead>
          <tr>
            {COLUMNS.map((c) => (
              <th key={c.key} className={`${c.numeric ? "n" : ""} ${c.wide ? "hide-sm" : ""}`} onClick={() => sortBy(c.key)}>
                {c.label}
                {key === c.key ? (desc ? " ↓" : " ↑") : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((c) => (
            <tr key={c.ticker}>
              <td>
                <img src={logoUrl(c.ticker)} alt="" width={16} height={16} />
                <a href={`#/c/${c.ticker}`}>{c.name}</a>
              </td>
              <td className="n">{c.ai_sentences}</td>
              <td className="n">{c.concrete}</td>
              <td className="n">{c.vague}</td>
              <td className="n hide-sm">{c.risk}</td>
              <td className="n">{c.substance === null ? "–" : `${Math.round(c.substance * 100)}%`}</td>
              <td className="n hide-sm">{c.delta === null ? "" : `${c.delta > 0 ? "+" : ""}${Math.round(c.delta * 100)} pts`}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
