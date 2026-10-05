import { Download, FileX, History, Printer, Save, Trash2, UserRound } from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { getProfile, type Profile } from "../api/accounts";
import {
  deleteLetter,
  getLetter,
  getVersions,
  type Letter,
  letterExportUrl,
  putLetter,
  restoreVersion,
} from "../api/library";
import { useLibrary } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { Button, ButtonLink } from "../design/components/Button";
import { Dialog, DialogContent } from "../design/components/Dialog";
import { Card, EmptyState, Notice } from "../design/components/Display";
import { Field, TextArea } from "../design/components/Field";
import { useToast } from "../design/components/toastContext";
import { useLoad } from "../hooks/useLoad";
import { useI18n } from "../i18n";
import limits from "../limits.json";
import { formatDateTime, formatLetterDate } from "../lib/dates";
import { type FillResult, fillFromProfile, placeholders, segments } from "../lib/placeholders";

/** Letter workspace: edit, fill placeholders from the profile (with a preview), versions, export and print. */
export function LetterWorkspace() {
  const { t } = useI18n();
  const { id = "" } = useParams();
  const { result } = useLoad(`letter:${id}`, () => getLetter(id));
  if (result.status === "loading") return <p role="status">{t("loading")}</p>;
  if (result.status === "error") {
    return (
      <EmptyState icon={<FileX size={32} />} title={t(result.notFound ? "letter_not_found" : "library_error")}>
        <Link to="/library?tab=letters" className="font-semibold text-brand underline underline-offset-3">
          {t("library_open")}
        </Link>
      </EmptyState>
    );
  }
  return <Editor key={result.data.id} letter={result.data} />;
}

