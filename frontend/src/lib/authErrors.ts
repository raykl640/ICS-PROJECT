import { ApiError } from "../api/client";
import type { Translate } from "../i18n";

/** A user-facing message for a failed auth/account call (server messages are English-only, so codes are mapped). */
export function authMessage(error: unknown, t: Translate, recovering = false): string {
  if (!(error instanceof ApiError)) return t("auth_error_generic");
  switch (error.code) {
    case "invalid_credentials":
      return t(recovering ? "auth_error_recover" : "auth_error_invalid");
    case "locked_out":
      return t("auth_error_locked", { seconds: error.retryAfter ?? 30 });
    case "username_taken":
      return t("auth_error_taken");
    case "invalid_username":
      return t("auth_error_username");
    case "rate_limited":
      return t("auth_error_rate");
    default:
      return t("auth_error_generic");
  }
}
