import { useEffect, useState } from "react";
import type { SiteData } from "./types";
import { loadData } from "./lib/data";
import { useRoute } from "./lib/useRoute";
import { About } from "./components/About";
import { CompanyPage } from "./components/CompanyPage";
import { DraftChecker } from "./components/DraftChecker";
import { FilingWall } from "./components/FilingWall";
import { Rankings } from "./components/Rankings";

const NAV = [
  { href: "#/", page: "home", label: "The filings" },
  { href: "#/rankings", page: "rankings", label: "Rankings" },
  { href: "#/draft", page: "draft", label: "Check your own text" },
  { href: "#/about", page: "about", label: "About" },
];

export default function App() {
  const route = useRoute();
  const [data, setData] = useState<SiteData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData().then(setData, (e: Error) => setError(e.message));
  }, []);

  const current = route.page === "company" ? "home" : route.page;

  return (
    <>
      <header className="bar">
        <a className="name" href="#/">AI Hype Checker</a>
        <nav>
          {NAV.map((n) => (
            <a key={n.page} href={n.href} className={n.page === current ? "on" : ""}>
              {n.label}
            </a>
          ))}
        </nav>
      </header>

      <main>
        {error && <p>Couldn't load the data ({error}).</p>}
        {!data && !error && <p className="sub">Loading filings…</p>}
        {data && route.page === "home" && <FilingWall data={data} />}
        {data && route.page === "company" && <CompanyPage data={data} ticker={route.ticker} />}
        {data && route.page === "rankings" && <Rankings data={data} />}
        {route.page === "draft" && <DraftChecker />}
        {data && route.page === "about" && <About data={data} />}
      </main>

      <footer>
        Tejesh Annavarapu · filings from SEC EDGAR
        {data?.updated ? `, checked every hour (last ${data.updated})` : ""}
        {data && !data.live ? " · showing the saved snapshot" : ""} · not investment advice
      </footer>
    </>
  );
}
