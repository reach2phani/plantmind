"""
ragas_test.py — PM-RAGAS-01
PlantMind RAG evaluation using Ragas 0.4.x
Uses Groq via OpenAI-compatible client (what Ragas expects)
"""

import os, json, time, requests
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from ragas import evaluate
from ragas.metrics import faithfulness, context_recall
from ragas.llms import llm_factory
from datasets import Dataset

FLASK_URL = "http://localhost:5000"
GROQ_KEY  = os.getenv("GROQ_API_KEY")

GOLDEN_CASES = [
    {
        "id": "RQ-001",
        "description": "Spatter threshold — two thresholds in one document",
        "question": "What spatter index value triggers the initial alarm on WR-401 (not the auto-quarantine threshold)?",
        "ground_truth": (
            "The initial spatter index alarm threshold for WR-401 is 3.5. "
            "When the spatter index exceeds 3.5 a quality alarm is triggered. "
            "A separate higher threshold of 5.0 triggers automatic panel quarantine. "
            "These are two distinct thresholds: 3.5 for the initial alarm, 5.0 for auto-quarantine."
        ),
        "plant_site": "Northgate Automotive",
        "equip_tag":  "WR-401",
        "mode":       "doc",
    },
    {
        "id": "RQ-002",
        "description": "Burn-in reasoning — cross-document connection",
        "question": "WR-401 had a wire liner replaced yesterday and is showing wire feed stuttering. What is causing this and what should the operator do?",
        "ground_truth": (
            "Wire feed stuttering after a liner replacement is expected behaviour during the burn-in period. "
            "The SOP for WR-401 requires a mandatory burn-in procedure after any wire liner replacement. "
            "The operator should complete the burn-in procedure before resuming production. "
            "This is LOW criticality — expected post-maintenance behaviour, not an equipment failure."
        ),
        "plant_site": "Northgate Automotive",
        "equip_tag":  "WR-401",
        "mode":       "doc",
    }
]

def get_plantmind_answer(case):
    print(f"\n  [{case['id']}] Calling PlantMind...")
    try:
        resp = requests.post(
            f"{FLASK_URL}/ask",
            json={"question": case["question"], "plant_site": case["plant_site"],
                  "equip_tag": case["equip_tag"], "mode": case["mode"]},
            stream=True, timeout=60
        )
        full_text, sources = "", []
        for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
            if not chunk: continue
            if chunk.startswith("SOURCES:"):
                try: sources = json.loads(chunk.replace("SOURCES:", "").strip())
                except: pass
            elif not chunk.startswith(("FALLBACK:", "NOANSWER:")):
                full_text += chunk
        answer   = full_text.strip()
        contexts = [s.get("text") or s.get("content") or s.get("name","") for s in sources]
        contexts = [c for c in contexts if c] or ["No documents retrieved."]
        print(f"  Answer ({len(answer)} chars): {answer[:100]}...")
        print(f"  Contexts: {len(contexts)} chunks retrieved")
        return answer, contexts
    except Exception as e:
        print(f"  ERROR: {e}")
        return "Error retrieving answer.", ["No documents retrieved."]

def build_dataset():
    rows = []
    for case in GOLDEN_CASES:
        answer, contexts = get_plantmind_answer(case)
        rows.append({
            "question":     case["question"],
            "answer":       answer,
            "contexts":     contexts,
            "ground_truth": case["ground_truth"]
        })
        time.sleep(3)
    return Dataset.from_list(rows)

def run_ragas(dataset):
    print("\n  Setting up Ragas judge...")
    print("  Using Groq via OpenAI-compatible endpoint")

    # Ragas needs an OpenAI-compatible client
    # Groq supports this via their v1 endpoint
    groq_as_openai = OpenAI(
        api_key=GROQ_KEY,
        base_url="https://api.groq.com/openai/v1"
    )

    judge = llm_factory(
        model="llama-3.1-8b-instant",
        provider="openai",          # openai adapter works with any OpenAI-compatible API
        client=groq_as_openai
    )

    metrics = [faithfulness, context_recall]
    for metric in metrics:
        metric.llm = judge

    print(f"  Running {len(metrics)} metrics on {len(dataset)} cases...")
    print("  (~6-8 LLM calls per case, this takes ~60 seconds...)\n")

    result = evaluate(dataset=dataset, metrics=metrics, raise_exceptions=False)
    return result

def print_results(result):
    print("\n" + "="*60)
    print("RAGAS RESULTS — PlantMind PM-RAGAS-01")
    print("="*60)

    df = result.to_pandas()

    for i, case in enumerate(GOLDEN_CASES):
        row = df.iloc[i]
        print(f"\n{case['id']}: {case['description']}")
        for col in ['faithfulness', 'context_recall']:
            if col in row:
                try:
                    val  = float(row[col])
                    icon = "PASS" if val >= 0.8 else "WARN" if val >= 0.5 else "FAIL"
                    print(f"  [{icon}] {col}: {val:.2f}")
                except:
                    print(f"  [????] {col}: {row[col]}")

    print(f"\n{'─'*40}")
    print("AVERAGES vs TARGETS")
    targets = {'faithfulness': 1.0, 'context_recall': 0.85}
    for col, target in targets.items():
        if col in df.columns:
            try:
                avg = float(df[col].mean())
                gap = target - avg
                status = "✓" if gap <= 0 else f"need +{gap:.2f}"
                print(f"  {col}: {avg:.2f}  (target {target}) {status}")
            except:
                pass

    os.makedirs("evals", exist_ok=True)
    output = {
        "run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "judge":  "llama-3.1-8b via Groq OpenAI-compat",
        "cases":  len(GOLDEN_CASES),
        "scores": {},
        "per_case": df.to_dict(orient="records")
    }
    for col in ['faithfulness', 'context_recall']:
        if col in df.columns:
            try: output["scores"][col] = round(float(df[col].mean()), 3)
            except: pass

    with open("evals/ragas_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Full results saved to evals/ragas_results.json")
    print("="*60)

if __name__ == "__main__":
    print("="*60)
    print("PlantMind — Ragas Evaluation (PM-RAGAS-01)")
    print("2 golden cases: spatter threshold + burn-in reasoning")
    print(f"Flask: {FLASK_URL}")
    print("="*60)
    input("\nPress Enter when Flask is running...\n")

    print("Step 1: Getting answers from PlantMind...")
    dataset = build_dataset()

    print("\nStep 2: Running Ragas evaluation...")
    result = run_ragas(dataset)

    print("\nStep 3: Results")
    print_results(result)
