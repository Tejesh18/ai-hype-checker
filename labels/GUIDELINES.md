# Labeling guide

Every sentence that mentions AI gets exactly one label. The question behind
all four: **when this company talks about its own AI, could an outsider
check what it's saying?**

| Label | Use it when | Example |
|---|---|---|
| `concrete` | The company describes its own AI work with something checkable: a named product, model or feature, a number (dollars, users, %, speedup), a dated launch, or a specific use with a stated result. | "NVIDIA NIM ... delivers a 2.5x increase in token throughput." (NVDA FY2025) |
| `vague` | The company claims it uses, invests in, or is good at AI, but nothing in the sentence can be checked. | "We use, and expect to increasingly use, emerging technologies, including AI, across our operations." (BAC FY2025) |
| `risk` | AI shows up as a threat, uncertainty, liability, cost, regulation the company is exposed to, or something competitors or attackers might use. | "The increasing sophistication of AI technologies poses a greater risk of identity fraud." (WMT FY2025) |
| `context` | AI is mentioned but the company isn't claiming anything about itself: describing a law, the market, history, competitors, accounting definitions, forward-looking-statement boilerplate, or a section header. | "In the EU, ... the AI Act ... [is] rapidly changing privacy and cybersecurity compliance requirements." (JNJ FY2025) |

## Tie-breakers

These came up often enough to need a rule.

1. **A claim wrapped in a risk.** "The Company leverages machine learning ... across its business, and [that] may result in unintended consequences." Label the claim (`vague` here). The claim is what an investor reads as a statement about the company.
2. **Spending without a number.** "We are making significant investments in AI" is `vague`. "Capital expenditures were $11.34 billion ... mainly for AI-related capital expenditures" is `concrete`.
3. **A named product is enough.** "Meta AI is an assistant available across our apps, on Ray-Ban Meta AI glasses" is `concrete` even without a number, because you can go check that it exists.
4. **Financial results tied to AI.** "Gross margin decreased slightly driven by continued investments in AI infrastructure" is `concrete`: it's a reported number with a stated cause.
5. **Laws.** "We are subject to laws governing AI" is `risk` (exposure). "The EU AI Act regulates ..." with no link to the company is `context`.
6. **AI as the attacker.** Anything about criminals, fraudsters or hostile actors using AI is `risk`, even when the sentence also describes a defense.

## Why four labels and not two

The first pass used concrete/vague only. About two thirds of AI sentences in
a 10-K are risk disclosures, and calling those "vague" would punish banks for
being careful. The substance score only compares `concrete` against `vague`,
the sentences where a company is actually talking up its own AI.
