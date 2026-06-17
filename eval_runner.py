"""
eval_runner.py  —  PM-E02
Sends every test case in test_cases.json through the live PlantMind API
and saves the raw responses to eval_results.json.

Usage:
    python eval_runner.py

Make sure your Flask app is running locally first:
    python app.py

Learning concepts in this file:
  - Programmatic AI testing  : treating your AI system like any other software
  - Streaming response handling : collecting streamed chunks into a full response
  - Structured test harness  : input → system → output → save
"""

import json
import time
import requests

# ── Config ────────────────────────────────────────────────────────────
BASE_URL   = "http://localhost:5000"   # your local Flask app
INPUT_FILE = "evals/test_cases.json"
OUTPUT_FILE= "evals/eval_results.json"

# Fallback site, used ONLY when a test case does not declare its own.
# Site now belongs on each test case (input.plant_site), not here.
DEFAULT_PLANT_SITE = "Greenfield Steel Works"


# ── Helpers ───────────────────────────────────────────────────────────

def call_qa(test_case):
    """
    Call the /ask endpoint in doc (Q&A) mode.
    Returns the full answer text and sources list.

    Teaching note: /ask streams the response — we read it chunk by chunk
    and reassemble it. This is how streaming APIs work in practice.
    """
    inp = test_case["input"]

    payload = {
        "question":   inp["question"],
        "plant_site": inp.get("plant_site", DEFAULT_PLANT_SITE),
        "line":       inp.get("line", ""),
        "equip_tag":  inp.get("equipment_id", ""),
        "mode":       "doc",
        "time_from":  "",
        "time_to":    ""
    }

    try:
        response = requests.post(
            f"{BASE_URL}/ask",
            json=payload,
            stream=True,
            timeout=60
        )

        full_text = ""
        sources   = []

        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if not chunk:
                continue

            if chunk.startswith("SOURCES:"):
                first_line = chunk.split("\n")[0]
                try:
                    sources = json.loads(first_line[len("SOURCES:"):])
                except Exception:
                    pass
                rest = "\n".join(chunk.split("\n")[1:])
                full_text += rest
            elif chunk.startswith("NOANSWER:"):
                full_text = chunk[len("NOANSWER:"):]
            elif chunk.startswith("FALLBACK:"):
                pass
            else:
                full_text += chunk

        return {
            "answer":  full_text.strip(),
            "sources": sources,
            "error":   None
        }

    except requests.exceptions.ConnectionError:
        return {"answer": "", "sources": [], "error": "CONNECTION_ERROR — is Flask running?"}
    except Exception as e:
        return {"answer": "", "sources": [], "error": str(e)}


def call_shift_intel(test_case):
    """
    Call the /ask endpoint in shift (Shift Intel) mode.
    """
    inp = test_case["input"]

    payload = {
        "question":   inp["question"],
        "plant_site": inp.get("plant_site", DEFAULT_PLANT_SITE),
        "line":       inp.get("line", ""),
        "equip_tag":  inp.get("equipment_id", ""),
        "mode":       "shift",
        "time_from":  inp.get("time_from") or "",
        "time_to":    inp.get("time_to") or ""
    }

    try:
        response = requests.post(
            f"{BASE_URL}/ask",
            json=payload,
            stream=True,
            timeout=60
        )

        full_text = ""
        sources   = []

        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if not chunk:
                continue
            if chunk.startswith("SOURCES:"):
                first_line = chunk.split("\n")[0]
                try:
                    sources = json.loads(first_line[len("SOURCES:"):])
                except Exception:
                    pass
                rest = "\n".join(chunk.split("\n")[1:])
                full_text += rest
            elif chunk.startswith("NOANSWER:"):
                full_text = chunk[len("NOANSWER:"):]
            elif chunk.startswith("FALLBACK:"):
                pass
            else:
                full_text += chunk

        return {
            "answer":  full_text.strip(),
            "sources": sources,
            "error":   None
        }

    except requests.exceptions.ConnectionError:
        return {"answer": "", "sources": [], "error": "CONNECTION_ERROR — is Flask running?"}
    except Exception as e:
        return {"answer": "", "sources": [], "error": str(e)}


