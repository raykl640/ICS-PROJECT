import { TriangleAlert } from "lucide-react";
import { Component, type ContextType, type ReactNode } from "react";
import { Button } from "../design/components/Button";
import { I18nContext } from "../i18n";

/** Last-resort screen for a rendering crash: says so plainly and offers a reload (settings live in storage). */
export class ErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  static contextType = I18nContext;
  declare context: ContextType<typeof I18nContext>;
  state = { failed: false };

  static getDerivedStateFromError(): { failed: boolean } {
    return { failed: true };
  }

  render(): ReactNode {
    if (!this.state.failed) return this.props.children;
    const { t } = this.context;
    return (
      <main className="mx-auto flex min-h-dvh max-w-xl flex-col items-start justify-center gap-4 px-4">
        <TriangleAlert aria-hidden="true" size={36} className="text-danger" />
        <h1 className="font-display-style text-3xl text-ink">{t("crash_title")}</h1>
        <p className="text-lg text-ink">{t("crash_body")}</p>
        <Button variant="primary" onClick={() => window.location.reload()}>
          {t("reload")}
        </Button>
      </main>
    );
  }
}
