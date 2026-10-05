import { createContext, useContext } from "react";
import type { RequestedLanguage } from "../api/client";
import type { Health } from "../api/types";
import type { SessionState } from "../hooks/session";
import type { Settings } from "./settings";

export interface SettingsValue {
  settings: Settings;
  update: (change: Partial<Settings>) => void;
}

export const SettingsContext = createContext<SettingsValue | null>(null);

/** Current settings and a setter that persists them. */
export function useSettings(): SettingsValue {
  const value = useContext(SettingsContext);
  if (!value) throw new Error("useSettings needs a SettingsProvider");
  return value;
}

export interface SessionValue {
  state: SessionState;
  submit: (question: string, language: RequestedLanguage) => Promise<void>;
  retry: () => void;
  reset: () => void;
  health: Health | null;
  refreshHealth: () => void;
}

export const SessionContext = createContext<SessionValue | null>(null);

/** The app-wide question session (one question at a time) and backend health. */
export function useSession(): SessionValue {
  const value = useContext(SessionContext);
  if (!value) throw new Error("useSession needs a SessionProvider");
  return value;
}
