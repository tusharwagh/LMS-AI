import { useState } from "react";

import { searchLendableCatalog } from "@/api/catalog";
import type { CatalogSearchHit } from "@/api/types";
import { Alert } from "@/components/Alert/Alert";
import { Button } from "@/components/Button/Button";
import { Card, ListRow } from "@/components/Card/Card";
import styles from "@/components/Card/Card.module.css";
import { PageShell } from "@/components/PageShell/PageShell";
import {
  FormField,
  inputClassName,
  mutedClassName,
} from "@/components/FormField/FormField";

export function CatalogSearch() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<CatalogSearchHit[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function search() {
    const q = query.trim();
    if (!q) return;
    setBusy(true);
    setError(null);
    setResults(null);
    try {
      const hits = await searchLendableCatalog(q);
      setResults(hits);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed");
      setResults([]);
    } finally {
      setBusy(false);
    }
  }

  return (
    <PageShell>
      <Card>
      {error ? <Alert variant="error">{error}</Alert> : null}
      <FormField
        id="catalog-query"
        label="Search published titles with available copies"
      >
        <input
          id="catalog-query"
          className={inputClassName()}
          placeholder="Title, ISBN, call number"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void search();
          }}
        />
      </FormField>
      <Button onClick={() => void search()} disabled={busy}>
        {busy ? "Searching…" : "Search"}
      </Button>
      <div style={{ marginTop: "1rem" }}>
        {results === null ? null : results.length === 0 ? (
          <p className={mutedClassName()}>No published titles with available copies.</p>
        ) : (
          results.map((hit) => (
            <ListRow key={hit.catalog.title}>
              <strong>{hit.catalog.title}</strong>
              <div className={styles.meta}>
                {hit.lendable_holdings.length} available cop
                {hit.lendable_holdings.length === 1 ? "y" : "ies"}
              </div>
              <ul className={styles.meta}>
                {hit.lendable_holdings.map((h) => (
                  <li key={h.barcode}>
                    Barcode {h.barcode}
                    {h.shelf_location ? ` · Shelf ${h.shelf_location}` : ""}
                  </li>
                ))}
              </ul>
            </ListRow>
          ))
        )}
      </div>
      </Card>
    </PageShell>
  );
}
