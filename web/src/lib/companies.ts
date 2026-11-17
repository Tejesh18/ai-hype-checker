// Display names and the domain used to fetch each company's site icon.
export const COMPANIES: Record<string, { name: string; domain: string }> = {
  AAPL: { name: "Apple", domain: "apple.com" },
  MSFT: { name: "Microsoft", domain: "microsoft.com" },
  NVDA: { name: "NVIDIA", domain: "nvidia.com" },
  AMZN: { name: "Amazon", domain: "amazon.com" },
  GOOGL: { name: "Alphabet", domain: "google.com" },
  META: { name: "Meta", domain: "meta.com" },
  TSLA: { name: "Tesla", domain: "tesla.com" },
  JPM: { name: "JPMorgan Chase", domain: "jpmorganchase.com" },
  GS: { name: "Goldman Sachs", domain: "goldmansachs.com" },
  BAC: { name: "Bank of America", domain: "bankofamerica.com" },
  XOM: { name: "ExxonMobil", domain: "exxonmobil.com" },
  JNJ: { name: "Johnson & Johnson", domain: "jnj.com" },
  WMT: { name: "Walmart", domain: "walmart.com" },
  KO: { name: "Coca-Cola", domain: "coca-colacompany.com" },
  NFLX: { name: "Netflix", domain: "netflix.com" },
};

export const companyName = (ticker: string) => COMPANIES[ticker]?.name ?? ticker;

// Google's public favicon service, so no logo files live in this repo.
export const logoUrl = (ticker: string) =>
  `https://www.google.com/s2/favicons?domain=${COMPANIES[ticker]?.domain ?? "sec.gov"}&sz=64`;
