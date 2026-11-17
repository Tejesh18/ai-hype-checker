import type { SiteData } from "../types";

const METHOD_NAMES: Record<string, string> = {
  rules: "Keyword rules",
  tfidf: "TF-IDF + logistic regression",
  embed: "Embeddings + logistic regression (what the site uses)",
  finetune: "Fine-tuned small model",
};

export function About({ data }: { data: SiteData }) {
  const m = data.metrics;
  return (
    <div className="plain">
      <h2>About</h2>
      <p>
        I'm Tejesh. I work closely with equity research analysts, building the portal they use to connect with their
        clients, and one thing I keep hearing is that clients want to invest in companies that are actually doing AI,
        not just talking about it. Meanwhile "AI" now shows up in every annual report. The SEC has started fining
        companies for overstating their AI, and its letters to companies mostly ask one thing: be specific. Whether a
        sentence is specific enough to check turned out to be something you can measure.
      </p>
      <p>
        Every hour a small job on AWS checks the SEC for new annual reports from these companies, pulls out every
        sentence that mentions AI, and marks it up with a model trained on {m.n} labeled sentences. A new filing shows
        up here a few minutes after it's filed.
      </p>
      <p className="sub">
        How each approach did against the labeled sentences, {m.folds}-fold cross-validation (1.0 is perfect):
      </p>
      <table>
        <thead>
          <tr>
            <th>Method</th>
            <th className="n">Overall F1</th>
            <th className="n">Green</th>
            <th className="n">Yellow</th>
            <th className="n hide-sm">Red</th>
          </tr>
        </thead>
        <tbody>
          {Object.entries(m.results).map(([k, r]) => (
            <tr key={k}>
              <td>{METHOD_NAMES[k] ?? k}</td>
              <td className="n">{r.macro_f1.toFixed(2)}</td>
              <td className="n">{r.per_class_f1.concrete.toFixed(2)}</td>
              <td className="n">{r.per_class_f1.vague.toFixed(2)}</td>
              <td className="n hide-sm">{r.per_class_f1.risk.toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      <p className="sub">
        The model is right about 7 times in 10 on the labels that matter, so read the numbers as a strong hint, not a
        verdict, and click through to the filing. Code, labels and a longer write-up:{" "}
        <a href="https://github.com/Tejesh18/ai-hype-checker">github.com/Tejesh18/ai-hype-checker</a>.
      </p>
    </div>
  );
}
