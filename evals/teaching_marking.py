"""
teaching_marking.py — Evals teaching set, step 3: does the AI judge agree with a person?

WHAT THIS IS (simple version)
    The AI judge marked L1, L3 and L5 on every answer. Before we believe those
    marks, a person marks a sample of the same answers WITHOUT seeing the
    judge's marks, and we count how often the two agree.

    build   picks 10 real answers (5 graph OFF, 5 graph ON, all three wordings),
            shuffles them, labels them A1..A10 so you cannot tell OFF from ON,
            removes personal names, and writes a marking page.
    score   reads your marks and compares them with the judge.

RUN (from C:\\plantmind)
    venv\\Scripts\\python.exe evals\\teaching_marking.py build
      -> open evals\\fl101\\results\\teaching_step3_marking_sheet.html in a browser,
         mark every answer, press "Copy my marks", paste them into
         evals\\fl101\\results\\teaching_step3_human_marks.json
    venv\\Scripts\\python.exe evals\\teaching_marking.py score

    Do NOT open teaching_step3_key.json before marking: it holds the judge's marks.

OUTPUT
    evals/fl101/results/teaching_step3_marking_sheet.html   the page you mark
    evals/fl101/results/teaching_step3_key.json             answer ids -> run + judge marks
    evals/fl101/results/teaching_step3_agreement.md         the result (after score)
"""

import hashlib
import html
import json
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "evals" / "fl101" / "results"
SPEC = json.loads((ROOT / "evals" / "fl101" / "teaching_cases.json").read_text(encoding="utf-8"))
CHECKS = {c["id"]: c for c in SPEC["checks"]}
MARKED = ["L1", "L3", "L5"]          # the judge's lines; L2 and L4 are code
NAMES = ["A. Moreno", "J. Kim", "K. Brandt", "L. Haddad", "M. Varga", "N. Adeyemi",
         "P. Singh", "R. Osei", "T. Novak"]   # every person named in demo_data/fl101
# Which runs go on the sheet: (wording, graph arm, which run of that pair).
PICK = [("T-1", "off", 0), ("T-1", "off", 1), ("T-2", "off", 0), ("T-3", "off", 0), ("T-3", "off", 1),
        ("T-1", "on", 0), ("T-1", "on", 3), ("T-2", "on", 0), ("T-2", "on", 1), ("T-3", "on", 0)]


def scrub(text):
    for n in NAMES:
        text = text.replace(n, "[name]")
    # Hide which arm an answer came from: graph-ON reports name the knowledge
    # graph in their sources, which would tell the marker "this is ON". The
    # three marked lines are about what the operator is told to do, so the
    # wording of a source name never decides a mark.
    return re.sub(r"(?i)knowledge[\s-]*graph|\bgraph\b", "[source]", text)


def answer_body(report):
    """What the reader judges: the report, without the code-made confidence block."""
    return re.sub(r"REPORT CONFIDENCE:.*?(?=\n\n|\nSOURCE DATA)", "", report, flags=re.S).strip()


