KenyaLegalAid
System Architecture — Technical Description

1. System Overview
KenyaLegalAid is a Retrieval-Augmented Generation (RAG) system that answers legal queries by
retrieving relevant text from a curated corpus of Kenyan statutes, then passing that text to a locally-
running language model to generate a grounded response. The system runs entirely offline after initial
setup — no external API calls are made during inference.


The pipeline has seven sequential stages: corpus ingestion, legal-aware parsing and chunking, dual
indexing, hybrid retrieval, cross-encoder reranking, LLM generation, and API/frontend delivery. Each
stage is described in full below.


Stage              Component                                 Technology
1 — Ingestion      Statute PDF download and OCR              requests, pdfplumber
                   verification
2 — Parsing        Legal-aware chunker with section          pdfplumber, regex
                   metadata
3 — Indexing       Dense vector index + BM25 keyword         FAISS, Whoosh
                   index
4 — Retrieval      Parallel dense + sparse query, RRF        sentence-transformers,
                   fusion                                    custom Python
5 — Reranking      Cross-encoder relevance scoring           cross-encoder/ms-marco-
                                                             MiniLM-L-6-v2
6 — Generation     Grounded LLM response with inline         Mistral 7B via Ollama
                   citations
7 — Delivery       REST API with SSE streaming + React       FastAPI, React, Tailwind
                   frontend



2. Corpus — Source Documents
The corpus consists of 9–10 primary Kenyan statutes downloaded as PDFs from kenyalaw.org. These
are text-searchable PDFs, not scanned images. Scanned documents require Tesseract OCR
preprocessing and are manually verified before inclusion.


Document                                     Legal domain covered
Constitution of Kenya 2010                   Fundamental rights — employment, housing,
                                             fair trial, equality
Employment Act Cap 226                       Dismissal, contracts, leave, wages,
                                             disciplinary procedures
Landlord & Tenant (Shops) Act Cap 301        Commercial tenancy rights and disputes
Rent Restriction Act Cap 296                 Residential rent controls
Land Act 2012                                Land registration, transactions, compulsory
                                             acquisition
Consumer Protection Act 2012                 Unfair terms, consumer redress, warranties
National Police Service Act 2011             Police conduct, use of force, complaints
                                             procedure
Criminal Procedure Code Cap 75               Arrest procedure, bail, trial process
Traffic Act Cap 403                          Road offences, penalties, licence
                                             requirements



                                               Page 1 of 8
After parsing, the corpus produces approximately 1,000–3,000 LegalChunk objects depending on
section granularity. This is the ground truth from which all retrieval and generation operates.



3. Legal-Aware Parsing and Chunking
Standard RAG systems split documents into fixed-length token windows (e.g. 512 tokens). This is
unsuitable for legal text because a single statutory section may span 800 words, and splitting mid-
clause destroys legal meaning. This system parses documents by legal structure.


3.1 Parsing logic
pdfplumber extracts text page by page from each statute PDF. A regex pattern identifies section
headings by detecting lines that begin with a number followed by an uppercase title. The parser walks
the extracted text and creates one chunk per section, capturing the full text of that section including all
subsections and paragraphs.


Each chunk is stored as a LegalChunk object with the following fields:
  – act: Name of the statute (e.g. 'Employment Act')
  – part: The Part heading this section falls under (e.g. 'PART V — TERMINATION')
  – section_num: Section number as a string (e.g. '41')
  – section_title: Section title as extracted (e.g. 'Termination of employment')
  – text: Full text of the section including all subsections
  – page: Page number in the source PDF
  – act_year: Year of the Act


3.2 Known parsing limitations
   – The section-heading regex will produce false positives on footnotes, table of contents entries, and
     inconsistently formatted headings. Parsed output is manually reviewed for each statute before
     indexing.
   – pdfplumber does not reliably preserve indentation. Subsection boundaries are inferred by
     indentation patterns that may break on some PDFs.
   – Scanned PDFs require OCR. OCR output has noise that degrades chunk quality. Documents with
     OCR confidence below an acceptable threshold are excluded from the corpus.



4. Dual Indexing — FAISS and BM25
Two independent indexes are built over the same set of LegalChunk objects. They capture different
aspects of relevance and are queried in parallel during retrieval.


