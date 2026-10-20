#!/usr/bin/env python3
"""Deterministic half of the rulebook-audit loop.

The model does judgment. This script does everything that must be exact:
  plan      rules.json + repo            -> jobs.jsonl   (shard x rule batches)
  coverage  jobs.jsonl + raw/*.json      -> which jobs silently skipped rules
  verify    raw findings                 -> findings that quote real text (+ relocated line numbers)
  report    verified findings            -> dedup, suppress, baseline diff, report.md, exit code

No third-party dependencies.
"""
import argparse, hashlib, json, os, re, subprocess, sys
from pathlib import Path

AUDIT = Path(".audit")
RULE_TEXTS = ""
SKIP_DIRS = {".git", "node_modules", "dist", "build", ".audit", "vendor", "__pycache__", ".venv"}


# ---------- helpers ----------
def load_json(p, default=None):
    p = Path(p)
    return json.loads(p.read_text()) if p.exists() else default

def norm(s: str) -> str:
    """Whitespace-insensitive comparison: models reflow indentation when quoting."""
    return re.sub(r"\s+", " ", s or "").strip()

def repo_files(root: Path):
    try:  # respect .gitignore when possible
        out = subprocess.run(["git", "-C", str(root), "ls-files"], capture_output=True, text=True, check=True).stdout
        files = [f for f in out.splitlines() if f]
        if files:
            return files
    except Exception:
        pass
    files = []
    for dp, dns, fns in os.walk(root):
        dns[:] = [d for d in dns if d not in SKIP_DIRS]
        for fn in fns:
            files.append(str(Path(dp, fn).relative_to(root)))
    return files

def glob_re(g):
    """Gitignore-style globs: ** crosses directories (and may be empty), * does not."""
    out, i = "", 0
    while i < len(g):
        if g.startswith("**/", i): out += "(?:.*/)?"; i += 3
        elif g.startswith("**", i): out += ".*"; i += 2
        elif g[i] == "*": out += "[^/]*"; i += 1
        elif g[i] == "?": out += "[^/]"; i += 1
        else: out += re.escape(g[i]); i += 1
    return re.compile(out + r"\Z")

def matches(path, globs):
    return any(glob_re(g).match(path) for g in globs)

def shard_of(path, depth):
    parts = Path(path).parts
    return "/".join(parts[:depth]) if len(parts) > depth else (parts[0] if len(parts) > 1 else ".")

def fingerprint(f):
    """Stable across reruns and line shifts: rule ids + file + normalized evidence."""
    key = "|".join([",".join(sorted(f["rule_ids"])), f.get("file", ""), norm(f["evidence"])[:400]])
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# ---------- check-rules ----------
def cmd_check_rules(a):
    """Gate before human approval: rule text must be verbatim, ids unique, scopes non-empty."""
    rules = load_json(a.rules)["rules"]
    rb = norm(Path(a.rulebook).read_text())
    problems, seen = [], set()
    for r in rules:
        if r["id"] in seen: problems.append(f"{r['id']}: duplicate id")
        seen.add(r["id"])
        if norm(r["text"]) not in rb: problems.append(f"{r['id']}: text is not verbatim from the rulebook")
        if not r["scope"]: problems.append(f"{r['id']}: empty scope")
        if r["kind"] == "mechanical" and not r.get("check"): problems.append(f"{r['id']}: mechanical but no check command")
    for p in problems: print("  ⚠", p)
    print(f"{len(rules)} rules, {len(problems)} problems")
    sys.exit(1 if problems else 0)


