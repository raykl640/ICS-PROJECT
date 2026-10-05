"""Synthetic retrieval stack (invented corpus + fakes) shared by the retrieval tests and `bench_retrieval.py --fake`."""

from pathlib import Path

from backend.app.config import ActSpec, Settings
from backend.app.interfaces import CrossEncoderLike
from backend.app.retrieval.dense import DenseIndex
from backend.app.retrieval.hybrid import HybridRetriever
from backend.app.retrieval.pipeline import ContextPipeline
from backend.app.retrieval.refs import RefExtractor
from backend.app.retrieval.router import DomainTable, Router
from backend.app.retrieval.scope import ScopeClassifier, ScopeExamples
from backend.app.retrieval.sparse import SparseIndex
from backend.app.retrieval.store import ChunkStore
from backend.app.retrieval.windows import WindowSpec
from backend.tests.corpus import CONSTITUTION, EMPLOYMENT, TENANCY, corpus
from backend.tests.fakes import FakeEmbedder, FakeReranker

ACTS = [
    ActSpec(name="Sample Constitution", year=2000, file="c.pdf", unit="Article"),
    ActSpec(name="Sample Employment Act", year=2000, file="e.pdf", cap="999"),
    ActSpec(name="Sample Tenancy Act", year=2000, file="t.pdf"),
]
TABLE = DomainTable.build(
    {
        "co_domain": CONSTITUTION,
        "co_domain_for": [EMPLOYMENT, TENANCY],
        "acts": {
            CONSTITUTION: {"aliases": ["constitution"], "terms": ["rights", "discrimination"]},
            EMPLOYMENT: {"aliases": [], "terms": ["fired", "employer", "leave", "wages"]},
            TENANCY: {"aliases": [], "terms": ["landlord", "tenant", "evict"]},
        },
    },
    ACTS,
)
EMB = FakeEmbedder()
SCOPE = ScopeExamples(
    in_scope=["my boss sacked me", "the landlord kicked me out", "police beat me"],
    out_scope=["chapati recipe", "football score", "weather tomorrow"],
)
STORE = ChunkStore(corpus())


def build_parts(sparse_dir: Path) -> tuple[DenseIndex, SparseIndex]:
    """Dense and sparse indexes over the synthetic corpus (sparse written to sparse_dir)."""
    spec = WindowSpec(split_over=200, words=180, stride=120)
    dense = DenseIndex.build(STORE.indexable(), EMB, spec=spec, model_name="fake", corpus_hash=STORE.corpus_hash)
    sparse = SparseIndex.build(STORE.indexable(), sparse_dir, corpus_hash=STORE.corpus_hash)
    return dense, sparse


def fake_retriever(parts: tuple[DenseIndex, SparseIndex], settings: Settings) -> HybridRetriever:
    """HybridRetriever over the synthetic corpus with the fake embedder."""
    router = Router(TABLE, RefExtractor(ACTS, TABLE.aliases))
    return HybridRetriever(EMB, parts[0], parts[1], STORE, router, settings)


def fake_pipeline(sparse_dir: Path, settings: Settings, reranker: CrossEncoderLike | None = None) -> ContextPipeline:
    """Full retrieve -> rerank pipeline over the synthetic corpus; FakeReranker unless one is given."""
    retriever = fake_retriever(build_parts(sparse_dir), settings)
    scope = ScopeClassifier(EMB, SCOPE, settings.scope_neighbours)
    return ContextPipeline(retriever, reranker or FakeReranker(), scope, settings, STORE)
