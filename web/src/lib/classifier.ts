import type { Label } from "../types";

/**
 * The TF-IDF + logistic regression model from src/aiwash/model.py, ported
 * so the "check your own text" page runs in the browser.
 *
 * Mirrors sklearn's TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True):
 * lowercase, tokens of 2+ word characters, unigrams and bigrams,
 * 1 + log(tf), times idf, L2-normalized; then one dot product per class.
 * classifier.test.ts checks it against sklearn on every labeled sentence.
 */
export interface TfidfModel {
  classes: Label[];
  vocab: string[];
  idf: number[];
  coef: number[][];
  intercept: number[];
}

const TOKEN = /[\p{L}\p{N}_]{2,}/gu;

export class Classifier {
  private readonly model: TfidfModel;
  private readonly index: Map<string, number>;

  constructor(model: TfidfModel) {
    this.model = model;
    this.index = new Map(model.vocab.map((w, i) => [w, i]));
  }

  private features(text: string): Array<[number, number]> {
    const tokens = text.toLowerCase().match(TOKEN) ?? [];
    const grams = [...tokens];
    for (let i = 0; i < tokens.length - 1; i++) grams.push(`${tokens[i]} ${tokens[i + 1]}`);

    const counts = new Map<number, number>();
    for (const g of grams) {
      const j = this.index.get(g);
      if (j !== undefined) counts.set(j, (counts.get(j) ?? 0) + 1);
    }
    const x: Array<[number, number]> = [];
    let norm = 0;
    for (const [j, n] of counts) {
      const v = (1 + Math.log(n)) * this.model.idf[j];
      x.push([j, v]);
      norm += v * v;
    }
    norm = Math.sqrt(norm) || 1;
    return x.map(([j, v]) => [j, v / norm]);
  }

  predict(text: string): Label {
    const x = this.features(text);
    const scores = this.model.coef.map((row, k) => x.reduce((s, [j, v]) => s + row[j] * v, this.model.intercept[k]));
    return this.model.classes[scores.indexOf(Math.max(...scores))];
  }
}

const AI_ACRONYM = /\b(?:AI|GenAI|LLMs?)\b|generative AI/;
const AI_PHRASE = /artificial intelligence|machine learning|large language models?|neural network/i;

/** Same rule the pipeline uses to decide a sentence is "about AI". */
export const mentionsAI = (s: string) => AI_ACRONYM.test(s) || AI_PHRASE.test(s);

export const splitSentences = (text: string) =>
  text.replace(/\n/g, " ").split(/(?<=[.!?])\s+(?=[A-Z("“])/).filter((s) => s.trim());
