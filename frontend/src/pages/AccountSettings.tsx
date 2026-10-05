import { Download, Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import {
  changePassword,
  deleteAccount,
  EXPORT_URL,
  getPrefs,
  getProfile,
  type Prefs,
  type Profile,
  putPrefs,
  putProfile,
} from "../api/accounts";
import { useAuth, useSession } from "../app/contexts";
import { StrengthMeter } from "../components/StrengthMeter";
import { Button, ButtonLink } from "../design/components/Button";
import { Dialog, DialogClose, DialogContent, DialogTrigger } from "../design/components/Dialog";
import { Card, Notice } from "../design/components/Display";
import { Field, Select } from "../design/components/Field";
import { useToast } from "../design/components/toastContext";
import { ToggleGroup } from "../design/components/ToggleGroup";
import { type StringKey, useI18n } from "../i18n";
import { authMessage } from "../lib/authErrors";
import limits from "../limits.json";

const PROFILE_FIELDS: { key: keyof Profile; label: StringKey; autoComplete: string }[] = [
  { key: "name", label: "profile_name", autoComplete: "name" },
  { key: "address", label: "profile_address", autoComplete: "street-address" },
  { key: "phone", label: "profile_phone", autoComplete: "tel" },
  { key: "email", label: "profile_email", autoComplete: "email" },
  { key: "id_number", label: "profile_id", autoComplete: "off" },
];
const LOCK_MINUTES = [5, 10, 15, 30, 60];

/** Letter profile (stored encrypted). */
export function ProfileTab() {
  const { t } = useI18n();
  const [profile, setProfile] = useState<Profile | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    getProfile().then(setProfile, () => setStatus(t("auth_error_generic")));
  }, [t]);

  const save = async () => {
    if (!profile) return;
    try {
      setProfile(await putProfile(profile));
      setStatus(t("saved"));
    } catch {
      setStatus(t("auth_error_generic"));
    }
  };

  return (
    <Card title={t("settings_profile")}>
      <p className="mb-4 text-ink-muted">{t("profile_intro")}</p>
      {profile && (
        <form
          className="flex flex-col gap-4"
          onSubmit={(event) => {
            event.preventDefault();
            void save();
          }}
        >
          {PROFILE_FIELDS.map(({ key, label, autoComplete }) => (
            <Field
              key={key}
              label={t(label)}
              autoComplete={autoComplete}
              maxLength={200}
              value={profile[key]}
              onChange={(e) => setProfile({ ...profile, [key]: e.target.value })}
            />
          ))}
          <div className="flex items-center gap-3">
            <Button variant="primary" type="submit">
              {t("profile_save")}
            </Button>
            <span role="status" className="font-semibold text-ink-muted">
              {status}
            </span>
          </div>
        </form>
      )}
    </Card>
  );
}

/** History switch, auto-lock, password change, export and delete. */
export function PrivacyTab() {
  const { t } = useI18n();
  const [prefs, setPrefs] = useState<Prefs | null>(null);
  const [status, setStatus] = useState("");

  useEffect(() => {
    getPrefs().then(setPrefs, () => setStatus(t("auth_error_generic")));
  }, [t]);

  const update = async (change: Partial<Prefs>) => {
    if (!prefs) return;
    try {
      setPrefs(await putPrefs({ ...prefs, ...change }));
      setStatus(t("saved"));
    } catch {
      setStatus(t("auth_error_generic"));
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <Card title={t("settings_privacy")}>
        {prefs && (
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-2">
              <span aria-hidden="true" className="font-semibold text-ink">
                {t("privacy_history")}
              </span>
              <p className="text-sm text-ink-muted">{t("privacy_history_hint")}</p>
              <ToggleGroup
                label={t("privacy_history")}
                className="self-start"
                value={prefs.save_history ? "on" : "off"}
                onValueChange={(v) => void update({ save_history: v === "on" })}
                items={[
                  { value: "on", label: t("history_on") },
                  { value: "off", label: t("history_off") },
                ]}
              />
            </div>
            <Select
              label={t("privacy_autolock")}
              value={String(prefs.auto_lock_minutes)}
              onChange={(e) => void update({ auto_lock_minutes: Number(e.target.value) })}
              options={[...new Set([...LOCK_MINUTES, prefs.auto_lock_minutes])]
                .sort((a, b) => a - b)
                .map((n) => ({ value: String(n), label: t("minutes", { n }) }))}
              frameClassName="max-w-xs"
            />
            <p role="status" className="text-sm font-semibold text-ink-muted">
              {status}
            </p>
          </div>
        )}
      </Card>
      <PasswordCard />
      <Card title={t("privacy_export")}>
        <p className="mb-3 text-ink-muted">{t("privacy_export_hint")}</p>
        <ButtonLink href={EXPORT_URL} download icon={<Download size={18} />}>
          {t("privacy_export")}
        </ButtonLink>
      </Card>
      <DeleteCard />
    </div>
  );
}

function PasswordCard() {
  const { t } = useI18n();
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  const min = limits.password_min_chars;

  const submit = async () => {
    if (next.length < min) return setMessage({ ok: false, text: t("password_too_short", { min }) });
    try {
      await changePassword(current, next);
      setMessage({ ok: true, text: t("password_changed") });
      setCurrent("");
      setNext("");
    } catch (failure) {
      setMessage({ ok: false, text: authMessage(failure, t) });
    }
  };

  return (
    <Card title={t("password_change_title")}>
      <form
        className="flex flex-col gap-4"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <Field
          label={t("current_password")}
          type="password"
          autoComplete="current-password"
          value={current}
          onChange={(e) => setCurrent(e.target.value)}
        />
        <Field
          label={t("new_password_label")}
          hint={t("password_hint", { min })}
          type="password"
          autoComplete="new-password"
          value={next}
          onChange={(e) => setNext(e.target.value)}
        />
        <StrengthMeter password={next} />
        {message && (
          <div role={message.ok ? "status" : "alert"}>
            <Notice tone={message.ok ? "info" : "danger"}>{message.text}</Notice>
          </div>
        )}
        <Button type="submit" className="self-start" disabled={!current || !next}>
          {t("password_change_title")}
        </Button>
      </form>
    </Card>
  );
}

function DeleteCard() {
  const { t } = useI18n();
  const { apply } = useAuth();
  const { reset } = useSession();
  const toast = useToast();
  const navigate = useNavigate();
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const remove = async () => {
    try {
      apply(await deleteAccount(password));
      reset();
      toast({ title: t("delete_done"), tone: "success" });
      navigate("/");
    } catch (failure) {
      setError(authMessage(failure, t));
      setPassword("");
    }
  };

  return (
    <Card title={t("delete_title")}>
      <p className="mb-3 text-ink">{t("delete_body")}</p>
      <Dialog>
        <DialogTrigger asChild>
          <Button variant="danger" icon={<Trash2 size={18} />}>
            {t("delete_submit")}
          </Button>
        </DialogTrigger>
        <DialogContent title={t("delete_title")} description={t("delete_body")} closeLabel={t("cancel")}>
          <form
            className="flex flex-col gap-4"
            onSubmit={(event) => {
              event.preventDefault();
              void remove();
            }}
          >
            <Field
              label={t("delete_confirm_label")}
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              error={error ?? undefined}
            />
            <div className="flex flex-wrap justify-end gap-2">
              <DialogClose asChild>
                <Button>{t("cancel")}</Button>
              </DialogClose>
              <Button variant="danger" type="submit" disabled={!password}>
                {t("delete_submit")}
              </Button>
            </div>
          </form>
        </DialogContent>
      </Dialog>
    </Card>
  );
}
