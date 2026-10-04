import { useState } from "react";
import { letterUrl } from "../api/client";
import { useI18n } from "../i18n";
import { BUTTON_SECONDARY } from "./buttons";

type CopyState = "idle" | "copied" | "failed";

/** The draft letter as plain text (line breaks kept), with copy and .txt/.docx download once the answer is done. */
export function LetterTab({ text, sessionId, finished }: { text: string; sessionId: string; finished: boolean }) {
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
    <div className="space-y-4">
      <div className="rounded-lg border border-line bg-paper px-5 py-6 font-serif text-[1.0625rem] leading-relaxed whitespace-pre-wrap shadow-inner sm:px-8">
        {text}
      </div>
      {text.includes("[") && <p className="text-base text-muted">{t("letter_hint")}</p>}
      {finished ? (
        <div className="flex flex-wrap items-center gap-2">
          <button type="button" onClick={copyLetter} className={BUTTON_SECONDARY}>
            {t("copy_letter")}
          </button>
          <a href={letterUrl(sessionId, "txt")} download className={BUTTON_SECONDARY}>
            {t("download_letter_txt")}
          </a>
          <a href={letterUrl(sessionId, "docx")} download className={BUTTON_SECONDARY}>
            {t("download_letter_docx")}
          </a>
          <span role="status" className="text-sm font-medium text-muted">
            {copy === "copied" && t("copied")}
            {copy === "failed" && t("copy_failed")}
          </span>
        </div>
      ) : (
        <p className="text-sm text-muted">{t("letter_wait")}</p>
      )}
    </div>
  );
}
