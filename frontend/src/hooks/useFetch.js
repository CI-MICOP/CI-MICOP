import { useCallback, useEffect, useState } from "react";

/**
 * Runs `fetcher` on mount (and whenever `deps` change), exposing the
 * loading/success/error states every API-driven page needs. `fetcher`
 * must be stable across renders that shouldn't re-fetch - callers
 * typically wrap it in useCallback themselves or pass a plain closure
 * and list its real dependencies in `deps`.
 */
export function useFetch(fetcher, deps = []) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  const load = useCallback(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);
    fetcher()
      .then((result) => {
        if (!cancelled) setData(result);
      })
      .catch((err) => {
        if (!cancelled) setError(err);
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => load(), [load]);

  return { data, error, isLoading, reload: load };
}
