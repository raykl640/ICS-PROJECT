import { Search } from "lucide-react";
import { useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { Button } from "../../design/components/Button";
import { Field } from "../../design/components/Field";
import { useI18n } from "../../i18n";
import limits from "../../limits.json";

/** Full-text search box; submitting opens /search?q=. */
export function LawSearchForm({ initial = "", acts = [] }: { initial?: string; acts?: string[] }) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const [q, setQ] = useState(initial);
  const submit = (event: FormEvent) => {
    event.preventDefault();
    const params = new URLSearchParams({ q: q.trim() });
    if (acts.length) params.set("acts", acts.join(","));
    if (q.trim()) navigate(`/search?${params}`);
  };
  return (
    <form role="search" onSubmit={submit} className="flex flex-wrap items-end gap-2">
      <Field
        label={t("laws_search_label")}
        value={q}
        maxLength={limits.max_question_chars}
        onChange={(e) => setQ(e.target.value)}
        frameClassName="min-w-0 flex-1"
      />
      <Button type="submit" variant="primary" icon={<Search size={18} />}>
        {t("laws_search_button")}
      </Button>
    </form>
  );
}
