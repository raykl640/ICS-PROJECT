import { Link } from "react-router";
import { listActs, listReads, type ActInfo } from "../api/laws";
import { useAuth } from "../app/contexts";
import { PageTitle } from "../app/PageTitle";
import { LawSearchForm } from "../components/laws/LawSearchForm";
import { Skeleton } from "../design/components/Display";
import { useLoad } from "../hooks/useLoad";
import { type StringKey, useI18n } from "../i18n";

type Group = "rights" | "work" | "home" | "family" | "crime" | "courts" | "buying" | "health";

// Everyday area and plain-language scope of each Act in data/sources.yaml (DEVIATIONS D32, D33). An Act missing here
// is listed under "Other Acts" without a description.
const ACTS: Record<string, { group: Group; domain: StringKey }> = {
  "constitution-of-kenya": { group: "rights", domain: "domain_constitution" },
  "legal-aid-act": { group: "rights", domain: "domain_legal_aid" },
  "refugees-act": { group: "rights", domain: "domain_refugees" },
  "counter-trafficking-in-persons-act": { group: "rights", domain: "domain_trafficking" },
  "employment-act": { group: "work", domain: "domain_employment" },
  "labour-relations-act": { group: "work", domain: "domain_labour" },
  "landlord-and-tenant-shops-hotels-and-catering-establishments-act": { group: "home", domain: "domain_shops" },
  "rent-restriction-act": { group: "home", domain: "domain_rent" },
  "land-act": { group: "home", domain: "domain_land" },
  "land-registration-act": { group: "home", domain: "domain_land_registration" },
  "marriage-act": { group: "family", domain: "domain_marriage" },
  "matrimonial-property-act": { group: "family", domain: "domain_matrimonial" },
  "law-of-succession-act": { group: "family", domain: "domain_succession" },
  "national-police-service-act": { group: "crime", domain: "domain_police" },
  "criminal-procedure-code": { group: "crime", domain: "domain_cpc" },
  "penal-code": { group: "crime", domain: "domain_penal" },
  "traffic-act": { group: "crime", domain: "domain_traffic" },
  "civil-procedure-act": { group: "courts", domain: "domain_civil_procedure" },
  "small-claims-court-act": { group: "courts", domain: "domain_small_claims" },
  "limitation-of-actions-act": { group: "courts", domain: "domain_limitation" },
  "evidence-act": { group: "courts", domain: "domain_evidence" },
  "consumer-protection-act": { group: "buying", domain: "domain_consumer" },
  "public-health-act": { group: "health", domain: "domain_public_health" },
  "mental-health-act": { group: "health", domain: "domain_mental_health" },
  "hiv-and-aids-prevention-and-control-act": { group: "health", domain: "domain_hiv" },
};
const GROUPS: Group[] = ["rights", "work", "home", "family", "crime", "courts", "buying", "health"];

/** The Acts in the corpus, grouped by everyday area; each opens its table of contents. */
export function Laws() {
  const { t } = useI18n();
  const { result } = useLoad("acts", listActs);
  const grouped = (acts: ActInfo[]) => [
    ...GROUPS.map((group) => ({
      key: group,
      title: t(`law_group_${group}`),
      acts: acts.filter((act) => ACTS[act.slug]?.group === group),
    })),
    { key: "other", title: t("law_group_other"), acts: acts.filter((act) => !ACTS[act.slug]) },
  ];
  return (
    <div className="flex max-w-4xl flex-col gap-10">
      <div className="flex flex-col gap-5">
        <div>
          <PageTitle>{t("laws_title")}</PageTitle>
          <p className="mt-2 text-lg text-ink-muted">{t("laws_intro")}</p>
        </div>
        <LawSearchForm />
      </div>
      <RecentReads />
      {result.status === "error" && <p className="font-semibold text-danger">{t("laws_error")}</p>}
      {result.status === "loading" && <Skeleton className="h-40 rounded-md" />}
      {result.status === "ok" &&
        grouped(result.data)
          .filter((group) => group.acts.length > 0)
          .map((group) => (
            <section key={group.key} aria-labelledby={`group-${group.key}`}>
              <h2 id={`group-${group.key}`} className="mb-3 text-sm font-semibold text-ink-muted">
                {group.title}
              </h2>
              <ul className="grid gap-3 sm:grid-cols-2">
                {group.acts.map((act) => (
                  <li key={act.slug}>
                    <ActLink act={act} />
                  </li>
                ))}
              </ul>
            </section>
          ))}
    </div>
  );
}

function ActLink({ act }: { act: ActInfo }) {
  const { t } = useI18n();
  const domain = ACTS[act.slug]?.domain;
  return (
    <Link
      to={`/laws/${act.slug}`}
      className="target flex h-full flex-col gap-1 rounded-lg border border-line-subtle bg-raised px-4 py-3.5 text-ink motion-colors hover:border-line hover:shadow-raised"
    >
      <span className="font-semibold">{act.name}</span>
      {domain && <span className="text-sm text-ink-muted">{t(domain)}</span>}
      <span className="mt-auto pt-1 text-xs text-ink-muted">
        {t(act.unit === "Article" ? "laws_count_articles" : "laws_count_sections", {
          year: act.year,
          count: act.sections,
        })}
      </span>
    </Link>
  );
}

/** Signed in: the sections read most recently. */
function RecentReads() {
  const { t } = useI18n();
  const { me } = useAuth();
  const enabled = Boolean(me?.user && !me.locked);
  const reads = useLoad(enabled ? "laws-reads" : null, () => listReads(3)).result;
  if (!enabled || reads.status !== "ok" || reads.data.length === 0) return null;
  return (
    <section aria-labelledby="reads-title">
      <h2 id="reads-title" className="mb-2 text-sm font-semibold text-ink-muted">
        {t("continue_reading")}
      </h2>
      <ul className="flex flex-col divide-y divide-line-subtle">
        {reads.data.map((read) => (
          <li key={read.chunk_id}>
            <Link
              to={`/laws/act/${read.chunk_id}`}
              className="-mx-3 flex items-baseline gap-2 rounded-md px-3 py-2.5 text-ink motion-colors hover:bg-sunken"
            >
              <span className="line-clamp-1 min-w-0">
                <span className="font-semibold">{read.act}</span>
                <span className="text-ink-muted">
                  {" — "}
                  {read.section_num}: {read.section_title}
                </span>
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}
