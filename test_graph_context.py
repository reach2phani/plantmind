"""
Test what graph context looks like when fetched for WM-101
"""
import os, sys
sys.path.insert(0, r'C:\plantmind') if os.name == 'nt' else None

from dotenv import load_dotenv
load_dotenv()

from knowledge_graph import get_fault_chain

print("Fetching fault chain for WM-101...")
chain = get_fault_chain("WM-101", "wire_feed_overload")

print(f"\nhas_data    : {chain['has_data']}")
print(f"nodes found : {len(chain['chain_nodes'])}")
print(f"warnings    : {len(chain['warnings'])}")
print(f"downtime    : {chain['downtime']}")
print(f"\n=== CHAIN TEXT (what orchestrator receives) ===\n")
print(chain['chain_text'])
print(f"\n=== WARNINGS ===")
for w in chain['warnings']:
    print(f"  - {w}")
