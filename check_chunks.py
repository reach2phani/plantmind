"""
check_chunks.py — debug what Pinecone returns for RQ-001
"""
from dotenv import load_dotenv
load_dotenv()
import os
from pinecone import Pinecone

pc  = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
idx = pc.Index(os.getenv("PINECONE_INDEX"))

question = "WR-401 had a wire liner replaced yesterday and is showing wire feed stuttering. What is causing this and what should the operator do?"

emb = pc.inference.embed(
    model="multilingual-e5-large",
    inputs=[question],
    parameters={"input_type":"query"}
)
vec = emb[0].values

results = idx.query(
    vector=vec,
    top_k=8,
    filter={"equip_tag":{"$eq":"WR-401"}},
    include_metadata=True
)

print(f"Top {len(results.matches)} chunks for RQ-001:\n")
for i, m in enumerate(results.matches):
    name  = m.metadata.get("name","")
    text  = m.metadata.get("text","")[:200]
    score = m.score
    print(f"[{i+1}] Score: {score:.3f} | {name}")
    print(f"     {text}")
    print()
