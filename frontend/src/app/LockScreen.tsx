import { Lock } from "lucide-react";
import { useState } from "react";
import { logout, unlock } from "../api/accounts";
import { AuthForm } from "../components/AuthForm";
import { Button } from "../design/components/Button";
import { Field } from "../design/components/Field";
import { useI18n } from "../i18n";
import { authMessage } from "../lib/authErrors";
import { useAuth, useSession } from "./contexts";

/** Shown instead of the whole app while signed in but locked: only the password, or sign out. */
export function LockScreen({ name }: { name: string }) {
  const { t } = useI18n();
  const { apply, refresh } = useAuth();
  const { reset } = useSession();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await unlock(password);
      await refresh();
    } catch (failure) {
      setError(authMessage(failure, t));
      setPassword("");
    } finally {
      setBusy(false);
    }
  };
  const signOut = async () => {
    apply(await logout());
    reset();
  };

  return (
    <main className="flex min-h-dvh items-center justify-center bg-canvas px-4 py-10">
      <div className="flex w-full flex-col items-center gap-4">
        <Lock aria-hidden="true" size={36} className="text-accent" />
        <AuthForm
          title={t("lock_title")}
          intro={t("lock_body", { name })}
          error={error}
          onSubmit={submit}
          footer={
            <Button variant="ghost" className="self-start" onClick={() => void signOut()}>
              {t("sign_out")}
            </Button>
          }
        >
          <Field
            label={t("password_label")}
            type="password"
            autoComplete="current-password"
            autoFocus
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
          <Button variant="primary" type="submit" disabled={busy || !password}>
            {t("unlock_submit")}
          </Button>
        </AuthForm>
      </div>
    </main>
  );
}
