// Labels for statutory units, shared by the laws pages.
import type { LawChunk, UnitType } from "../api/laws";
import type { Translate } from "../i18n";

/** "Section 41" / "Article 27" / "First Schedule". */
export function unitName(t: Translate, unitType: UnitType, num: string): string {
  if (unitType === "schedule") return num;
  return `${t(unitType === "article" ? "unit_article" : "unit_section")} ${num}`;
}

/** "Employment Act, section 41 (Termination of employment)": what Copy citation and Ask about this use. */
export function citation(t: Translate, chunk: LawChunk): string {
  const unit = unitName(t, chunk.unit_type, chunk.section_num);
  return `${chunk.act}, ${chunk.unit_type === "schedule" ? unit : unit.toLowerCase()} (${chunk.section_title})`;
}