# ---------- plan ----------
def cmd_plan(a):
    rules = load_json(a.rules)["rules"]
    files = repo_files(Path(a.repo))
    jobs, unmatched = [], []
    shards = {}  # shard -> set(rule ids)
    for r in rules:
        if r["kind"] == "mechanical" and r.get("check"):
            continue  # handled by run.sh without a model
        hit = [f for f in files if matches(f, r["scope"])]
        if not hit:
            unmatched.append(r["id"])
            continue
        for f in hit:
            shards.setdefault(shard_of(f, a.depth), set()).add(r["id"])
    for shard, ids in sorted(shards.items()):
        ids = sorted(ids)
        for i in range(0, len(ids), a.batch):
            jobs.append({"job": f"{shard.replace('/', '__')}.{i // a.batch}", "shard": shard, "rule_ids": ids[i:i + a.batch]})
    AUDIT.mkdir(exist_ok=True)
    with open(AUDIT / "jobs.jsonl", "w") as fh:
        for j in jobs:
            fh.write(json.dumps(j) + "\n")
    (AUDIT / "unmatched_scope.json").write_text(json.dumps(unmatched, indent=2))
    print(f"{len(jobs)} jobs over {len(shards)} shards; {len(unmatched)} rules match no files")


# ---------- coverage ----------
def cmd_coverage(a):
    """Exit 1 and list jobs to retry if any job output is missing, invalid, or skipped a rule."""
    retry = []
    for line in open(AUDIT / "jobs.jsonl"):
        j = json.loads(line)
        out = load_json(AUDIT / "raw" / f"{j['job']}.json")
        if not out or "checked" not in out:
            retry.append(j["job"]); continue
        missing = set(j["rule_ids"]) - set(out["checked"])
        if missing:
            retry.append(j["job"])
            print(f"{j['job']}: skipped {sorted(missing)}", file=sys.stderr)
    (AUDIT / "retry.txt").write_text("\n".join(retry))
    print(f"{len(retry)} jobs need retry")
    sys.exit(1 if retry else 0)


# ---------- verify ----------
def cmd_verify(a):
    rules = load_json(a.rules)["rules"]
    rule_ids = {r["id"] for r in rules}
    global RULE_TEXTS
    RULE_TEXTS = " || ".join(norm(r["text"]) for r in rules)
    rulebook = norm(Path(a.rulebook).read_text())
    kept, rejected = [], []
    for p in sorted((AUDIT / "raw").glob("*.json")):
        out = load_json(p) or {}
        for f in out.get("findings", []):
            f["_source"] = p.stem
            why = check_one(f, Path(a.repo), rulebook, rule_ids)
            (rejected if why else kept).append({**f, "_rejected": why} if why else f)
    (AUDIT / "verified.json").write_text(json.dumps(kept, indent=2))
    (AUDIT / "rejected.json").write_text(json.dumps(rejected, indent=2))
    print(f"kept {len(kept)}, rejected {len(rejected)} (see .audit/rejected.json)")

def check_one(f, repo, rulebook, rule_ids):
    # accept a parent id when extraction split a rule (CFG-1 -> CFG-1.a, CFG-1.b)
    unknown = {i for i in f["rule_ids"] if i not in rule_ids and not any(r.startswith(i + ".") for r in rule_ids)}
    if unknown:
        return f"unknown rule ids {sorted(unknown)}"
    if f.get("rule_quote") and norm(f["rule_quote"]) not in rulebook \
            and norm(f["rule_quote"]) not in RULE_TEXTS:
        return "rule_quote not found verbatim in rulebook"
    if f["kind"] == "unverifiable" or f.get("_mechanical"):
        return None
    if not f.get("file"):  # rulebook-level finding
        return None if norm(f["evidence"]) in rulebook else "evidence not found in rulebook"
    path = repo / f["file"]
    if not path.is_file():
        return "cited file does not exist"
    lines = path.read_text(errors="replace").splitlines()
    ev = norm(f["evidence"])
    s, e = f.get("line_start", 1), f.get("line_end", f.get("line_start", 1))
    window = norm("\n".join(lines[max(0, s - 4):e + 3]))
    if ev and ev in window:
        return None
    # relocate: quote is real but line numbers are off
    for i in range(len(lines)):
        n = max(1, (e - s) + 1)
        if ev and ev in norm("\n".join(lines[i:i + n + 3])):
            f["line_start"], f["line_end"], f["_relocated"] = i + 1, i + n, True
            return None
    return "evidence not found in cited file"


