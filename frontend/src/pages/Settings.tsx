import type { ReactNode } from "react";
import type { UiLanguage } from "../api/types";
import { useSettings } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { type ContrastChoice, type MotionChoice, TEXT_SIZES, type ThemeChoice } from "../app/settings";
import { Card } from "../design/components/Display";
import { ToggleGroup } from "../design/components/ToggleGroup";
import { useI18n } from "../i18n";

function Setting({ label, hint, children }: { label: string; hint?: string; children: ReactNode }) {
  return (
    <div className="flex flex-col gap-2 border-t border-line-subtle py-4 first:border-t-0 first:pt-0">
      <span aria-hidden="true" className="font-semibold text-ink">
        {label}
      </span>
      {hint && <p className="text-sm text-ink-muted">{hint}</p>}
      <div className="overflow-x-auto">{children}</div>
    </div>
  );
}

/** Appearance and language, saved in this browser only. */
export function Settings() {
  const { t } = useI18n();
  const { settings, update } = useSettings();
  return (
    <div className="flex max-w-3xl flex-col gap-6">
      <div>
        <PageTitle>{t("settings_title")}</PageTitle>
        <p className="mt-2 text-ink-muted">{t("settings_intro")}</p>
      </div>
      <Card title={t("settings_appearance")}>
        <Setting label={t("theme_label")}>
          <ToggleGroup
            label={t("theme_label")}
            value={settings.theme}
            onValueChange={(theme: ThemeChoice) => update({ theme })}
            items={[
              { value: "system", label: t("theme_system") },
              { value: "light", label: t("theme_light") },
              { value: "dark", label: t("theme_dark") },
            ]}
          />
        </Setting>
        <Setting label={t("contrast_label")} hint={t("settings_contrast_hint")}>
          <ToggleGroup
            label={t("contrast_label")}
            value={settings.contrast}
            onValueChange={(contrast: ContrastChoice) => update({ contrast })}
            items={[
              { value: "system", label: t("theme_system") },
              { value: "standard", label: t("contrast_standard") },
              { value: "more", label: t("contrast_more") },
            ]}
          />
        </Setting>
        <Setting label={t("text_size_label")}>
          <ToggleGroup
            label={t("text_size_label")}
            value={settings.text}
            onValueChange={(text) => update({ text })}
            items={TEXT_SIZES.map((size) => ({ value: size, label: t(`text_${size}`) }))}
          />
          <p className="mt-3 font-reading text-lg text-ink">{t("text_preview")}</p>
        </Setting>
        <Setting label={t("motion_label")} hint={t("settings_motion_hint")}>
          <ToggleGroup
            label={t("motion_label")}
            value={settings.motion}
            onValueChange={(motion: MotionChoice) => update({ motion })}
            items={[
              { value: "system", label: t("motion_system") },
              { value: "reduce", label: t("motion_reduce") },
            ]}
          />
        </Setting>
      </Card>
      <Card title={t("settings_language")}>
        <Setting label={t("ui_language")} hint={t("settings_language_hint")}>
          <ToggleGroup
            label={t("ui_language")}
            value={settings.language}
            onValueChange={(language: UiLanguage) => update({ language })}
            items={[
              { value: "en", label: t("language_en") },
              { value: "sw", label: t("language_sw") },
            ]}
          />
        </Setting>
      </Card>
    </div>
  );
}
