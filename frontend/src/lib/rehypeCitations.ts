// rehype plugin: wraps citations that resolve to a retrieved chunk in <a data-cite="chunk_id">, rendered as buttons.
import type { Element, ElementContent, Root, RootContent } from "hast";
import type { SourceChunk } from "../api/types";
import { findCitations } from "./citations";

const SKIP = new Set(["a", "code", "pre"]);

/** Text node split into plain text and citation links. */
function split(value: string, sources: SourceChunk[]): ElementContent[] {
  const parts: ElementContent[] = [];
  let at = 0;
  for (const span of findCitations(value, sources)) {
    if (span.start > at) parts.push({ type: "text", value: value.slice(at, span.start) });
    parts.push({
      type: "element",
      tagName: "a",
      properties: { href: `#source-${span.chunkId}`, dataCite: span.chunkId },
      children: [{ type: "text", value: value.slice(span.start, span.end) }],
    });
    at = span.end;
  }
  if (at < value.length) parts.push({ type: "text", value: value.slice(at) });
  return parts;
}

function walk(node: Root | Element, sources: SourceChunk[]): void {
  const children: (RootContent | ElementContent)[] = [];
  for (const child of node.children) {
    if (child.type === "text") {
      children.push(...split(child.value, sources));
      continue;
    }
    if (child.type === "element" && !SKIP.has(child.tagName)) walk(child, sources);
    children.push(child);
  }
  node.children = children as typeof node.children;
}

/** Plugin factory for react-markdown's rehypePlugins. */
export function rehypeCitations(options: { sources: SourceChunk[] }) {
  return (tree: Root): void => {
    if (options.sources.length) walk(tree, options.sources);
  };
}