# ---------- report ----------
def cmd_report(a):
    found = load_json(AUDIT / "final.json") or load_json(AUDIT / "verified.json", [])
    supp = {s["fingerprint"]: s for s in load_json(a.suppressions, [])}
    base = set(load_json(a.baseline, []))
    uniq = {}
    for f in found:
        fp = fingerprint(f)
        f["fingerprint"] = fp
        if f["confidence"] < a.min_confidence or fp in supp:
            continue
        if fp not in uniq or f["confidence"] > uniq[fp]["confidence"]:
            uniq[fp] = f
    findings = sorted(uniq.values(), key=lambda f: ({"high": 0, "medium": 1, "low": 2}[f["severity"]], f.get("file", "")))
    new = [f for f in findings if f["fingerprint"] not in base]
    (AUDIT / "findings.json").write_text(json.dumps(findings, indent=2))
    if a.update_baseline:
        Path(a.baseline).write_text(json.dumps(sorted(uniq), indent=2))

    unmatched = load_json(AUDIT / "unmatched_scope.json", [])
    retry = [x for x in (AUDIT / "retry.txt").read_text().splitlines() if x] if (AUDIT / "retry.txt").exists() else []
    L = ["# Rulebook audit", "",
         f"{len(findings)} findings ({len(new)} new since baseline). "
         f"Rejected by evidence check: {len(load_json(AUDIT / 'rejected.json', []))}.", ""]
    if retry:
        L += [f"**Incomplete coverage:** {len(retry)} jobs failed after retry: {', '.join(retry)}", ""]
    if unmatched:
        L += [f"**Rules whose scope matches no files** (possible gap or stale rule): {', '.join(unmatched)}", ""]
    for kind in ["conflict", "gap", "ambiguity", "violation", "unverifiable"]:
        group = [f for f in findings if f["kind"] == kind]
        if not group:
            continue
        L += [f"## {kind.capitalize()} ({len(group)})", ""]
        for f in group:
            loc = f"`{f['file']}:{f.get('line_start', '?')}`" if f.get("file") else "rulebook"
            tag = " 🆕" if f in new else ""
            L += [f"### [{f['severity']}] {', '.join(f['rule_ids'])} — {loc}{tag}",
                  f"{f['explanation']}", "", "```", f["evidence"].strip()[:800], "```",
                  f"<sub>confidence {f['confidence']:.2f} · fp `{f['fingerprint']}`</sub>", ""]
    (AUDIT / "report.md").write_text("\n".join(L))
    print(f"report: .audit/report.md ({len(findings)} findings, {len(new)} new)")
    sys.exit(2 if any(f["severity"] == "high" for f in new) and a.fail_on_new_high else 0)


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("check-rules"); p.add_argument("--rules", default=".audit/rules.json")
    p.add_argument("--rulebook", required=True); p.set_defaults(fn=cmd_check_rules)
    p = sp.add_parser("plan"); p.add_argument("--rules", default=".audit/rules.json"); p.add_argument("--repo", default=".")
    p.add_argument("--depth", type=int, default=2, help="path depth that defines a shard, e.g. 2 = services/<name>")
    p.add_argument("--batch", type=int, default=6, help="rules per job"); p.set_defaults(fn=cmd_plan)
    p = sp.add_parser("coverage"); p.set_defaults(fn=cmd_coverage)
    p = sp.add_parser("verify"); p.add_argument("--rules", default=".audit/rules.json"); p.add_argument("--repo", default=".")
    p.add_argument("--rulebook", required=True); p.set_defaults(fn=cmd_verify)
    p = sp.add_parser("report"); p.add_argument("--suppressions", default=".audit/suppressions.json")
    p.add_argument("--baseline", default=".audit/baseline.json"); p.add_argument("--min-confidence", type=float, default=0.5)
    p.add_argument("--update-baseline", action="store_true"); p.add_argument("--fail-on-new-high", action="store_true")
    p.set_defaults(fn=cmd_report)
    a = ap.parse_args(); a.fn(a)

if __name__ == "__main__":
    main()
