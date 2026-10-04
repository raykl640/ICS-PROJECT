import { useCallback, useEffect, useState } from "react";
import { getHealth } from "../api/client";
import type { Health } from "../api/types";

/** /api/health on mount and on demand (null until known or when unreachable). */
export function useHealth(): { health: Health | null; refresh: () => void } {
  const [health, setHealth] = useState<Health | null>(null);
  const refresh = useCallback(() => {
    getHealth().then(setHealth, () => setHealth(null));
  }, []);
  useEffect(refresh, [refresh]);
  return { health, refresh };
}
