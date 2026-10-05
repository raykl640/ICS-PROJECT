import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { getMe, type Me } from "../api/accounts";
import { AuthContext } from "./contexts";

/** At most one activity report per this many ms (the server's idle timer only needs minute precision). */
export const ACTIVITY_PING_MS = 60_000;

/** Sign-in state from /api/auth/me; reports activity and re-checks when the server's auto-lock is due. */
export function AuthProvider({ children }: { children: ReactNode }) {
  const [me, setMe] = useState<Me | null>(null);
  const lastPing = useRef(0);

  const refresh = useCallback(() => getMe().then(setMe, () => setMe({ user: null, locked: false, lock_in_s: 0 })), []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const unlocked = Boolean(me?.user && !me.locked);
  const lockIn = me?.lock_in_s ?? 0;

  // Activity (keys, pointer) resets the server's idle timer, reported at most once a minute.
  useEffect(() => {
    if (!unlocked) return;
    const onActivity = () => {
      const now = Date.now();
      if (now - lastPing.current < ACTIVITY_PING_MS) return;
      lastPing.current = now;
      getMe(true).then(setMe, () => {});
    };
    window.addEventListener("keydown", onActivity);
    window.addEventListener("pointerdown", onActivity);
    return () => {
      window.removeEventListener("keydown", onActivity);
      window.removeEventListener("pointerdown", onActivity);
    };
  }, [unlocked]);

  // Ask the server again just after the moment it would auto-lock; it decides.
  useEffect(() => {
    if (!unlocked || lockIn <= 0) return;
    const timer = setTimeout(() => void refresh(), (lockIn + 1) * 1000);
    return () => clearTimeout(timer);
  }, [unlocked, lockIn, refresh]);

  const value = useMemo(() => ({ me, apply: setMe, refresh }), [me, refresh]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}
