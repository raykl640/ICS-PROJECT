import type { Sections } from "./sectionSplitter";

// Same rule as backend/app/letter.py: the model sometimes ends with the disclaimer line; the UI shows its own.
const DISCLAIMER_LINE = /^.*legal information,? not legal advice.*$/gim;

/** Sections with any model-written disclaimer line removed. */
export function withoutDisclaimer(sections: Sections): Sections {
  const strip = (text: string) => text.replace(DISCLAIMER_LINE, "").trimEnd();
  return { rights: strip(sections.rights), steps: strip(sections.steps), letter: strip(sections.letter) };
}