def call_investigation(test_case):
    """
    Call the /investigate endpoint.

    Teaching note: Investigation uses the multi-agent pipeline —
    it takes longer (10-30 seconds) because it makes 4+ LLM calls.
    We set a longer timeout.
    """
    inp = test_case["input"]

    payload = {
        "incident":   inp["incident"],
        "plant_site": inp.get("plant_site", DEFAULT_PLANT_SITE),
        "line":       ""
    }

    try:
        response = requests.post(
            f"{BASE_URL}/investigate",
            json=payload,
            stream=True,
            timeout=120     # investigations take longer — 4 agent calls
        )

        full_text = ""
        for chunk in response.iter_content(chunk_size=None, decode_unicode=True):
            if chunk:
                full_text += chunk

        return {
            "answer":  full_text.strip(),
            "sources": [],
            "error":   None
        }

    except requests.exceptions.ConnectionError:
        return {"answer": "", "sources": [], "error": "CONNECTION_ERROR — is Flask running?"}
    except Exception as e:
        return {"answer": "", "sources": [], "error": str(e)}


# ── Keyword check ─────────────────────────────────────────────────────

def keyword_check(answer, expected):
    """
    Simple keyword pass/fail check — before LLM-as-judge scoring.

    Teaching note: keyword checks are fast and cheap. They catch obvious
    failures (wrong number, missing key term) before spending LLM tokens
    on grading. Always run cheap checks first.
    """
    answer_lower = answer.lower()
    results = {}

    # must_contain — all of these must appear
    must_have = expected.get("must_contain", [])
    for keyword in must_have:
        results[f"must_contain:{keyword}"] = keyword.lower() in answer_lower

    # must_contain_one_of — at least one must appear
    must_one = expected.get("must_contain_one_of", [])
    if must_one:
        results["must_contain_one_of"] = any(
            kw.lower() in answer_lower for kw in must_one
        )

    # must_not_contain — none of these should appear
    must_not = expected.get("must_not_contain", [])
    for keyword in must_not:
        if keyword:
            results[f"must_not_contain:{keyword}"] = keyword.lower() not in answer_lower

    passed = all(results.values())
    return passed, results


# ── Main runner ───────────────────────────────────────────────────────

