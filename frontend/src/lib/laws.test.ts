import { describe, expect, it } from "vitest";
import { actSlugOf, type ActInfo } from "../api/laws";
import { parseLawQuery } from "./lawRef";
import { markSegments } from "./marks";

const act = (slug: string, name: string, unit: ActInfo["unit"] = "Section"): ActInfo => ({
  slug,
  name,
  unit,
  year: 2000,
  sections: 1,
  repealed: 0,
});
const ACTS = [
  act("constitution-of-kenya", "Constitution of Kenya", "Article"),
  act("employment-act", "Employment Act"),
  act("rent-restriction-act", "Rent Restriction Act"),
  act("land-act", "Land Act"),
  act("landlord-and-tenant-shops-act", "Landlord and Tenant (Shops) Act"),
];

describe("palette law references", () => {
  it.each([
    ["Employment s.41", "employment-act-41"],
    ["s 41 employment", "employment-act-41"],
    ["employment act section 41A", "employment-act-41a"],
    ["art 27", "constitution-of-kenya-27"],
    ["Article 27 constitution", "constitution-of-kenya-27"],
    ["rent 5", "rent-restriction-act-5"],
  ])("%s -> %s", (query, chunkId) => {
    expect(parseLawQuery(query, ACTS)[0]?.chunkId).toBe(chunkId);
  });

  it("names the Act without a number", () => {
    expect(parseLawQuery("employment", ACTS)).toEqual([{ slug: "employment-act", label: "Employment Act" }]);
  });

  it("a bare section never points at the Constitution, a bare article only at it", () => {
    expect(parseLawQuery("s 41", ACTS).map((t) => t.slug)).not.toContain("constitution-of-kenya");
    expect(parseLawQuery("section 41 constitution", ACTS)).toEqual([]);
    expect(parseLawQuery("art 27", ACTS).map((t) => t.slug)).toEqual(["constitution-of-kenya"]);
  });

  it("word prefixes match, unrelated words do not", () => {
    expect(parseLawQuery("land", ACTS).map((t) => t.slug)).toEqual(["land-act", "landlord-and-tenant-shops-act"]);
    expect(parseLawQuery("chapati recipe", ACTS)).toEqual([]);
    expect(parseLawQuery("", ACTS)).toEqual([]);
  });

  it("finds the Act slug of a chunk id (longest slug wins)", () => {
    expect(actSlugOf("land-act-12", ACTS)).toBe("land-act");
    expect(actSlugOf("landlord-and-tenant-shops-act-3", ACTS)).toBe("landlord-and-tenant-shops-act");
    expect(actSlugOf("unknown-1", ACTS)).toBeUndefined();
  });
});

describe("snippet marks", () => {
  it("uses code-point offsets, so astral characters do not shift marks", () => {
    const text = "😀 employer and 🙂 employee";
    const segments = markSegments(text, [
      [2, 10],
      [17, 25],
    ]);
    expect(segments.filter((s) => s.mark).map((s) => s.text)).toEqual(["employer", "employee"]);
    expect(segments.map((s) => s.text).join("")).toBe(text);
  });

  it("skips overlapping and out-of-range marks and keeps markup as text", () => {
    const text = "<b>wages</b> wages";
    const segments = markSegments(text, [
      [3, 8],
      [4, 6],
      [13, 99],
      [5, 5],
    ]);
    expect(segments).toEqual([
      { text: "<b>", mark: false },
      { text: "wages", mark: true },
      { text: "</b> wages", mark: false },
    ]);
  });
});
