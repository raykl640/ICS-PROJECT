import type { Health } from "../api/types";
import { isEngineError, type SessionError } from "../hooks/session";
import { type StringKey, useI18n } from "../i18n";
import { Banner } from "./Banner";
import { BUTTON_PRIMARY } from "./buttons";

/** The user-facing message key, and whether asking again could help. */
function describe(error: SessionError): { key: StringKey; retry: boolean; detail?: string } {
  if (error.kind === "disconnected") return { key: "error_disconnected", retry: true };
  if (isEngineError(error)) return { key: "error_engine", retry: true };
  if (error.kind === "http" && error.status === 429) return { key: "error_rate", retry: true };
  if (error.code === "busy") return { key: "error_busy", retry: true };
  if (error.kind === "http" && error.status === 422)
    return { key: "error_generic", retry: false, detail: error.message };
  return { key: "error_generic", retry: true, detail: error.message };
}

/** A failed question: what happened, the health details when the engine is down, and a retry. */
export function ErrorState({
  error,
  health,
  onRetry,
}: {
  error: SessionError;
  health: Health | null;
  onRetry: () => void;
}) {
  const { t } = useI18n();
  const { key, retry, detail } = describe(error);
  const healthMessage = isEngineError(error) ? health?.error?.message : undefined;
  return (
    <div role="alert" className="space-y-4">
      <Banner tone="danger" title={t("error_title")}>
        <p className="mt-1">{t(key)}</p>
        {detail && <p className="mt-1 text-sm">{detail}</p>}
        {healthMessage && (
          <p className="mt-2 text-sm">
            {t("health_details")} <code className="break-words">{healthMessage}</code>
          </p>
        )}
      </Banner>
      {retry && (
        <button type="button" onClick={onRetry} className={BUTTON_PRIMARY}>
          {t("retry")}
        </button>
      )}
    </div>
  );
}

/** Page-level notice while /api/health reports degraded. */
export function HealthBanner({ health }: { health: Health | null }) {
  const { t } = useI18n();
  if (!health || health.status === "ok") return null;
  return (
    <Banner tone="warn" title={t("health_title")}>
      {health.error && (
        <p className="mt-1 text-sm">
          {t("health_details")} <code className="break-words">{health.error.message}</code>
        </p>
      )}
    </Banner>
  );
}
