import { useEffect, useState } from "react";
import { api } from "../api";
import { parseLocal } from "./dates";

let cache = null;

/** All terms, oldest first (fetched once per page load). */
export function useTerms() {
  const [terms, setTerms] = useState(cache);
  useEffect(() => {
    if (cache) return;
    api.get("/terms").then((t) => {
      cache = t;
      setTerms(t);
    });
  }, []);
  return terms;
}

/** The term a student is most likely planning: the next one to start, else the latest. */
export function defaultPlanningTerm(terms) {
  if (!terms?.length) return null;
  const now = new Date();
  return terms.find((t) => parseLocal(t.start_date) > now) ?? terms[terms.length - 1];
}
