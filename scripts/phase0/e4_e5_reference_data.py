"""
Phase 0 · Batch E4 + E5 — fill gaps in the equipment list and parts inventory.

THE PROBLEMS
  E4: the gas cutter, press and furnace have no equipment type.
  E5: the WM-101 work instruction lists 1.0mm parts (GSW-LINER-10,
      GSW-DROLL-10, GSW-TIP-10) that the inventory doesn't have, and the SOP
      specifies C25 gas (Argon/CO2 75/25) while the only gas SKU is 80/20.
      The work-order agent can only order parts the inventory contains.

THE FIX
  E4: set type only. Manufacturers are NOT filled in — they aren't recorded
      anywhere, and inventing them would add false data.
  E5: ADD the missing parts. Existing parts are not renamed or changed.
      New parts start at quantity 0 (not stocked), so a work order flags them
      for reordering. Cost, supplier and lead time are copied from the
      matching 0.8mm / existing gas part — marked below; adjust if known.

HOW TO RUN
  1. Preview (changes nothing):   python scripts\\phase0\\e4_e5_reference_data.py
  2. Apply:                       python scripts\\phase0\\e4_e5_reference_data.py --apply

COST: none (plain database writes).
"""
import os
import sys

PROJECT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
os.chdir(PROJECT_DIR)

from dotenv import load_dotenv            # noqa: E402
load_dotenv(os.path.join(PROJECT_DIR, ".env"))
from supabase import create_client        # noqa: E402

APPLY = "--apply" in sys.argv
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

EQUIPMENT_TYPES = {"GC-201": "Gas Cutter", "HC-401": "Press", "HT-301": "Furnace"}

NEW_PARTS = [  # (new sku, name, copy cost/supplier/lead time from, equip_tag)
    ("GSW-LINER-10", "Wire Liner 1.0mm (torch assembly)",  "GSW-LINER-08", "WM-101"),
    ("GSW-DROLL-10", "Drive Rolls (1.0mm groove)",          "GSW-DROLL-08", "WM-101"),
    ("GSW-TIP-10",   "Contact Tip 1.0mm (pack of 10)",      "GSW-TIP-08",   "WM-101"),
    ("GSW-GAS-C25",  "Shielding Gas Cylinder (Ar/CO2 75/25, C25 — per WM-101 SOP)", "GSW-GAS-CO2", None),
]

print(f"\n{'APPLYING' if APPLY else 'PREVIEW (nothing will change)'}\n")

print("E4 — equipment types")
equip = {e["equip_tag"]: e for e in (sb.table("equipment").select("*").execute().data or [])}
for tag, new_type in EQUIPMENT_TYPES.items():
    current = (equip.get(tag) or {}).get("type") or ""
    if tag not in equip:
        print(f"  {tag}: not found, skipped")
    elif current == new_type:
        print(f"  {tag}: already '{new_type}'")
    else:
        print(f"  {tag}: type {current or '(blank)'!r} -> {new_type!r}   (manufacturer left blank: unknown)")
        if APPLY:
            sb.table("equipment").update({"type": new_type}).eq("equip_tag", tag).execute()

print("\nE5 — parts inventory (add only)")
parts = {p["sku"]: p for p in (sb.table("parts_inventory").select("*").execute().data or [])}
for sku, name, copy_from, equip_tag in NEW_PARTS:
    if sku in parts:
        print(f"  {sku}: already exists, skipped")
        continue
    src = parts.get(copy_from)
    if not src:
        print(f"  {sku}: source part {copy_from} missing, skipped")
        continue
    row = {
        "sku": sku, "name": name, "equip_tag": equip_tag,
        "qty_on_hand": 0,
        "reorder_point": src.get("reorder_point"),
        "bin_location": None,
        "unit_cost_usd": src.get("unit_cost_usd"),
        "lead_time_days": src.get("lead_time_days"),
        "supplier_id": src.get("supplier_id"),
    }
    print(f"  ADD {sku}: {name}")
    print(f"      qty 0 (not stocked) · cost ${row['unit_cost_usd']} / lead {row['lead_time_days']}d / "
          f"supplier copied from {copy_from} — adjust if known")
    if APPLY:
        sb.table("parts_inventory").insert(row).execute()

if not APPLY:
    print("\nNothing changed. If this looks right, run again with --apply")
else:
    print("\nDone.")
