import { Copy, Download, Printer } from "lucide-react";
import { useState } from "react";
import { Button } from "../design/components/Button";
import { Checkbox } from "../design/components/Field";
import { useI18n } from "../i18n";

/** The recovery code, shown once: copy, print or save as .txt; Continue stays disabled until "I saved it" is ticked. */
export function RecoveryCode({ code, username, onDone }: { code: string; username: string; onDone: () => void }) {
  const { t } = useI18n();
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);
  const fileText = `${t("recovery_file_heading", { username })}\n\n${code}\n`;

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
    } catch {
      setCopied(false);
    }
  };
  const save = () => {
    const url = URL.createObjectURL(new Blob([fileText], { type: "text/plain" }));
    const link = Object.assign(document.createElement("a"), { href: url, download: `hakiai-recovery-${username}.txt` });
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <section aria-labelledby="recovery-title" className="flex flex-col gap-4">
      <h2 id="recovery-title" className="font-display-style text-xl text-ink">
        {t("recovery_title")}
      </h2>
      <p className="text-ink">{t("recovery_body")}</p>
      <div className="print-area border-4 border-double border-accent bg-raised p-5 text-center">
        <p className="sr-only print:not-sr-only">{t("recovery_file_heading", { username })}</p>
        <p className="font-mono text-2xl font-semibold tracking-wider text-ink" data-testid="recovery-code">
          {code.split("-").map((group, i) => (
            <span key={i} className="inline-block whitespace-nowrap">
              {i > 0 && "-"}
              {group}
            </span>
          ))}
        </p>
      </div>
      <div className="flex flex-wrap items-center gap-2">
        <Button icon={<Copy size={18} />} onClick={copy}>
          {t("recovery_copy")}
        </Button>
        <Button icon={<Printer size={18} />} onClick={() => window.print()}>
          {t("recovery_print")}
        </Button>
        <Button icon={<Download size={18} />} onClick={save}>
          {t("recovery_save")}
        </Button>
        <span role="status" className="text-sm font-semibold text-ink-muted">
          {copied && t("copied")}
        </span>
      </div>
      <Checkbox label={t("recovery_saved_check")} checked={saved} onChange={(e) => setSaved(e.target.checked)} />
      <Button variant="primary" disabled={!saved} onClick={onDone} className="self-start">
        {t("recovery_continue")}
      </Button>
    </section>
  );
}
