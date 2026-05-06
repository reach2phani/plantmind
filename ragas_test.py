"""
ragas_test.py — PM-RAGAS-01
PlantMind RAG evaluation using Ragas 0.4.x + Groq
Fetches contexts directly from Pinecone for accurate faithfulness scoring.
"""
import os, json, time, requests
from dotenv import load_dotenv
load_dotenv()

from openai import OpenAI
from pinecone import Pinecone
from ragas import evaluate
from ragas.metrics import faithfulness, context_recall
from ragas.llms import llm_factory
from datasets import Dataset

FLASK_URL = "http://localhost:5000"
GROQ_KEY  = os.getenv("GROQ_API_KEY")
pc        = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
pine_idx  = pc.Index(os.getenv("PINECONE_INDEX"))

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
        "question": "After replacing the wire liner on WR-401, what does the SOP require the operator to do before resuming production?",
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

def get_answer(case):
    print(f"\n  [{case['id']}] Getting answer from PlantMind...")
    try:
        resp = requests.post(f"{FLASK_URL}/ask",
            json={"question": case["question"], "plant_site": case["plant_site"],
                  "equip_tag": case["equip_tag"], "mode": case["mode"]},
            stream=True, timeout=60)
        text = ""
        for chunk in resp.iter_content(chunk_size=None, decode_unicode=True):
            if chunk and not chunk.startswith(("SOURCES:","FALLBACK:","NOANSWER:")):
                text += chunk
        answer = text.strip()
        print(f"  Answer: {answer[:100]}...")
        return answer
    except Exception as e:
        print(f"  ERROR: {e}")
        return "Error."

def get_contexts(case):
    print(f"  [{case['id']}] Fetching contexts from Pinecone...")
    try:
        emb = pc.inference.embed(model="multilingual-e5-large",
            inputs=[case["question"]], parameters={"input_type":"query"})
        vec = emb[0].values
        res = pine_idx.query(vector=vec, top_k=8,
            filter={"equip_tag":{"$eq":case["equip_tag"]}}, include_metadata=True)
        ctxs = [f"[From {m.metadata.get('name','')}]:\n{m.metadata.get('text','')}"
                for m in res.matches if m.metadata.get("text","")]
        print(f"  Got {len(ctxs)} chunks")
        return ctxs or ["No documents retrieved."]
    except Exception as e:
        print(f"  Pinecone error: {e}")
        return ["No documents retrieved."]

def build_dataset():
    rows = []
    for case in GOLDEN_CASES:
        answer   = get_answer(case)
        contexts = get_contexts(case)
        rows.append({"question": case["question"], "answer": answer,
                     "contexts": contexts, "ground_truth": case["ground_truth"]})
        time.sleep(3)
    return Dataset.from_list(rows)

def run_ragas(dataset):
    print("\n  Setting up Ragas judge (Groq llama-3.1-8b)...")
    client = OpenAI(api_key=GROQ_KEY, base_url="https://api.groq.com/openai/v1")
    judge  = llm_factory(model="llama-3.1-8b-instant", provider="openai", client=client)
    metrics = [faithfulness, context_recall]
    for m in metrics: m.llm = judge
    print(f"  Running on {len(dataset)} cases (~60 seconds)...\n")
    return evaluate(dataset=dataset, metrics=metrics, raise_exceptions=False)

def print_results(result):
    print("\n" + "="*60)
    print("RAGAS RESULTS — PlantMind PM-RAGAS-01")
    print("="*60)
    df = result.to_pandas()
    for i, case in enumerate(GOLDEN_CASES):
        row = df.iloc[i]
        print(f"\n{case['id']}: {case['description']}")
        for col in ['faithfulness','context_recall']:
            if col in row:
                try:
                    v = float(row[col])
                    icon = "PASS" if v>=0.8 else "WARN" if v>=0.5 else "FAIL"
                    print(f"  [{icon}] {col}: {v:.2f}")
                except: print(f"  [????] {col}: {row[col]}")
    print(f"\n{'─'*40}")
    targets = {'faithfulness':1.0, 'context_recall':0.85}
    for col, t in targets.items():
        if col in df.columns:
            try:
                avg = float(df[col].mean())
                print(f"  {col}: {avg:.2f}  (target {t}) {'✓' if avg>=t else f'gap {t-avg:+.2f}'}")
            except: pass
    os.makedirs("evals", exist_ok=True)
    out = {"run_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "judge": "llama-3.1-8b Groq", "context_source": "Pinecone direct",
           "scores": {c: round(float(df[c].mean()),3) for c in ['faithfulness','context_recall'] if c in df.columns},
           "per_case": df.to_dict(orient="records")}
    with open("evals/ragas_results.json","w") as f: json.dump(out,f,indent=2,default=str)
    print(f"\n  Saved to evals/ragas_results.json")
    print("="*60)

if __name__ == "__main__":
    print("="*60)
    print("PlantMind Ragas Evaluation — contexts from Pinecone directly")
    print("="*60)
    input("\nPress Enter when Flask is running...\n")
    dataset = build_dataset()
    result  = run_ragas(dataset)
    print_results(result)
