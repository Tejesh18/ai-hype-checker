import { useEffect, useState } from "react";
import { Classifier, mentionsAI, splitSentences, type TfidfModel } from "../lib/classifier";
import type { Label } from "../types";
import { Highlight } from "./Highlight";

const EXAMPLE =
  "We are leveraging artificial intelligence across our business to drive efficiency and growth. " +
  "Our AI assistant, launched in March, now handles 40% of customer support chats. " +
  "Laws governing AI are evolving and could increase our compliance costs.";

const SECTIONS = ["Item 1. Business", "Item 1A. Risk Factors", "Item 7. Management's Discussion and Analysis"];

export function DraftChecker() {
  const [clf, setClf] = useState<Classifier | null>(null);
  const [text, setText] = useState(EXAMPLE);
  const [section, setSection] = useState(SECTIONS[0]);
  const [result, setResult] = useState<Array<{ s: string; label: Label | null }>>([]);

  useEffect(() => {
    fetch(`${import.meta.env.BASE_URL}model.json`)
      .then((r) => r.json() as Promise<TfidfModel>)
      .then((m) => setClf(new Classifier(m)));
  }, []);

  const check = () => {
    if (!clf) return;
    setResult(
      splitSentences(text).map((s) => ({
        s,
        // the model was trained on "section: sentence", so it gets the same here
        label: mentionsAI(s) && s.split(/\s+/).length >= 5 ? clf.predict(`${section}: ${s}`) : null,
      })),
    );
  };

  return (
    <div className="plain">
      <h2>Check your own text</h2>
      <p className="sub">
        Writing a disclosure or a press release? Paste it here and the same model marks it up. It runs in your browser;
        nothing is sent anywhere.
      </p>
      <p>
        <select value={section} onChange={(e) => setSection(e.target.value)}>
          {SECTIONS.map((s) => (
            <option key={s}>{s}</option>
          ))}
        </select>{" "}
        <button className="btn" onClick={check} disabled={!clf}>
          {clf ? "Highlight it" : "Loading model…"}
        </button>
      </p>
      <textarea value={text} onChange={(e) => setText(e.target.value)} />
      {result.length > 0 && (
        <p className="out">
          {result.map(({ s, label }, i) => (
            <span key={i}>{label ? <Highlight label={label}>{s}</Highlight> : s} </span>
          ))}
        </p>
      )}
    </div>
  );
}