4.1 FAISS dense index
Each chunk's text is encoded into a 384-dimensional embedding vector using sentence-transformers
(model: all-MiniLM-L6-v2). This model was chosen for its speed on CPU and its suitability for semantic
similarity search. The embeddings are stored in a FAISS IndexFlatL2 index and persisted to disk. At



                                                 Page 2 of 8
query time, the user's question is encoded with the same model and the nearest neighbours in vector
space are returned.


Dense retrieval captures semantic similarity — a query about 'wrongful dismissal' will retrieve chunks
about 'unfair termination' even if those exact words are absent from the query. It does not reliably
match specific legal terms, section numbers, or Act names.


4.2 Whoosh BM25 sparse index
The same chunks are indexed in a Whoosh BM25 inverted index. BM25 scores documents by term
frequency weighted against inverse document frequency. It is effective for exact legal terminology —
section numbers, Act names, specific statutory phrases — that dense embeddings may dilute.


The two indexes are complementary. Dense retrieval handles paraphrased or lay-language queries.
BM25 handles precise legal term lookups. The system queries both in parallel.



5. Hybrid Retrieval — RRF Fusion
At query time, the user's question (translated to English if Swahili is detected) is issued against both
indexes simultaneously. Each index returns a ranked list of 20 candidate chunks. These two ranked
lists are merged using Reciprocal Rank Fusion (RRF).


5.1 RRF fusion
RRF assigns each chunk a score of 1 / (k + rank) where k = 60 is a smoothing constant and rank is its
position in each list (1-indexed). A chunk's final score is the sum of its scores from both lists. Chunks
appearing in the top positions of both lists receive the highest combined scores. Chunks appearing in
only one list still receive a partial score.


The output of RRF is a single merged ranked list of up to 40 unique candidates (20 from each index,
with overlap). The top 20 candidates from this merged list are passed to the reranker.


5.2 Domain metadata filtering (lightweight routing)
Before retrieval, a keyword-based domain filter narrows the FAISS search to chunks belonging to the
relevant legal domain. A lookup table maps query keywords to Act names (e.g. 'fired', 'dismissal',
'employer' → Employment Act). This replaces the computationally expensive bart-large-mnli zero-shot
classifier from earlier designs. If no domain is detected, retrieval runs across the full corpus.



6. Cross-Encoder Reranking
The top 20 RRF candidates are re-scored by a cross-encoder model (cross-encoder/ms-marco-MiniLM-
L-6-v2). Unlike the bi-encoder used for FAISS, which encodes the query and document independently,
a cross-encoder takes the query and document together as a single input and produces a single
relevance score. This is slower but substantially more accurate.




                                                Page 3 of 8
The cross-encoder scores all 20 (query, chunk) pairs and sorts them by descending score. The top 5
chunks from this reranked list are selected and passed to the generation stage. These 5 chunks
constitute the retrieved context from which Mistral generates its response.


The reranker runs on CPU. For 20 pairs with chunks averaging 300 tokens, inference time is
approximately 2–4 seconds on an 8 GB RAM laptop.



7. LLM Generation — Mistral 7B via Ollama
Mistral 7B Instruct (4-bit quantised, Q4_K_M) is served locally using Ollama. Ollama handles model
loading, quantisation, and exposes a local REST API on port 11434. The 4-bit quantised model
occupies approximately 4.1 GB of RAM and runs on CPU-only hardware.


7.1 How Mistral is used in this system
Mistral is not asked to recall legal knowledge from its training weights. Its role is to read the 5 retrieved
chunks and synthesise a structured response from that text. The prompt is constructed as follows:


       SYSTEM: You are a Kenyan legal aid assistant. Answer ONLY using the legal
               text provided below. Do not use outside knowledge. If the answer
               cannot be found in the provided text, say so explicitly. Cite the
               Act name and section number for every factual claim.

       CONTEXT:
       [CHUNK 1] Employment Act, Section 41, Page 23:
         An employer shall not terminate a contract of service...
       [CHUNK 2] Employment Act, Section 45, Page 27:
         An employee who is summarily dismissed...
       [CHUNK 3] Constitution of Kenya 2010, Article 41, Page 18:
         Every person has the right to fair labour practices...

       USER QUESTION: My employer fired me without notice. What are my rights?


