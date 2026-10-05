import { Copy, Download } from "lucide-react";
import { type ReactNode, useState } from "react";
import { letterUrl } from "../api/client";
import { Button, ButtonLink } from "../design/components/Button";
import { useI18n } from "../i18n";

type CopyState = "idle" | "copied" | "failed";

interface LetterTabProps {
  text: string;
  sessionId: string;
  finished: boolean;
  /** Replaces the .txt/.docx downloads (e.g. "Edit this letter" for a saved answer). */
  actions?: ReactNode;
}

/** The draft letter as plain text (line breaks kept), with copy and .txt/.docx download once the answer is done. */
export function LetterTab({ text, sessionId, finished, actions }: LetterTabProps) {
  const { t } = useI18n();
  const [copy, setCopy] = useState<CopyState>("idle");

  const copyLetter = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopy("copied");
    } catch {
      setCopy("failed");
    }
  };

  return (
    <div className="flex flex-col gap-4 text-base">
      <div className="border border-ink bg-raised px-5 py-6 font-reading text-[1.0625rem] leading-relaxed whitespace-pre-wrap sm:px-10 sm:py-8">
        {text}
      </div>
      {text.includes("[") && <p className="text-ink-muted">{t("letter_hint")}</p>}
      {finished ? (
        <div className="flex flex-wrap items-center gap-2">
          <Button icon={<Copy size={18} />} onClick={copyLetter}>
            {t("copy_letter")}
          </Button>
          {actions ?? (
            <>
              <ButtonLink href={letterUrl(sessionId, "txt")} download icon={<Download size={18} />}>
                {t("download_letter_txt")}
              </ButtonLink>
              <ButtonLink href={letterUrl(sessionId, "docx")} download icon={<Download size={18} />}>
                {t("download_letter_docx")}
              </ButtonLink>
            </>
          )}
          <span role="status" className="text-sm font-semibold text-ink-muted">
            {copy === "copied" && t("copied")}
            {copy === "failed" && t("copy_failed")}
          </span>
        </div>
      ) : (
        <p className="text-sm text-ink-muted">{t("letter_wait")}</p>
      )}
    </div>
  );
}
