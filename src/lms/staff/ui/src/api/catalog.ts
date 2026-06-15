import { api } from "./client";
import type { CatalogSearchHit } from "./types";

export async function searchLendableCatalog(query: string): Promise<CatalogSearchHit[]> {
  return api<CatalogSearchHit[]>(
    `/api/v1/catalog/catalogs/search/lendable?q=${encodeURIComponent(query)}`,
  );
}