The chunk metadata (Act name, section number, page) is embedded directly in the context string so
Mistral can reference it in citations without hallucinating source details.


7.2 Temperature and generation parameters
Mistral is called with temperature = 0.1. At low temperature, the model stays close to the wording of the
retrieved chunks and is less likely to paraphrase in ways that alter legal meaning. The model is not
asked to be creative; it is asked to synthesise and cite.


7.3 Structured output format
The system prompt instructs Mistral to structure every response in three sections:
  – Rights Explanation: Plain-language description of the user's legal position, citing specific
    provisions


                                                  Page 4 of 8
   – Recommended Steps: Numbered list of concrete actions the user can take
   – Formal Letter: A draft letter the user can send to the relevant party (employer, landlord, etc.)

The FastAPI backend parses section headers (## RIGHTS EXPLANATION, ## RECOMMENDED
STEPS, ## FORMAL LETTER) to split the response into separate frontend panels.


7.4 Hallucination risk — honest assessment
RAG reduces the rate of unsupported generation by constraining the model to retrieved context. It does
not eliminate it. Mistral may still synthesise claims that span multiple chunks incorrectly, attribute a rule
to the wrong section, or generate legally plausible conclusions not explicitly stated in any chunk. The
system therefore includes: (a) verbatim source display in the Sources Panel so users can verify claims
directly against the retrieved text, and (b) a disclaimer on every response that the output is not legal
advice.


7.5 Null response fallback
If the retrieval pipeline returns fewer than 2 chunks with a relevance score above a minimum threshold,
the system returns a fixed message rather than passing low-confidence context to Mistral: 'I cannot find
a specific provision covering this in the current corpus. Please consult a qualified advocate.' This
prevents generation from near-empty context.



8. FastAPI Backend
The backend is a FastAPI application serving five endpoints. Session state is held in memory (Python
dict keyed by UUID session ID). No external database or cache is used.


Endpoint                   Method         Function
POST /api/query            POST           Accepts question + language. Runs retrieval and
                                          reranking. Stores top-5 chunks in session.
                                          Returns session_id.
GET /api/stream/           GET (SSE)      Opens a Server-Sent Events connection. Calls
{session_id}                              Ollama streaming API. Forwards tokens to the
                                          client as they are generated.
GET /api/sources/          GET            Returns the 5 retrieved chunks for a session —
{session_id}                              Act name, section number, page, verbatim text —
                                          for display in the Sources Panel.
GET /api/letter/           GET            Extracts the Formal Letter section from the
{session_id}                              generated response and returns it as plain text or
                                          DOCX.
GET /api/health            GET            Confirms Ollama is reachable and the model is
                                          loaded. Used on startup.


8.1 SSE streaming
Ollama's /api/generate endpoint supports token-by-token streaming. The FastAPI backend opens a
streaming request to Ollama and forwards each token to the React frontend via Server-Sent Events.
The frontend renders tokens as they arrive. This means the user sees output beginning within 2–3
seconds rather than waiting for the full response to complete (which may take 60–120 seconds on CPU
hardware).



                                                 Page 5 of 8
8.2 Language handling
Language detection runs on the incoming question using langdetect. If Swahili is detected, the question
is translated to English using a locally-running MarianMT model (Helsinki-NLP/opus-mt-sw-en) before
being passed to the retrieval pipeline. Retrieval and generation operate in English. If the original
question was Swahili, the generated response is translated back to Swahili via Helsinki-NLP/opus-mt-
en-sw before streaming. A legal glossary maps known legal terms to their Swahili equivalents with
bracketed English originals.


Note: MarianMT was not trained on legal corpora. Translation quality for legal nuance is limited. Swahili
output is a best-effort aid, not an authoritative translation.



9. React Frontend
The frontend is a single-page React application. It communicates with the FastAPI backend over HTTP
and EventSource (SSE). The UI has four panels:


    – Query Panel: Text input for the legal question. Language toggle (EN / SW). Submit button.
    – Response Panel: Renders the streamed response in real time. Three sub-sections displayed as
      tabs or accordion: Rights Explanation, Recommended Steps, Formal Letter.
    – Sources Panel: Collapsible panel showing the 5 retrieved chunks verbatim. Each chunk displays
      Act name, section number, page number, and the full text of that section. This allows the user to
      verify every claim in the response against the source document.
    – Feedback Bar: Thumbs up / thumbs down. Feedback is appended to a local JSON file for later
      analysis.

The frontend is built with React and Tailwind CSS. It is served as a static build from the FastAPI
backend (or a separate dev server during development). No external services are called from the
frontend.



10. End-to-End Query Flow
The following describes the complete data path for a single user query from input to rendered
response.


Ste   What happens                                                Component
p
1     User types a question and submits                           React frontend
2     Frontend POSTs question to /api/query                       HTTP
3     Language detected. If Swahili, question translated to       FastAPI + MarianMT
      English via MarianMT sw→en
4     Keyword domain filter identifies relevant Acts from query   FastAPI — domain router
      terms
5     Question encoded to 384-dim vector via all-MiniLM-L6-v2     sentence-transformers
6     FAISS returns top-20 nearest neighbours from dense          FAISS
      index
7     Whoosh BM25 returns top-20 keyword matches from             Whoosh



                                                   Page 6 of 8
Ste   What happens                                                 Component
p
      sparse index
8     RRF merges the two ranked lists into one merged list of      Custom Python
      up to 40 candidates
9     Cross-encoder scores top-20 RRF candidates as                ms-marco cross-encoder
      (question, chunk) pairs
10    Top-5 reranked chunks selected. Session stored with          FastAPI — session store
      session_id
11    Frontend receives session_id. Opens SSE connection           EventSource API
      to /api/stream/{session_id}
12    FastAPI constructs prompt: system instruction + 5 chunks     FastAPI — prompt builder
      + user question
13    Prompt sent to Ollama /api/generate with stream: true        Ollama HTTP API
14    Mistral 7B generates tokens from the retrieved context.      Mistral 7B Q4
      Each token forwarded via SSE
15    If original question was Swahili, completed response         MarianMT
      translated via MarianMT en→sw
16    Frontend renders tokens in real time across Rights / Steps   React
      / Letter panels
17    User clicks Sources Panel. Frontend calls /api/sources/      FastAPI + React
      {session_id}. Verbatim chunks displayed



11. Component Dependencies and Data Flow
The following describes which components depend on which, and what data passes between them.


From                        To                           Data passed
PDF files (kenyalaw.org)    pdfplumber parser            Raw PDF bytes
pdfplumber parser           LegalChunk objects           Structured text with act/section/page
                                                         metadata
LegalChunk objects          FAISS index                  384-dim embedding vectors
LegalChunk objects          Whoosh index                 Raw text + metadata fields
LegalChunk objects          Chunk store (dict/JSON)      Full chunk objects referenced by
                                                         chunk_id
User query (React)          FastAPI /api/query           Question string + language flag
FastAPI                     MarianMT (sw→en)             Swahili question string (conditional)
FastAPI                     sentence-transformers        English question string
sentence-transformers       FAISS                        384-dim query vector
FAISS                       RRF module                   List of (chunk_id, distance) pairs, top
                                                         20
Whoosh                      RRF module                   List of (chunk_id, BM25 score) pairs,
                                                         top 20
RRF module                  Cross-encoder                List of chunk_ids (top 20 merged)
Chunk store                 Cross-encoder                Chunk texts for the top-20 chunk_ids
Cross-encoder               Session store                Top-5 (chunk, score) pairs
Session store               FastAPI /api/stream          5 chunks retrieved by session_id
5 chunks + question         Prompt builder               Formatted context string
Prompt builder              Ollama API                   Full prompt string
Ollama API                  FastAPI SSE endpoint         Token stream
FastAPI SSE endpoint        React frontend               Token strings via EventSource
React frontend              FastAPI /api/sources         session_id
FastAPI /api/sources        React Sources Panel          5 chunk objects (act, section, page,
                                                         text)




                                                    Page 7 of 8
Page 8 of 8
