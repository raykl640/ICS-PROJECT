import { X } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate } from "react-router";
import { login } from "../api/accounts";
import { useAuth } from "../app/contexts";
import { AuthForm } from "../components/AuthForm";
import { Button, IconButton } from "../design/components/Button";
import { Checkbox, Field } from "../design/components/Field";
import { useI18n } from "../i18n";
import { authMessage } from "../lib/authErrors";
import { forgetUsername, rememberedUsernames, rememberUsername } from "../lib/remembered";

/** Sign in, with optional usernames remembered on this device. */
export function SignIn() {
  const { t } = useI18n();
  const { refresh } = useAuth();
  const navigate = useNavigate();
  const [known, setKnown] = useState(rememberedUsernames);
  const [username, setUsername] = useState(known[0] ?? "");
  const [password, setPassword] = useState("");
  const [remember, setRemember] = useState(known.length > 0);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await login(username, password);
      if (remember) rememberUsername(result.user.username);
      else forgetUsername(result.user.username);
      await refresh();
      navigate("/");
    } catch (failure) {
      setError(authMessage(failure, t));
      setPassword("");
    } finally {
      setBusy(false);
    }
  };
  const forget = (name: string) => {
    forgetUsername(name);
    setKnown(rememberedUsernames());
  };

  return (
    <AuthForm
      title={t("signin_title")}
      error={error}
      onSubmit={submit}
      footer={
        <>
          <Link to="/recover" className="font-semibold text-brand underline underline-offset-3">
            {t("forgot_password")}
          </Link>
          <Link to="/signup" className="font-semibold text-brand underline underline-offset-3">
            {t("no_account")}
          </Link>
        </>
      }
    >
      {known.length > 0 && (
        <div className="flex flex-col gap-2">
          <p className="text-sm font-semibold text-ink-muted">{t("remembered_label")}</p>
          <ul className="flex flex-wrap gap-2">
            {known.map((name) => (
              <li key={name} className="flex items-center rounded-md border border-line bg-surface">
                <Button
                  variant="ghost"
                  className="border-0"
                  aria-pressed={username === name}
                  onClick={() => setUsername(name)}
                >
                  {name}
                </Button>
                <IconButton
                  label={t("forget_username", { username: name })}
                  icon={<X size={16} />}
                  onClick={() => forget(name)}
                />
              </li>
            ))}
          </ul>
        </div>
      )}
      <Field
        label={t("username_label")}
        autoComplete="username"
        value={username}
        onChange={(e) => setUsername(e.target.value)}
        required
      />
      <Field
        label={t("password_label")}
        type="password"
        autoComplete="current-password"
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        required
      />
      <Checkbox label={t("remember_username")} checked={remember} onChange={(e) => setRemember(e.target.checked)} />
      <Button variant="primary" type="submit" disabled={busy || !username || !password}>
        {t("sign_in")}
      </Button>
    </AuthForm>
  );
}