function Editor({ letter }: { letter: Letter }) {
  const { t, language } = useI18n();
  const toast = useToast();
  const navigate = useNavigate();
  const { bump } = useLibrary();
  const [saved, setSaved] = useState({ title: letter.title, body: letter.body, version: letter.version });
  const [title, setTitle] = useState(letter.title);
  const [body, setBody] = useState(letter.body);
  const [busy, setBusy] = useState(false);
  const [fill, setFill] = useState<FillResult | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const versions = useLoad(`versions:${letter.id}:${saved.version}`, () => getVersions(letter.id)).result;
  const profile = useLoad("profile", getProfile).result;
  const dirty = title !== saved.title || body !== saved.body;
  const left = useMemo(() => placeholders(body), [body]);

  const adopt = useCallback((next: Letter) => {
    setSaved({ title: next.title, body: next.body, version: next.version });
    setTitle(next.title);
    setBody(next.body);
  }, []);

  const save = useCallback(async () => {
    if (!dirty || busy || !title.trim()) return;
    setBusy(true);
    try {
      const next = await putLetter(letter.id, { title: title.trim(), body });
      adopt(next);
      bump();
      toast({ title: t("letter_saved", { n: next.version }), tone: "success" });
    } catch {
      toast({ title: t("library_error"), tone: "danger" });
    } finally {
      setBusy(false);
    }
  }, [adopt, body, bump, busy, dirty, letter.id, t, title, toast]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void save();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [save]);

  const restore = async (n: number) => {
    const next = await restoreVersion(letter.id, n);
    adopt(next);
    bump();
    toast({ title: t("version_restored", { n, m: next.version }), tone: "success" });
  };
  const openFill = (data: Profile) => setFill(fillFromProfile(body, data, formatLetterDate(new Date(), language)));
  const destroy = async () => {
    await deleteLetter(letter.id);
    bump();
    navigate("/library?tab=letters");
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink-muted">{t("library_tab_letters")}</p>
          <PageTitle>{saved.title}</PageTitle>
          {letter.conversation_id && (
            <Link
              to={`/ask/${letter.conversation_id}`}
              className="mt-1 inline-block font-semibold text-brand underline underline-offset-3"
            >
              {t("letter_from_chat")}
            </Link>
          )}
        </div>
        <Button variant="danger" icon={<Trash2 size={18} />} onClick={() => setConfirmDelete(true)}>
          {t("action_delete")}
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <Field
            label={t("letter_title_label")}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={limits.title_max_chars}
          />
          <TextArea
            label={t("letter_body_label")}
            hint={t("letter_placeholders_hint")}
            value={body}
            onChange={(e) => setBody(e.target.value)}
            maxLength={limits.letter_max_chars}
            className="min-h-80 font-reading"
            spellCheck
          />
          <div className="flex flex-wrap items-center gap-2">
            <Button variant="primary" icon={<Save size={18} />} onClick={() => void save()} disabled={!dirty || busy}>
              {t("letter_save")}
            </Button>
            <Button
              icon={<UserRound size={18} />}
              onClick={() => profile.status === "ok" && openFill(profile.data)}
              disabled={profile.status !== "ok" || left.length === 0}
            >
              {t("fill_from_profile")}
            </Button>
            <span role="status" className="text-sm font-semibold text-ink-muted">
              {dirty ? t("letter_unsaved") : t("version_label", { n: saved.version })}
            </span>
          </div>
          {left.length > 0 && <Notice tone="info">{t("letter_placeholders_left", { count: left.length })}</Notice>}

          <section aria-labelledby="letter-preview" className="flex flex-col gap-2">
            <h2 id="letter-preview" className="font-display-style text-xl text-ink">
              {t("letter_preview")}
            </h2>
            <div className="print-area rounded-md border border-line-subtle bg-raised px-5 py-6 font-reading leading-relaxed whitespace-pre-wrap text-ink sm:px-8">
              {segments(body).map((part, i) =>
                part.placeholder ? (
                  <mark key={i} className="rounded-sm bg-highlight px-0.5 text-ink">
                    {part.text}
                  </mark>
                ) : (
                  <span key={i}>{part.text}</span>
                ),
              )}
              <p className="print-only mt-8 border-t pt-2 text-sm">{t("disclaimer")}</p>
            </div>
          </section>
        </div>

        <div className="flex flex-col gap-6">
          <Card title={t("export_title")}>
            <div className="flex flex-col gap-2">
              {dirty && <p className="text-sm text-ink-muted">{t("letter_save_first")}</p>}
              <ButtonLink
                href={letterExportUrl(letter.id, "docx", language)}
                download
                icon={<Download size={18} />}
                aria-disabled={dirty}
                className={dirty ? "pointer-events-none opacity-55" : undefined}
              >
                {t("download_letter_docx")}
              </ButtonLink>
              <ButtonLink
                href={letterExportUrl(letter.id, "txt", language)}
                download
                icon={<Download size={18} />}
                aria-disabled={dirty}
                className={dirty ? "pointer-events-none opacity-55" : undefined}
              >
                {t("download_letter_txt")}
              </ButtonLink>
              <Button icon={<Printer size={18} />} onClick={() => window.print()}>
                {t("print_letter")}
              </Button>
            </div>
          </Card>
          <Card title={t("versions_title")}>
            <p className="mb-3 text-sm text-ink-muted">{t("versions_hint", { max: limits.letter_versions_max })}</p>
            {versions.status === "ok" && (
              <ol className="flex flex-col gap-1">
                {versions.data.map((version) => (
                  <li key={version.n} className="flex items-center justify-between gap-2 py-1">
                    <span className="min-w-0">
                      <span className="flex items-center gap-1 font-semibold text-ink">
                        <History aria-hidden="true" size={16} className="text-ink-muted" />
                        {t("version_label", { n: version.n })}
                      </span>
                      <span className="text-sm text-ink-muted">{formatDateTime(version.created_at, language)}</span>
                    </span>
                    {version.n === saved.version ? (
                      <span className="text-sm font-semibold text-ink-muted">{t("version_current")}</span>
                    ) : (
                      <Button variant="ghost" onClick={() => void restore(version.n)} disabled={busy}>
                        {t("version_restore")}
                        <span className="sr-only"> {t("version_label", { n: version.n })}</span>
                      </Button>
                    )}
                  </li>
                ))}
              </ol>
            )}
          </Card>
        </div>
      </div>

      {fill && (
        <FillDialog
          fill={fill}
          onApply={() => {
            setBody(fill.text);
            setFill(null);
          }}
          onClose={() => setFill(null)}
        />
      )}
      {confirmDelete && (
        <Dialog open onOpenChange={(next) => !next && setConfirmDelete(false)}>
          <DialogContent
            title={t("letter_delete_title")}
            description={t("letter_delete_body")}
            closeLabel={t("dismiss")}
          >
            <div className="flex justify-end gap-2">
              <Button onClick={() => setConfirmDelete(false)}>{t("cancel")}</Button>
              <Button variant="danger" icon={<Trash2 size={18} />} onClick={() => void destroy()}>
                {t("action_delete")}
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}

/** The replacements the profile would make, shown before anything changes. */
function FillDialog({ fill, onApply, onClose }: { fill: FillResult; onApply: () => void; onClose: () => void }) {
  const { t } = useI18n();
  const none = fill.changes.length === 0;
  return (
    <Dialog open onOpenChange={(next) => !next && onClose()}>
      <DialogContent title={t("fill_title")} description={none ? undefined : t("fill_intro")} closeLabel={t("dismiss")}>
        {none ? (
          <div className="flex flex-col gap-3">
            <p>{t("fill_none")}</p>
            <Link to="/settings?tab=profile" className="font-semibold text-brand underline underline-offset-3">
              {t("fill_profile_link")}
            </Link>
          </div>
        ) : (
          <div className="flex flex-col gap-4">
            <ul className="flex flex-col gap-2" aria-label={t("fill_title")}>
              {fill.changes.map((change) => (
                <li key={change.placeholder} className="rounded-md border border-line-subtle bg-surface px-3 py-2">
                  <del className="text-ink-muted">{change.placeholder}</del>
                  <span aria-hidden="true"> → </span>
                  <ins className="font-semibold text-ink no-underline">{change.value}</ins>
                  {change.count > 1 && (
                    <span className="ml-2 text-sm text-ink-muted">({t("fill_count", { count: change.count })})</span>
                  )}
                </li>
              ))}
            </ul>
            {fill.missing.length > 0 && (
              <p className="text-sm text-ink-muted">{t("fill_left", { list: fill.missing.join(", ") })}</p>
            )}
            <div className="flex justify-end gap-2">
              <Button onClick={onClose}>{t("cancel")}</Button>
              <Button variant="primary" onClick={onApply}>
                {t("fill_apply")}
              </Button>
            </div>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
