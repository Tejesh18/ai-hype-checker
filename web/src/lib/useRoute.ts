import { useEffect, useState } from "react";

export type Route =
  | { page: "home" }
  | { page: "company"; ticker: string }
  | { page: "rankings" }
  | { page: "draft" }
  | { page: "about" };

// Hash routes (#/c/WMT) because GitHub Pages can't rewrite paths to index.html.
function parse(hash: string): Route {
  const [page, arg] = hash.replace(/^#\/?/, "").split("/");
  if (page === "c" && arg) return { page: "company", ticker: arg.toUpperCase() };
  if (page === "rankings" || page === "draft" || page === "about") return { page };
  return { page: "home" };
}

export function useRoute(): Route {
  const [route, setRoute] = useState(() => parse(window.location.hash));
  useEffect(() => {
    const onChange = () => {
      setRoute(parse(window.location.hash));
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return route;
}
