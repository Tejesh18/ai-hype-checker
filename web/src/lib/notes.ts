import type { Company } from "../types";
import { MIN_CLAIMS } from "./data";

export interface Note {
  ticker: string;
  text: string;
}

const pct = (x: number) => `${Math.round(x * 100)}%`;

/**
 * The "things I noticed" list on the home page. Computed from the data so
 * it stays true when a new filing changes the numbers.
 */
export function notes(cs: Company[]): Note[] {
  const out: Note[] = [];

  const withPrev = cs.filter((c) => c.prev);
  const grew = [...withPrev].sort((a, b) => b.ai_sentences - b.prev!.ai_sentences - (a.ai_sentences - a.prev!.ai_sentences))[0];
  if (grew?.prev) {
    const green = grew.concrete ? `Only ${grew.concrete} are green.` : "Not one is green.";
    out.push({ ticker: grew.ticker, text: `${grew.name} went from ${grew.prev.ai_sentences} AI sentences to ${grew.ai_sentences} in one year. ${green}` });
  }

  const best = cs.filter((c) => c.substance !== null).sort((a, b) => b.concrete - a.concrete)[0];
  if (best) {
    out.push({ ticker: best.ticker, text: `${best.name} has the most green by far: ${best.concrete} sentences that name an actual product, number or launch.` });
  }

  const drop = cs.filter((c) => c.delta !== null).sort((a, b) => a.delta! - b.delta!)[0];
  if (drop?.prev && drop.delta! < 0) {
    out.push({
      ticker: drop.ticker,
      text: `${drop.name} more than doubled its AI talk (${drop.prev.ai_sentences} to ${drop.ai_sentences}) while the share you could check fell from ${pct(drop.prev.substance!)} to ${pct(drop.substance!)}.`,
    });
  }

  for (const c of cs.filter((x) => x.ai_sentences >= 15 && x.concrete + x.vague === 0)) {
    out.push({ ticker: c.ticker, text: `${c.name} mentions AI ${c.ai_sentences} times and never once talks up its own. It's all red and underline.` });
  }

  const buzz = cs.find((c) => c.substance === 0 && c.vague >= MIN_CLAIMS);
  if (buzz) out.push({ ticker: buzz.ticker, text: `${buzz.name}'s report has ${buzz.vague} yellow sentences about "AI-powered tools" and no green at all.` });

  return out;
}