def build():
    runs = [json.loads(l) for l in (RES / "teaching_runs.jsonl").read_text(encoding="utf-8").splitlines()
            if l.strip()]
    runs = [r for r in runs if not r.get("failed")]
    cache = json.loads((RES / "teaching_judge_cache.json").read_text(encoding="utf-8"))
    chosen = []
    for case, arm, idx in PICK:
        same = [r for r in runs if r["case"] == case and r["arm"] == arm]
        r = same[idx]
        digest = hashlib.sha1(r["report"].encode("utf-8")).hexdigest()[:12]
        judge = {lid: cache.get(f"{case}|{arm}|{lid}|{digest}") for lid in MARKED}
        chosen.append({"case": case, "arm": arm, "run": idx + 1, "judge": judge,
                       "text": scrub(answer_body(r["report"]))})
    random.Random(20261002).shuffle(chosen)
    for i, c in enumerate(chosen, 1):
        c["id"] = f"A{i}"

    key = [{k: c[k] for k in ("id", "case", "arm", "run", "judge")} for c in chosen]
    (RES / "teaching_step3_key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    missing = [(k["id"], l) for k in key for l, v in k["judge"].items() if v is None]
    if missing:
        print(f"WARNING: no judge mark found for {missing} (run --score in graph_value_test first)")

    qs = "".join(f'<li><b>{lid}</b> {html.escape(CHECKS[lid]["q"])}</li>' for lid in MARKED)
    cards = []
    for c in chosen:
        btns = "".join(
            f'<div class="row"><span class="lid">{lid}</span>'
            f'<button data-a="{c["id"]}" data-l="{lid}" data-v="YES">YES</button>'
            f'<button data-a="{c["id"]}" data-l="{lid}" data-v="NO">NO</button></div>' for lid in MARKED)
        cards.append(f'<section><h2>{c["id"]}</h2><pre>{html.escape(c["text"])}</pre>'
                     f'<div class="marks">{btns}</div></section>')
    page = PAGE.replace("{{QUESTIONS}}", qs).replace("{{CARDS}}", "\n".join(cards)) \
               .replace("{{IDS}}", json.dumps([c["id"] for c in chosen]))
    (RES / "teaching_step3_marking_sheet.html").write_text(page, encoding="utf-8")
    print(f"Marking sheet: {RES / 'teaching_step3_marking_sheet.html'}")
    print("Mark every answer, press 'Copy my marks', paste into "
          f"{RES / 'teaching_step3_human_marks.json'}, then run: score")


def score():
    key = json.loads((RES / "teaching_step3_key.json").read_text(encoding="utf-8"))
    human = json.loads((RES / "teaching_step3_human_marks.json").read_text(encoding="utf-8"))
    rows, agree, total, disagree = [], 0, 0, []
    for k in key:
        for lid in MARKED:
            h = (human.get(k["id"]) or {}).get(lid)
            j = k["judge"].get(lid)
            if h is None or j is None:
                rows.append((k, lid, h, j, "not compared"))
                continue
            h_yes, same = h == "YES", (h == "YES") == j
            total += 1
            agree += same
            if not same:
                disagree.append((k, lid, h, "YES" if j else "NO"))
            rows.append((k, lid, h, "YES" if j else "NO", "agree" if same else "DISAGREE"))
    lines = ["# Teaching set — step 3: does the AI judge agree with a person?", "",
             "10 real answers (5 graph OFF, 5 graph ON, all three wordings), shuffled and labelled "
             "A1–A10 so the marker could not tell OFF from ON. Personal names removed. The person "
             "marked L1, L3 and L5 without seeing the judge's marks.", "",
             f"**Judge agrees with the person on {agree}/{total} marks.**", "",
             "## Every disagreement", ""]
    if disagree:
        lines += ["| Answer | Wording | Graph | Line | Person | Judge |", "|---|---|---|---|---|---|"]
        lines += [f"| {k['id']} | {k['case']} | {k['arm'].upper()} | {lid} | {h} | {j} |"
                  for k, lid, h, j in disagree]
    else:
        lines.append("None.")
    lines += ["", "## All marks", "", "| Answer | Wording | Graph | Line | Person | Judge | |",
              "|---|---|---|---|---|---|---|"]
    lines += [f"| {k['id']} | {k['case']} | {k['arm'].upper()} | {lid} | {h} | {j} | {v} |"
              for k, lid, h, j, v in rows]
    lines += ["", "30 marks from one person: a first calibration, not proof. A disagreement can be the "
              "judge's mistake or the person's; read the answer before deciding which."]
    (RES / "teaching_step3_agreement.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Judge agrees with the person on {agree}/{total} marks; {len(disagree)} disagreement(s).")
    print(f"Scorecard: {RES / 'teaching_step3_agreement.md'}")


PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Marking Sheet</title>
<style>
:root{--bg:#f4f5f1;--card:#fff;--ink:#1d2623;--muted:#5a6560;--line:#d6dbd2;--yes:#2d6a58;--no:#a4473a}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 system-ui,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:24px 16px 80px}
h1{font-size:1.4rem;margin:0 0 6px}.lead{color:var(--muted)}
ol{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 14px 14px 34px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:18px 0;padding:14px 16px}
h2{margin:0 0 8px;font-size:1.1rem}
pre{white-space:pre-wrap;font:13px/1.5 ui-monospace,monospace;background:#fafaf7;border:1px solid var(--line);
border-radius:8px;padding:10px;max-height:420px;overflow:auto}
.marks{display:flex;gap:18px;flex-wrap:wrap;margin-top:10px}.row{display:flex;gap:6px;align-items:center}
.lid{font-weight:600;width:24px}
button{border:1px solid var(--line);background:#fff;border-radius:7px;padding:6px 12px;cursor:pointer;font:inherit}
button.on[data-v=YES]{background:var(--yes);color:#fff;border-color:var(--yes)}
button.on[data-v=NO]{background:var(--no);color:#fff;border-color:var(--no)}
.bar{position:fixed;bottom:0;left:0;right:0;background:var(--card);border-top:1px solid var(--line);padding:10px 16px;
display:flex;gap:12px;align-items:center;justify-content:center}
#copy{background:var(--ink);color:#fff;border:none}#status{color:var(--muted);font-size:13px}
</style></head><body><div class="wrap">
<h1>Step 3 marking sheet</h1>
<p class="lead">For each answer, mark the three lines YES or NO. Judge only what the answer says.
Don't open the key file until you're done.</p>
<ol>{{QUESTIONS}}</ol>
{{CARDS}}
</div>
<div class="bar"><span id="status"></span><button id="copy">Copy my marks</button></div>
<script>
var ids = {{IDS}}, marks = {};
try { marks = JSON.parse(localStorage.getItem('pm-step3') || '{}'); } catch (e) {}
function paint(){
  document.querySelectorAll('button[data-a]').forEach(function(b){
    b.classList.toggle('on', (marks[b.dataset.a]||{})[b.dataset.l] === b.dataset.v); });
  var done = ids.reduce(function(n,i){ return n + Object.keys(marks[i]||{}).length; }, 0);
  document.getElementById('status').textContent = done + ' / ' + (ids.length*3) + ' marks';
}
document.querySelectorAll('button[data-a]').forEach(function(b){
  b.onclick = function(){ (marks[b.dataset.a] = marks[b.dataset.a] || {})[b.dataset.l] = b.dataset.v;
    try { localStorage.setItem('pm-step3', JSON.stringify(marks)); } catch (e) {} paint(); };
});
document.getElementById('copy').onclick = function(){
  var t = JSON.stringify(marks, null, 1);
  navigator.clipboard.writeText(t).then(function(){ document.getElementById('status').textContent = 'Copied. Paste into teaching_step3_human_marks.json'; },
    function(){ prompt('Copy these marks:', t); });
};
paint();
</script></body></html>"""


if __name__ == "__main__":
    {"build": build, "score": score}.get((sys.argv[1:] or [""])[0],
                                         lambda: print("usage: teaching_marking.py build | score"))()
