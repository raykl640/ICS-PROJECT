# HakiAI v2 design directions (M11)

**Outcome (M11 gate):** "Mahakama colours + Jua radius". M12 made it the only theme (frontend/src/design/tokens.css:
Mahakama palette and fonts, with Jua's 8/14/22 px corners). The Jua and Kitabu screenshots below remain as the record of
the choice; the style guide now lives at /styleguide in dev builds, without a direction switcher.

Three visual directions for the v2 interface, built from the same components so that only the design tokens differ. Pick
one, or a mix, and write the choice into `.gates/M11-design.ok`. M12 builds the whole app on it.

**How to look at them**
- Screenshots: `docs/design/<direction>/<screen>-<width>-<mode>.png`, where the screens are `home`, `conversation` and
  `reader`, the widths are 1280 and 375 px, and the modes are light and dark. Each direction also has
  `conversation-375-light-sources.png`, which shows the sources panel as a bottom sheet on a phone.
- Live (after M12): `cd frontend && npm run dev`, then open <http://localhost:5173/styleguide> for every component on the
  chosen theme. The M11 switcher and mock screens were removed with the unchosen directions.

All text in the mock screens is placeholder (lorem ipsum, "Sample Act (placeholder)", "Section 0.x"). None of it is
statute text and none of it is a claim about Kenyan law.

## What is the same in all three

Colours are named by role (canvas, surface, raised, sunken, ink, ink-muted, line, brand, brand-ink, accent, success, warn,
danger, info, focus, highlight, plus a decorative line-subtle) and defined once per direction in
`frontend/src/design/themes/`. Each direction has a light and a dark palette, and each palette has a "more contrast"
variant. A test checks every text/background pair the components use:
- Standard contrast: reading text at least 7:1 (WCAG AAA), other text at least 4.5:1, borders and focus rings at least 3:1.
- More contrast: 10:1, 7:1 and 4.5:1.

All 12 combinations pass. Text size has four steps (SM to XL), and the whole interface scales with it. Click and tap
targets stay at least 44 px at every size. Animations last at most 180 ms and switch off when the system asks for reduced
motion. There is no blur and no glass effect. Fonts are bundled with the app, so nothing is downloaded at run time.

## Mahakama: forest green, brass and ivory

Mahakama feels authoritative and calm, like a well-kept court register. Headings and statute text use Source Serif 4 and
the interface uses Source Sans 3, a humanist sans that stays clear at small sizes on low-resolution laptop screens.
- Light: deep forest-green ink on ivory (ink on canvas 14.6:1); a forest-green primary button (7.8:1 for its label); brass
  for the accent marks and the focus ring (6.3:1 and 5.9:1); borders 3.8:1.
- Dark: ivory on a near-black green (14.8:1); a soft green primary (label 9.2:1); a brighter brass accent (8.5:1).
- Trade-offs: it carries the most trust, and its green continues the v1 identity and echoes the Kenyan flag. It can
  also feel formal, even official, to someone already nervous about a legal problem. Corners are small (4–10 px) and
  the overall look is restrained.

## Jua: terracotta, sand and charcoal

Jua is the warmest and most approachable: rounded shapes (8–22 px corners) and Nunito, a rounded sans, for the interface
and headings. Statute text uses Lora, a warm serif, so the law still reads as a document.
- Light: charcoal on sand (14.0:1); a terracotta primary button (label 6.1:1); a deep teal accent and focus ring (6.6:1
  and 6.0:1); borders 4.0:1.
- Dark: warm off-white on a brown-charcoal background (15.4:1); a coral primary (label 7.3:1); a light teal accent (8.6:1).
- Trade-offs: it is the friendliest for a first visit and for low-confidence readers. Terracotta sits close to the
  colours people read as "warning". Danger is a distinct crimson and always comes with text, but some primary buttons may
  still look alarming. Nunito is wide, so lines hold fewer words, and long answers get taller.

## Kitabu: paper, ink and one oxblood accent

Kitabu is an editorial, near-monochrome direction that puts reading first, like a printed statute book. Headings and
statute text use Literata, a serif designed for long reading on screens; the interface uses IBM Plex Sans. Corners are
almost square (2–4 px).
- Light: near-black on paper white (17.6:1). The primary button is black with a white label (17.4:1). The single oxblood
  accent also serves as the focus ring (9.1:1 and 8.7:1). Borders are 3.5:1.
- Dark: off-white on near-black (15.8:1); the primary button is inverted (15.0:1); a soft rose accent (7.7:1).
- Trade-offs: it gives the best long-form reading and the quietest screens, and has the highest contrast of the three.
  Primary buttons look like every other dark element, so "what to do next" stands out less. The accent and danger share
  the oxblood hue, so danger must always carry an icon or words (the components already do this). First-time users may
  find it severe.

## Recommendation

**Mahakama**, possibly with Jua's softer corners if it feels too stern. The people HakiAI serves need above all to trust
what they read and to find the next step. Mahakama's green primary actions are the most distinct of the three, it keeps
the v1 identity, and Source Sans 3 is the most legible UI face here on low-resolution screens. Jua would be my second
choice for a friendlier first impression. Kitabu's reading view is the best of the three, but its monochrome actions
work against first-time users. Its reading measure and statute layout (68-character lines, "(a)" sub-paragraphs with a
hanging indent) are already shared by all three directions.

Example gate file contents: `Mahakama` or `Mahakama colours + Jua radius`.
