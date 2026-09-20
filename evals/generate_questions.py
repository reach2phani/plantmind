"""
generate_questions.py — Phase 1 step 1.4: Ragas writes WM-101 test questions.

WHAT THIS IS FOR (simple version)
    Every test we have so far was written by a person, from a failure we had
    already thought of. That is great for tricky cases (refusals, pressure,
    safety) but leaves most of the WM-101 documents untested: gas flow, wire
    stickout, alarm thresholds, repair times, part numbers. Nothing checks those.

    Ragas reads the document chunks and writes questions WITH their correct
    answers, straight from the text. You then review each one (keep / fix /
    drop) before any of them becomes a real test.

WHAT IT READS
    The WM-101 chunks already in Pinecone, official documents only:
    SOP (11 chunks), Work Instruction (10), NCR (8) = 29 chunks.

    Two things are left out ON PURPOSE:
      - Expert fixes: they contain the known-wrong "15-16 V normal arc voltage"
        fact. A question generated from a wrong fact becomes a test that
        rewards the wrong answer.
      - Shift logs: those feed Shift mode, not Docs mode, and would produce
        questions the Docs tests cannot fairly answer.

    Reading the Pinecone chunks, not the original files, is deliberate: they
    are EXACTLY what the app's search sees, so a generated question is fair to
    the app. Each question also records which chunk it came from, which step
    1.5 (retrieval metrics) can reuse.

TOKEN COST — split across two separate daily quotas
    gpt-oss-20b  (fast) : reads every chunk once and pulls out the key terms.
                          Simple extraction, so the cheap model does it.
                          29 calls.
    gpt-oss-120b (deep) : writes the questions and their correct answers.
                          Quality matters here, because a wrong reference
                          answer becomes a permanently wrong test.
                          About 1-2 calls per question.
    Rough total for 10 questions: ~30-40K tokens on 20b, ~15-25K on 120b.
    The demo keeps most of each model's 200K/day. Check the Groq console after.

    It runs ONE call at a time (max_workers=1) to stay under Groq's
    tokens-per-minute limit, so expect it to take roughly 10-15 minutes.

RUN (from C:\\plantmind, using the venv — the app does NOT need to be running)
    venv\\Scripts\\python.exe evals\\generate_questions.py --dry-run
        -> fetches and counts the chunks only. No Groq tokens spent. Do this first.
    venv\\Scripts\\python.exe evals\\generate_questions.py
        -> generates 10 questions
    venv\\Scripts\\python.exe evals\\generate_questions.py --size 20
        -> generates 20

OUTPUT
    evals/generated/questions_<date>_<time>.json
    Each question has  "review": "pending"  — change it to keep / fix / drop.
"""

import argparse
import datetime as dt
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
# Explicit path: load_dotenv() with no argument fails when run from some shells.
load_dotenv(ROOT / ".env")

from pinecone import Pinecone  # noqa: E402

PLANT = "Greenfield Steel Works"
EQUIP = "WM-101"
OFFICIAL_DOC_TYPES = ["SOP", "Work Instruction", "NCR"]
EMBED_MODEL = "multilingual-e5-large"  # the same model the app uses

MODEL_FAST = os.getenv("PM_MODEL_FAST", "openai/gpt-oss-20b")
MODEL_DEEP = os.getenv("PM_MODEL_DEEP", "openai/gpt-oss-120b")

OUT_DIR = ROOT / "evals" / "generated"


# ─────────────────────────────────────────────────────────────────────────────
# 1. Fetch the chunks — no Groq tokens, Pinecone only
# ─────────────────────────────────────────────────────────────────────────────
def fetch_chunks(pc):
    """Return every official WM-101 chunk exactly as the app's search stores it."""
    index = pc.Index(os.getenv("PINECONE_INDEX"))

    # Pinecone has no "give me everything matching this filter" call, so we
    # search with a broad query and a top_k far above the real count. The
    # filter is what decides which chunks come back; the query only orders them.
    probe = pc.inference.embed(
        model=EMBED_MODEL,
        inputs=["query: WM-101 MIG welder procedure"],
        parameters={"input_type": "query"},
    )
    result = index.query(
        vector=probe.data[0]["values"],
        top_k=1000,
        include_metadata=True,
        filter={
            "equip_tag": EQUIP,
            "plant_site": PLANT,
            "doc_type": {"$in": OFFICIAL_DOC_TYPES},
        },
    )

    chunks = []
    for m in result.matches:
        md = m.metadata or {}
        text = (md.get("text") or "").strip()
        if text:
            chunks.append({
                "chunk_id": m.id,
                "name": md.get("name", ""),
                "doc_type": md.get("doc_type", ""),
                "text": text,
            })

    # Stable order (by document, then chunk NUMBER) so two runs over the same
    # data see the chunks in the same order. Sorting by the raw id string would
    # put "chunk_10" before "chunk_2".
    chunks.sort(key=lambda c: (c["name"], _chunk_number(c["chunk_id"])))
    return chunks