def run_evals(mode_filter=None, site_filter=None):
    print(f"\n{'='*60}")
    print("PlantMind Eval Runner — PM-E02")
    print(f"{'='*60}\n")

    # Load test cases
    with open(INPUT_FILE) as f:
        data = json.load(f)

    test_cases = data["test_cases"]
    if mode_filter:
        test_cases = [tc for tc in test_cases if tc["mode"] == mode_filter]
        print(f"Filtering to mode '{mode_filter}': {len(test_cases)} cases")
    if site_filter:
        test_cases = [tc for tc in test_cases
                      if tc["input"].get("plant_site", DEFAULT_PLANT_SITE) == site_filter]
        print(f"Filtering to site '{site_filter}': {len(test_cases)} cases")
    if not mode_filter and not site_filter:
        print(f"Loaded {len(test_cases)} test cases (all sites, all modes)\n")
    else:
        print()

    # Check Flask is reachable before running
    try:
        requests.get(BASE_URL, timeout=5)
    except requests.exceptions.ConnectionError:
        print("ERROR: Cannot reach Flask app at", BASE_URL)
        print("Run 'python app.py' first, then re-run this script.\n")
        return

    results  = []
    passed   = 0
    failed   = 0
    errors   = 0

    mode_stats = {"qa": {"pass": 0, "fail": 0}, 
                  "shift_intel": {"pass": 0, "fail": 0},
                  "investigation": {"pass": 0, "fail": 0}}

    for i, tc in enumerate(test_cases):
        tc_id   = tc["id"]
        mode    = tc["mode"]
        desc    = tc["description"]

        print(f"[{i+1:02d}/{len(test_cases)}] {tc_id} — {desc[:50]}...")

        start = time.time()

        # Route to the right endpoint based on mode
        if mode == "qa":
            response = call_qa(tc)
        elif mode == "shift_intel":
            response = call_shift_intel(tc)
        elif mode == "investigation":
            response = call_investigation(tc)
        else:
            response = {"answer": "", "sources": [], "error": f"Unknown mode: {mode}"}

        elapsed = round(time.time() - start, 1)

        if response["error"]:
            status = "ERROR"
            errors += 1
            kw_passed = False
            kw_results = {}
            print(f"         ERROR: {response['error']}")
        else:
            kw_passed, kw_results = keyword_check(response["answer"], tc["expected"])
            status = "PASS" if kw_passed else "FAIL"
            if kw_passed:
                passed += 1
                mode_stats[mode]["pass"] += 1
            else:
                failed += 1
                mode_stats[mode]["fail"] += 1

            # Show which keywords failed
            failures = [k for k, v in kw_results.items() if not v]
            if failures:
                print(f"         FAIL — keyword checks failed: {failures}")
            else:
                print(f"         {status} ({elapsed}s) — {len(response['sources'])} sources")

        # Save full result for PM-E03 (LLM judge) to use later
        results.append({
            "id":           tc_id,
            "mode":         mode,
            "description":  desc,
            "status":       status,
            "elapsed_s":    elapsed,
            "input":        tc["input"],
            "answer":       response["answer"],
            "sources":      response["sources"],
            "keyword_check":kw_results,
            "pass_criteria":tc["pass_criteria"],
            "fail_criteria":tc["fail_criteria"],
            "expected":     tc["expected"],
            "llm_score":    None,   # filled in by PM-E03
            "llm_reasoning":None    # filled in by PM-E03
        })

        # Free tier rate limit delays
        # Investigation (no reflection) = 5 LLM calls: 4x 8b agents + 1x 70b orchestrator
        # 4 agents at 400 tokens each = 1,600 tokens on 8b (under 6,000 TPM)
        # 20s gap is enough for TPM window to clear between investigations
        if mode == "investigation":
            time.sleep(20)
        else:
            time.sleep(3)

    # ── Summary ───────────────────────────────────────────────────────
    total     = len(test_cases)
    pass_rate = round((passed / total) * 100) if total else 0

    print(f"\n{'='*60}")
    print("RESULTS SUMMARY")
    print(f"{'='*60}")
    print(f"Total:   {total}")
    print(f"Passed:  {passed}  ({pass_rate}%)")
    print(f"Failed:  {failed}")
    print(f"Errors:  {errors}")
    print()
    print("By mode:")
    for m, s in mode_stats.items():
        total_m = s["pass"] + s["fail"]
        rate_m  = round((s["pass"] / total_m) * 100) if total_m else 0
        print(f"  {m:15s}  {s['pass']}/{total_m} passing  ({rate_m}%)")

    # ── Save results ──────────────────────────────────────────────────
    output = {
        "run_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "summary": {
            "total":     total,
            "passed":    passed,
            "failed":    failed,
            "errors":    errors,
            "pass_rate": pass_rate,
            "by_mode":   mode_stats
        },
        "results": results
    }

    with open(OUTPUT_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\nFull results saved to: {OUTPUT_FILE}")
    print("Next step: run eval_judge.py (PM-E03) to score with LLM-as-judge\n")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="PlantMind eval runner")
    parser.add_argument("--mode", choices=["qa", "shift", "inv"],
                        help="run only one mode")
    parser.add_argument("--site", help='run only one plant, e.g. --site "Greenfield Steel Works"')
    args = parser.parse_args()

    mode_map = {"qa": "qa", "shift": "shift_intel", "inv": "investigation"}
    mode_filter = mode_map.get(args.mode) if args.mode else None

    run_evals(mode_filter=mode_filter, site_filter=args.site)
