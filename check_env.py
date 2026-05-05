"""
check_env.py - Environment diagnostic for PlantMind
Run: python check_env.py
"""
import sys
print(f"Python: {sys.version}")
print(f"Python path: {sys.executable}")
print()

# Check all required packages
packages = [
    'flask', 'groq', 'pinecone', 'supabase', 
    'dotenv', 'openai', 'langchain_groq',
    'ragas', 'datasets'
]

print("Package versions:")
for pkg in packages:
    try:
        mod = __import__(pkg)
        ver = getattr(mod, '__version__', 'installed')
        print(f"  {pkg}: {ver}")
    except ImportError:
        print(f"  {pkg}: MISSING")

print()

# Check env vars
from dotenv import load_dotenv
load_dotenv()
import os

print("Environment variables:")
keys = ['GROQ_API_KEY', 'PINECONE_API_KEY', 'PINECONE_INDEX', 'SUPABASE_URL', 'SUPABASE_KEY']
for k in keys:
    v = os.getenv(k)
    print(f"  {k}: {'OK (' + v[:8] + '...)' if v else 'MISSING'}")

print()

# Check connections one by one
print("Connections:")
try:
    from supabase import create_client
    sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    sb.table("documents").select("id").limit(1).execute()
    print("  Supabase: OK")
except Exception as e:
    print(f"  Supabase: FAILED - {e}")

try:
    from pinecone import Pinecone
    pc = Pinecone(api_key=os.getenv("PINECONE_API_KEY"))
    idx = pc.Index(os.getenv("PINECONE_INDEX"))
    print("  Pinecone: OK")
except Exception as e:
    print(f"  Pinecone: FAILED - {e}")

try:
    from groq import Groq
    g = Groq(api_key=os.getenv("GROQ_API_KEY"))
    print("  Groq: OK")
except Exception as e:
    print(f"  Groq: FAILED - {e}")

print()

# Check PlantMind modules
print("PlantMind modules:")
modules = ['llm_logger', 'multi_agent', 'embedder']
for m in modules:
    try:
        __import__(m)
        print(f"  {m}: OK")
    except Exception as e:
        print(f"  {m}: FAILED - {e}")

print()
print("Done - if all OK above, Flask should start fine")
input("Press Enter to exit")
