import { LogIn, UserPlus, UserRound } from "lucide-react";
import { Link } from "react-router";
import { useAuth } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { useI18n } from "../i18n";

const TILE = "target flex items-center gap-3 rounded-sm border-2 px-4 py-3 text-lg font-semibold motion-colors";

/** First choice: create an account, sign in, or carry on as a guest (always offered). */
export function Welcome() {
  const { t } = useI18n();
  const { me } = useAuth();
  return (
    <div className="mx-auto flex max-w-xl flex-col gap-5">
      <PageTitle>{t("welcome_title")}</PageTitle>
      <p className="text-lg text-ink">{t("welcome_body")}</p>
      {me?.user && <p className="font-semibold text-brand">{t("signed_in_as", { name: me.user.display_name })}</p>}
      <div className="flex flex-col gap-3">
        <Link
          to="/signup"
          className={`${TILE} border-brand bg-brand text-brand-ink shadow-[0_3px_0_var(--hk-ink)] hover:border-ink hover:bg-ink hover:text-canvas`}
        >
          <UserPlus aria-hidden="true" size={20} />
          {t("create_account")}
        </Link>
        <Link to="/signin" className={`${TILE} border-ink text-ink hover:bg-highlight`}>
          <LogIn aria-hidden="true" size={20} />
          {t("sign_in")}
        </Link>
        <Link to="/" className={`${TILE} border-ink text-ink hover:bg-highlight`}>
          <UserRound aria-hidden="true" size={20} />
          {t("continue_guest")}
        </Link>
      </div>
      <p className="text-ink-muted">{t("welcome_guest_note")}</p>
    </div>
  );
}
