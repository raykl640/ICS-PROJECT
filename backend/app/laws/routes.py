"""/api/laws, /api/laws/{slug}, /api/laws/sections/{chunk_id}, /api/search (DESIGN_V2 "API v2" Laws). Public, no auth.

The search query is user content: it is sanitised (sanitize()) before Whoosh sees it and never logged."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request

from backend.app.accounts.service import AccountError
from backend.app.config import Settings
from backend.app.laws.catalog import ActInfo, ActToc, LawCatalog, SearchHit, SectionView

laws = APIRouter(prefix="/api")


def _catalog(request: Request) -> LawCatalog:
    found: LawCatalog | None = getattr(request.app.state, "laws", None)
    if found is None:
        raise AccountError(503, "not_ready", "The service is still starting. Please try again shortly.")
    return found


Catalog = Annotated[LawCatalog, Depends(_catalog)]


def _settings(request: Request) -> Settings:
    settings: Settings = request.app.state.runtime.deps.settings
    return settings


@laws.get("/laws")
def list_acts(catalog: Catalog) -> list[ActInfo]:
    """Every Act with its section counts."""
    return catalog.acts()


@laws.get("/laws/sections/{chunk_id}")
def get_section(chunk_id: str, catalog: Catalog) -> SectionView:
    """One section verbatim with prev/next and cross-references."""
    view = catalog.section(chunk_id)
    if view is None:
        raise AccountError(404, "not_found", "That section is not in the corpus.")
    return view


@laws.get("/laws/{slug}")
def get_act(slug: str, catalog: Catalog) -> ActToc:
    """An Act's table of contents grouped by Chapter/Part."""
    toc = catalog.toc(slug)
    if toc is None:
        raise AccountError(404, "not_found", "That Act is not in the corpus.")
    return toc


@laws.get("/search")
def search(
    request: Request,
    catalog: Catalog,
    q: Annotated[str, Query(min_length=1)],
    acts: Annotated[str, Query()] = "",
    limit: Annotated[int, Query(ge=1)] = 20,
) -> dict[str, list[SearchHit]]:
    """BM25 hits with snippets; acts is a comma-separated list of Act slugs (empty = all)."""
    settings = _settings(request)
    if len(q) > settings.max_question_chars:
        raise AccountError(422, "invalid_request", f"q: at most {settings.max_question_chars} characters.")
    slugs = [slug for slug in acts.split(",") if slug]
    return {"hits": catalog.search(q, slugs, min(limit, settings.search_max_results))}
