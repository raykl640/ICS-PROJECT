import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { recover } from "../api/accounts";
import { useAuth } from "../app/contexts";
import { AuthForm } from "../components/AuthForm";
import { RecoveryCode } from "../components/RecoveryCode";
import { StrengthMeter } from "../components/StrengthMeter";
import { Button } from "../design/components/Button";
import { Field } from "../design/components/Field";
import { useI18n } from "../i18n";
import { authMessage } from "../lib/authErrors";
import limits from "../limits.json";

/** Reset the password with the recovery code; a new code is shown once afterwards. */
export function Recover() {
  const { t } = useI18n();
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", code: "", password: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ code: string; username: string } | null>(null);
  const min = limits.password_min_chars;

  const submit = async () => {
    if (form.password.length < min) return setError(t("password_too_short", { min }));
    if (form.confirm !== form.password) return setError(t("password_mismatch"));
    setBusy(true);
    setError(null);
    try {
      const result = await recover(form.username, form.code, form.password);
      setDone({ code: result.recovery_code ?? "", username: result.user.username });
      void refresh();
    } catch (failure) {
      setError(authMessage(failure, t, true));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="mx-auto max-w-xl border-2 border-ink bg-surface p-5 sm:p-7">
        <RecoveryCode code={done.code} username={done.username} onDone={() => navigate("/")} />
      </div>
    );
  }

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: event.target.value }));
  return (
    <AuthForm
      title={t("recover_title")}
      intro={t("recover_body")}
      error={error}
      onSubmit={submit}
      footer={
        <Link to="/signin" className="font-semibold text-brand underline underline-offset-3">
          {t("have_account")}
        </Link>
      }
    >
      <Field
        label={t("username_label")}
        autoComplete="username"
        value={form.username}
        onChange={set("username")}
        required
      />
      <Field
        label={t("recovery_code_label")}
        autoComplete="off"
        spellCheck={false}
        value={form.code}
        onChange={set("code")}
        required
        className="font-mono uppercase"
      />
      <Field
        label={t("new_password_label")}
        hint={t("password_hint", { min })}
        type="password"
        autoComplete="new-password"
        value={form.password}
        onChange={set("password")}
        required
      />
      <StrengthMeter password={form.password} />
      <Field
        label={t("password_confirm")}
        type="password"
        autoComplete="new-password"
        value={form.confirm}
        onChange={set("confirm")}
        required
      />
      <Button variant="primary" type="submit" disabled={busy}>
        {t("recover_submit")}
      </Button>
    </AuthForm>
  );
}