def _chunk_number(chunk_id):
    tail = chunk_id.rsplit("_", 1)[-1]
    return int(tail) if tail.isdigit() else 0


def already_used_chunks():
    """Chunk ids that earlier runs already wrote questions from."""
    used = set()
    for f in OUT_DIR.glob("questions_*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        for q in data.get("questions", []):
            used.update(q.get("source_chunks", []))
    return used


def select_chunks(chunks, size, used):
    """
    Choose WHICH chunks get a question, instead of leaving it to Ragas.

    WHY THIS EXISTS
      The first run handed Ragas all 29 chunks and asked for 10 questions.
      Ragas simply took the first 10 in the order given, and that order was
      alphabetical: NCR, then SOP, then Work Instruction. Result: 8 questions
      from the NCR (mostly the history of one past incident), 2 from the start
      of the SOP, and ZERO from the Work Instruction. The gap the run was meant
      to fill — gas flow, stickout, voltage alarms, repair times — stayed
      completely untested.

    WHAT IT DOES NOW
      1. Skips chunks that an earlier run already wrote a question from, so
         each new run covers NEW ground instead of repeating the same chunks.
      2. Takes turns across the documents (round-robin), so every document
         gets its fair share. SOP and Work Instruction go first in each round:
         they hold the specs and procedures an operator must get right.

    Choosing exactly `size` chunks also means the fast model only reads the
    chunks that will actually be used — 10 instead of 29, so the run is cheaper.
    """
    order = ["SOP", "Work Instruction", "NCR"]
    queues = {t: [c for c in chunks if c["doc_type"] == t and c["chunk_id"] not in used]
              for t in order}

    picked = []
    while len(picked) < size and any(queues.values()):
        for t in order:
            if queues[t] and len(picked) < size:
                picked.append(queues[t].pop(0))
    return picked


# ─────────────────────────────────────────────────────────────────────────────
# 2. Adapters — let Ragas use Groq and Pinecone instead of OpenAI
# ─────────────────────────────────────────────────────────────────────────────
def build_embeddings(pc):
    """
    Ragas needs an embedding model, and Groq does not offer one. So we wrap
    Pinecone's multilingual-e5-large, which the app already uses: free, no new
    install, and the same model on both sides.
    """
    from langchain_core.embeddings import Embeddings
    from ragas.embeddings import LangchainEmbeddingsWrapper

    class PineconeEmbeddings(Embeddings):
        def _embed(self, texts, input_type):
            vectors = []
            for i in range(0, len(texts), 90):  # Pinecone limit is 96 per call
                batch = texts[i:i + 90]
                res = pc.inference.embed(
                    model=EMBED_MODEL,
                    inputs=batch,
                    parameters={"input_type": input_type, "truncate": "END"},
                )
                vectors.extend(d["values"] for d in res.data)
            return vectors

        def embed_documents(self, texts):
            return self._embed(list(texts), "passage")

        def embed_query(self, text):
            return self._embed([text], "query")[0]

    return LangchainEmbeddingsWrapper(PineconeEmbeddings())


def build_llm(model, effort, answer_tokens):
    """
    Groq through LangChain, set up the same way the app sets up GPT-OSS
    (see models.py completion_kwargs):
      - include_reasoning=False keeps the model's thinking out of the reply.
        Ragas expects clean JSON back; reasoning text mixed in would break it.
      - extra token headroom so the thinking cannot use up the answer's budget.
    """
    from langchain_groq import ChatGroq
    from ragas.llms import LangchainLLMWrapper

    headroom = {"low": 512, "medium": 1024}[effort]
    chat = ChatGroq(
        model=model,
        temperature=0.2,
        max_tokens=answer_tokens + headroom,
        reasoning_effort=effort,
        model_kwargs={"include_reasoning": False},
        max_retries=2,
    )
    return LangchainLLMWrapper(chat)


# ─────────────────────────────────────────────────────────────────────────────
# 3. Generate
# ─────────────────────────────────────────────────────────────────────────────
def generate(chunks, size, pc):
    from langchain_core.documents import Document
    from ragas.run_config import RunConfig
    from ragas.testset import TestsetGenerator
    from ragas.testset.persona import Persona
    from ragas.testset.synthesizers.prompts import (
        PersonaThemesMapping,
        ThemesPersonasMatchingPrompt,
    )
    from ragas.testset.synthesizers.single_hop.specific import (
        SingleHopSpecificQuerySynthesizer,
    )
    from ragas.testset.transforms.extractors.llm_based import KeyphrasesExtractor

    class TolerantPersonaMatching(ThemesPersonasMatchingPrompt):
        """
        FIX 1 — one bad reply must not crash the whole run.

        For each chunk, Ragas asks the model "which persona would ask about
        which of these terms?". The first real run died 23 seconds in: one reply
        came back unreadable, Ragas turned it into an empty {}, and because all
        chunks are handled inside ONE step, that single bad reply killed every
        question. Debugging showed the same prompt succeeds normally — the
        failure is intermittent, which is what reasoning models do now and then.

        So: retry twice, and if it still fails, fall back to "both personas may
        ask about every term". That fallback is harmless — the mapping only
        decides who is asking, not what the correct answer is.
        """

        async def generate(self, llm, data, **kwargs):
            for _ in range(3):
                try:
                    out = await super().generate(llm=llm, data=data, **kwargs)
                    # A readable reply can still be useless: testing showed the
                    # model sometimes maps every persona to an EMPTY list. That
                    # silently produces no questions for the chunk, so it counts
                    # as a failure too. Accept only if someone asks about something.
                    if out.mapping and any(out.mapping.values()):
                        return out
                except Exception:  # unreadable reply — try again
                    pass
            print(f"  (persona matching fell back for terms: {data.themes[:3]}...)")
            return PersonaThemesMapping(
                mapping={p.name: list(data.themes) for p in data.personas}
            )

    fast = build_llm(MODEL_FAST, "low", 1024)      # pulls key terms from chunks
    deep = build_llm(MODEL_DEEP, "medium", 1536)   # writes questions + answers
    embeddings = build_embeddings(pc)

    docs = [
        Document(page_content=c["text"],
                 metadata={"chunk_id": c["chunk_id"], "name": c["name"],
                           "doc_type": c["doc_type"]})
        for c in chunks
    ]

    # Who is asking. Given explicitly, because otherwise Ragas spends extra
    # LLM calls inventing personas from summaries of every chunk.
    personas = [
        Persona(
            name="Line operator",
            role_description=(
                "A welding operator on Fabrication Line 1 who runs the WM-101 "
                "MIG welder each shift and needs quick, exact answers: settings, "
                "alarm limits, what to check first, and when to stop the machine."
            ),
        ),
        Persona(
            name="Maintenance technician",
            role_description=(
                "A maintenance technician who services the WM-101: replaces "
                "liners, drive rolls and contact tips, follows lockout/tagout, "
                "and needs part numbers, repair times and post-repair checks."
            ),
        ),
    ]

    generator = TestsetGenerator(
        llm=deep,
        embedding_model=embeddings,
        persona_list=personas,
        # Without this the questions come out generic ("the welder"), and the
        # app then cannot tell which machine is meant.
        llm_context=(
            "Questions come from staff at Greenfield Steel Works about the "
            "WM-101 MIG welder on Fabrication Line 1. Every question must name "
            "the machine as WM-101. Ask about specific facts stated in the text: "
            "numbers, limits, steps, part numbers, durations, safety requirements."
        ),
    )

    # Keep the pipeline minimal, which keeps it cheap:
    #   - ONE extraction step (key phrases per chunk, on the fast model) instead
    #     of Ragas' default five (headlines, summaries, keyphrases, themes...).
    #   - ONE question type: single-hop, i.e. answerable from a single chunk.
    #     Multi-hop questions need extra relationship-building passes, and our
    #     hand-written investigation cases already cover cross-document reasoning.
    #
    # FIX 2 — KEY PHRASES, not named entities.
    #   The first version pulled "named entities", and on real chunks those were
    #   mostly dates, clock times and people: "14 November 2024", "23:14",
    #   "D. Kowalski". Questions built on those are trivia ("who was the shift
    #   supervisor?"), not plant knowledge. Key phrases on the same chunks gave
    #   "wire feed tension", "drive roll groove", "wire feed motor overload
    #   alarm" — the things an operator actually needs to get right.
    transforms = [KeyphrasesExtractor(llm=fast)]
    distribution = [(
        SingleHopSpecificQuerySynthesizer(
            llm=deep,
            property_name="keyphrases",
            theme_persona_matching_prompt=TolerantPersonaMatching(),
        ),
        1.0,
    )]

    run_config = RunConfig(
        max_workers=1,   # one call at a time: stays under 8K tokens/minute
        max_retries=6,
        max_wait=60,
        timeout=180,
    )

    return generator.generate_with_chunks(
        docs,
        testset_size=size,
        transforms=transforms,
        transforms_llm=fast,
        transforms_embedding_model=embeddings,
        query_distribution=distribution,
        run_config=run_config,
        # If writing ONE question fails, keep the others rather than losing the
        # whole run. Failed ones are dropped when the file is written.
        raise_exceptions=False,
    )


# ─────────────────────────────────────────────────────────────────────────────
# 4. Save in a shape made for reviewing
# ─────────────────────────────────────────────────────────────────────────────
def to_review_file(testset, chunks):
    """
    Ragas returns the source text of each question, not our chunk ids. We match
    the text back to the chunk, so every question says exactly which document
    and chunk it came from — needed both for your review ("is this answer
    really in the SOP?") and for retrieval scoring in step 1.5.
    """
    by_text = {c["text"]: c for c in chunks}

    def source_of(ctx):
        c = by_text.get((ctx or "").strip())
        if c is None:  # fallback: Ragas can trim whitespace differently
            c = next((x for x in chunks if ctx.strip()[:200] in x["text"]), None)
        return c

    # With raise_exceptions=False, a question that failed to generate comes back
    # as an empty row. Skip those instead of saving blank questions to review.
    rows = [r for r in testset.to_list()
            if isinstance(r.get("user_input"), str) and r["user_input"].strip()
            and isinstance(r.get("reference"), str) and r["reference"].strip()]
    skipped = len(testset.to_list()) - len(rows)
    if skipped:
        print(f"Note: {skipped} question(s) failed to generate and were skipped.")

    items = []
    for i, row in enumerate(rows, start=1):
        contexts = row.get("reference_contexts") or []
        sources = [source_of(c) for c in contexts]
        items.append({
            "id": f"GEN-{i:03d}",
            "question": row.get("user_input", ""),
            "reference_answer": row.get("reference", ""),
            "source_chunks": [s["chunk_id"] for s in sources if s],
            "source_documents": sorted({f'{s["doc_type"]}: {s["name"]}' for s in sources if s}),
            "source_text": contexts,
            "persona": row.get("persona_name", ""),
            # ── YOUR REVIEW ──────────────────────────────────────────────────
            # keep : good as it is
            # fix  : good idea, but edit the question or reference_answer
            # drop : unanswerable, trivial, wrong, or a duplicate
            "review": "pending",
            "review_notes": "",
        })
    return items


def main():
    ap = argparse.ArgumentParser(description="Generate WM-101 test questions with Ragas.")
    ap.add_argument("--size", type=int, default=10, help="how many questions (default 10)")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and count chunks only; spends no Groq tokens")
    args = ap.parse_args()

    if not os.getenv("GROQ_API_KEY") and not args.dry_run:
        sys.exit("GROQ_API_KEY is not set in .env")

    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    chunks = fetch_chunks(pc)

    print(f"\nFound {len(chunks)} official {EQUIP} chunks:")
    counts = {}
    for c in chunks:
        counts[c["doc_type"]] = counts.get(c["doc_type"], 0) + 1
    for k, v in sorted(counts.items()):
        print(f"  {k:<18} {v}")

    if len(chunks) == 0:
        sys.exit("\nNo chunks found — check PINECONE_INDEX and that WM-101 documents are embedded.")

    used = already_used_chunks()
    picked = select_chunks(chunks, args.size, used)

    print(f"\nAlready covered by earlier runs: {len(used)} chunk(s). "
          f"Picked {len(picked)} new chunk(s) for this run:")
    for c in picked:
        print(f"  {c['doc_type']:<18} {c['name']}  chunk {_chunk_number(c['chunk_id'])}")

    if not picked:
        sys.exit("\nEvery chunk already has a question. Nothing new to generate.")

    if args.dry_run:
        print("\nDry run: stopping here. No Groq tokens were spent.")
        return

    print(f"\nGenerating {len(picked)} questions — fast model {MODEL_FAST}, "
          f"deep model {MODEL_DEEP}.")
    print("One call at a time to respect the rate limit; this takes a while.\n")

    # One question per picked chunk: Ragas gets exactly the chunks we chose.
    testset = generate(picked, len(picked), pc)
    items = to_review_file(testset, picked)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    out = OUT_DIR / f"questions_{stamp}.json"
    out.write_text(json.dumps({
        "_meta": {
            "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
            "equip_tag": EQUIP,
            "plant_site": PLANT,
            "doc_types": OFFICIAL_DOC_TYPES,
            "chunks_available": len(chunks),
            "chunks_used": [c["chunk_id"] for c in picked],
            "models": {"extraction": MODEL_FAST, "questions": MODEL_DEEP},
            "ragas_synthesizer": "single_hop_specific",
            "how_to_review": "Set each 'review' to keep / fix / drop. For 'fix', "
                             "edit the question or reference_answer directly.",
        },
        "questions": items,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\nWrote {len(items)} questions to {out.relative_to(ROOT)}")
    unmatched = sum(1 for q in items if not q["source_chunks"])
    if unmatched:
        print(f"Note: {unmatched} question(s) could not be traced back to a chunk id.")


if __name__ == "__main__":
    main()
