import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { register } from "../api/accounts";
import { useAuth } from "../app/contexts";
import { AuthForm } from "../components/AuthForm";
import { RecoveryCode } from "../components/RecoveryCode";
import { StrengthMeter } from "../components/StrengthMeter";
import { Button } from "../design/components/Button";
import { Notice } from "../design/components/Display";
import { Field } from "../design/components/Field";
import { useI18n } from "../i18n";
import { authMessage } from "../lib/authErrors";
import limits from "../limits.json";

/** Create an account, then show the recovery code once (cannot continue without ticking "I saved it"). */
export function SignUp() {
  const { t } = useI18n();
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [form, setForm] = useState({ username: "", displayName: "", password: "", confirm: "" });
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<{ code: string; username: string } | null>(null);
  const min = limits.password_min_chars;
  const tooShort = form.password.length > 0 && form.password.length < min;
  const mismatch = form.confirm.length > 0 && form.confirm !== form.password;

  const submit = async () => {
    if (form.password.length < min) return setError(t("password_too_short", { min }));
    if (form.confirm !== form.password) return setError(t("password_mismatch"));
    setBusy(true);
    setError(null);
    try {
      const result = await register(form.username, form.password, form.displayName);
      setDone({ code: result.recovery_code ?? "", username: result.user.username });
      void refresh();
    } catch (failure) {
      setError(authMessage(failure, t));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <div className="mx-auto max-w-xl rounded-lg border border-line-subtle bg-surface p-5 shadow-raised sm:p-7">
        <RecoveryCode code={done.code} username={done.username} onDone={() => navigate("/")} />
      </div>
    );
  }

  const set = (key: keyof typeof form) => (event: { target: { value: string } }) =>
    setForm((f) => ({ ...f, [key]: event.target.value }));
  return (
    <AuthForm
      title={t("signup_title")}
      intro={<Notice tone="warn">{t("signup_warning")}</Notice>}
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
        hint={t("username_hint")}
        autoComplete="username"
        value={form.username}
        onChange={set("username")}
        maxLength={limits.username_max_chars}
        required
      />
      <Field
        label={t("display_name_label")}
        autoComplete="name"
        value={form.displayName}
        onChange={set("displayName")}
        maxLength={60}
      />
      <Field
        label={t("password_label")}
        hint={t("password_hint", { min })}
        error={tooShort ? t("password_too_short", { min }) : undefined}
        type="password"
        autoComplete="new-password"
        value={form.password}
        onChange={set("password")}
        required
      />
      <StrengthMeter password={form.password} />
      <Field
        label={t("password_confirm")}
        error={mismatch ? t("password_mismatch") : undefined}
        type="password"
        autoComplete="new-password"
        value={form.confirm}
        onChange={set("confirm")}
        required
      />
      <Button variant="primary" type="submit" disabled={busy}>
        {t("signup_submit")}
      </Button>
    </AuthForm>
  );
}
