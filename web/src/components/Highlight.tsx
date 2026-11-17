import type { ReactNode } from "react";
import type { Label } from "../types";
import { COLOR_WORD } from "../lib/labels";

export function Highlight({ label, children }: { label: Label; children: ReactNode }) {
  return (
    <mark className={label} title={COLOR_WORD[label]}>
      {children}
    </mark>
  );
}

export function Legend() {
  return (
    <p className="key">
      <Highlight label="concrete">green</Highlight> you could check it (a product, a number, a date)
      <Highlight label="vague">yellow</Highlight> a claim with nothing to check
      <Highlight label="risk">red</Highlight> AI as a risk
      <Highlight label="context">underline</Highlight> background
    </p>
  );
}
