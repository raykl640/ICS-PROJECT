import { useMemo } from "react";
import Markdown, { type Components } from "react-markdown";
import type { SourceChunk } from "../api/types";
import { useI18n } from "../i18n";
import { rehypeCitations } from "../lib/rehypeCitations";

interface Props {
  text: string;
  sources: SourceChunk[];
  onCite: (chunkId: string) => void;
}

/** Model markdown, rendered safely: raw HTML stays literal text, no images, no live links; citations jump to sources. */
export function AnswerMarkdown({ text, sources, onCite }: Props) {
  const { t } = useI18n();
  const components = useMemo<Components>(
    () => ({
      a: ({ node, children }) => {
        const chunkId = node?.properties?.dataCite;
        if (typeof chunkId !== "string") return <span>{children}</span>;
        const first = node?.children[0];
        const citation = first?.type === "text" ? first.value : chunkId;
        return (
          <button
            type="button"
            className="cite"
            aria-label={t("cite_jump", { citation })}
            onClick={() => onCite(chunkId)}
          >
            {children}
          </button>
        );
      },
    }),
    [onCite, t],
  );
  const plugins = useMemo(() => [[rehypeCitations, { sources }] as const], [sources]);
  return (
    <div className="prose-answer">
      <Markdown rehypePlugins={plugins as never} components={components} disallowedElements={["img"]} unwrapDisallowed>
        {text}
      </Markdown>
    </div>
  );
}
