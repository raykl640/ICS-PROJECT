import { useI18n } from "../i18n";

/** Wordmark with the section-sign mark and a thin Kenyan tricolour rule. */
export function Header() {
  const { t } = useI18n();
  return (
    <header>
      <div aria-hidden="true" className="tricolour h-1.5" />
      <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-4 sm:px-6 lg:px-8">
        <span
          aria-hidden="true"
          className="grid size-10 place-items-center rounded-lg bg-brand font-serif text-2xl leading-none font-bold text-on-brand"
        >
          §
        </span>
        <div>
          <p className="font-serif text-2xl leading-none font-bold tracking-tight">HakiAI</p>
          <p className="mt-1 text-sm text-muted">{t("brand_tagline")}</p>
        </div>
      </div>
    </header>
  );
}
