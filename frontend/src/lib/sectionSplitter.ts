// TypeScript port of backend/app/generation/parse.py (SectionSplitter); keep the two in step.
// Splits the streamed answer into its three headed sections, tolerant of header variants.

export type Section = "rights" | "steps" | "letter";
export type Sections = Record<Section, string>;

export const SECTIONS: readonly Section[] = ["rights", "steps", "letter"];

export interface SectionDelta {
  section: Section;
  text: string;
}

export interface ParsedResponse extends Sections {
  formatOk: boolean;
}

const NAMES: Record<string, Section> = {
  "rights explanation": "rights",
  "recommended steps": "steps",
  "formal letter": "letter",
};
// "## Rights Explanation", "**RIGHTS EXPLANATION**", "### RIGHTS EXPLANATION:", "**Formal Letter:** Dear ..." (inline).
const HEADER =
  /^[ \t#*_]*(?<name>rights explanation|recommended steps|formal letter)[ \t*_]*(?::[ \t*_]*(?<rest>.*?))?[ \t]*$/i;
const LEADING_MARKUP = /^[ \t#*_]*/;
const HEADER_TAIL = /^[ \t*_]*(?::.*)?$/;
const TRAILING_MARKUP = /[ \t*_]+$/;

export const emptySections = (): Sections => ({ rights: "", steps: "", letter: "" });

/** True while an unfinished line could still turn out to be a header line. */
function couldBeHeader(partial: string): boolean {
  const core = partial.replace(LEADING_MARKUP, "").toLowerCase();
  return Object.keys(NAMES).some(
    (name) =>
      name.startsWith(core.replace(TRAILING_MARKUP, "")) ||
      (core.startsWith(name) && HEADER_TAIL.test(core.slice(name.length))),
  );
}

/** Feed streamed tokens; body text is emitted as soon as its line cannot be a header, header lines switch section.
 * Text before the first header goes to rights; a repeated header appends to its section. */
export class SectionSplitter {
  private section: Section = "rights";
  private pending = "";
  private inBodyLine = false;
  private readonly parts: Record<Section, string[]> = { rights: [], steps: [], letter: [] };
  private readonly seenOrder: Section[] = [];

  /** The section that text currently goes to. */
  get current(): Section {
    return this.section;
  }

  /** Sections whose header has appeared, in order of first appearance. */
  get seen(): readonly Section[] {
    return this.seenOrder;
  }

  /** Consume one token and return the section deltas it completes. */
  feed(token: string): SectionDelta[] {
    return token
      .split(/(?<=\n)/)
      .filter(Boolean)
      .flatMap((piece) => this.consume(piece));
  }

  /** The text emitted so far per section (unstripped; a held-back possible header is not included). */
  snapshot(): Sections {
    return { rights: this.parts.rights.join(""), steps: this.parts.steps.join(""), letter: this.parts.letter.join("") };
  }

  /** Flush any unfinished line and return the trimmed sections; formatOk iff all three headers appeared. */
  finalize(): ParsedResponse {
    if (this.pending) {
      const line = this.pending;
      this.pending = "";
      this.line(line);
    }
    const sections = this.snapshot();
    return {
      rights: sections.rights.trim(),
      steps: sections.steps.trim(),
      letter: sections.letter.trim(),
      formatOk: this.seenOrder.length === SECTIONS.length,
    };
  }

  /** Handle a piece holding at most one newline, at its end. */
  private consume(piece: string): SectionDelta[] {
    const endsLine = piece.endsWith("\n");
    if (this.inBodyLine) {
      this.inBodyLine = !endsLine;
      return this.emit(piece);
    }
    this.pending += piece;
    if (endsLine) {
      const line = this.pending;
      this.pending = "";
      return this.line(line);
    }
    if (!couldBeHeader(this.pending)) {
      const text = this.pending;
      this.pending = "";
      this.inBodyLine = true;
      return this.emit(text);
    }
    return [];
  }

  /** Classify a complete (buffered) line: switch section on a header, else emit it as body text. */
  private line(line: string): SectionDelta[] {
    const body = line.replace(/\n$/, "");
    const match = HEADER.exec(body);
    if (!match?.groups) return this.emit(line);
    this.section = NAMES[match.groups.name.toLowerCase()];
    if (!this.seenOrder.includes(this.section)) this.seenOrder.push(this.section);
    const rest = match.groups.rest;
    return rest ? this.emit(rest + line.slice(body.length)) : [];
  }

  /** Append text to the current section. */
  private emit(text: string): SectionDelta[] {
    this.parts[this.section].push(text);
    return [{ section: this.section, text }];
  }
}

/** Split a complete answer into its sections. */
export function splitSections(text: string): ParsedResponse {
  const splitter = new SectionSplitter();
  splitter.feed(text);
  return splitter.finalize();
}
