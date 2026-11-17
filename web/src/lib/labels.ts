import type { Label } from "../types";

/** How each label is shown on the site: as a highlighter color. */
export const COLOR_WORD: Record<Label, string> = {
  concrete: "green",
  vague: "yellow",
  risk: "red",
  context: "underlined",
};
