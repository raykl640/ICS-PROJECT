import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { TooltipProvider } from "../design/components/Overlay";
import { ToastProvider } from "../design/components/Toast";
import { useMediaQuery } from "../design/useMediaQuery";
import { isEngineError } from "../hooks/session";
import { useHealth } from "../hooks/useHealth";
import { useQuerySession } from "../hooks/useQuerySession";
import { I18nContext, makeTranslate, useI18n } from "../i18n";
import { measure, recordSpeed } from "../lib/eta";
import { SessionContext, SettingsContext } from "./contexts";
import { applyAttributes, htmlAttributes, loadSettings, saveSettings, type Settings } from "./settings";

/** Settings state: persisted on change and mirrored onto <html> (following OS changes for "system" choices). */
function SettingsProvider({ children }: { children: ReactNode }) {
  const [settings, setSettings] = useState<Settings>(loadSettings);
  const systemDark = useMediaQuery("(prefers-color-scheme: dark)");
  const systemMore = useMediaQuery("(prefers-contrast: more)");

  useLayoutEffect(() => {
    applyAttributes(document.documentElement, htmlAttributes(settings, systemDark, systemMore));
  }, [settings, systemDark, systemMore]);

  const update = useCallback((change: Partial<Settings>) => {
    setSettings((current) => {
      const next = { ...current, ...change };
      saveSettings(next);
      return next;
    });
  }, []);

  const i18n = useMemo(
    () => ({ language: settings.language, t: makeTranslate(settings.language) }),
    [settings.language],
  );
  const value = useMemo(() => ({ settings, update }), [settings, update]);
  return (
    <SettingsContext.Provider value={value}>
      <I18nContext.Provider value={i18n}>{children}</I18nContext.Provider>
    </SettingsContext.Provider>
  );
}

/** The question session lives above the routes, so an answer keeps streaming while the user moves around. */
function SessionProvider({ children }: { children: ReactNode }) {
  const { state, submit, retry, reset } = useQuerySession();
  const { health, refresh } = useHealth();

  useEffect(() => {
    if (isEngineError(state.error)) refresh();
  }, [state.error, refresh]);

  // Learn this computer's answer speed from each cleanly streamed answer (numbers only), once per session.
  const recorded = useRef<string | null>(null);
  useEffect(() => {
    if (state.phase !== "done" || recorded.current === state.sessionId) return;
    recorded.current = state.sessionId;
    const sample = measure(state);
    if (sample) recordSpeed(sample);
  }, [state]);

  const value = useMemo(
    () => ({ state, submit, retry, reset, health, refreshHealth: refresh }),
    [state, submit, retry, reset, health, refresh],
  );
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

/** Everything the screens rely on: settings + i18n, tooltips, toasts and the session. */
export function Providers({ children }: { children: ReactNode }) {
  return (
    <SettingsProvider>
      <ToastsWithLabels>
        <SessionProvider>{children}</SessionProvider>
      </ToastsWithLabels>
    </SettingsProvider>
  );
}

function ToastsWithLabels({ children }: { children: ReactNode }) {
  const { t } = useI18n();
  return (
    <TooltipProvider delayDuration={400}>
      <ToastProvider closeLabel={t("dismiss")} regionLabel={t("notifications")}>
        {children}
      </ToastProvider>
    </TooltipProvider>
  );
}
