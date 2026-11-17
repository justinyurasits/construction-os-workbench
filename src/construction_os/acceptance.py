"""Grading a drafted PCO against a package acceptance case (expected.yaml), and the case's recorded proposal.

Shared by the offline tests, which replay the recording, and scripts/live_eval.py, which drafts live.
"""
import json
from collections import Counter
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

from construction_os.pricing.general_conditions import gc_applies
from construction_os.pricing.money import cents
from construction_os.rendering import document_text

RECORDING = "recorded_proposal.json"


def cases(corpus):
    root = Path(corpus) / "tests" / "acceptance" / "cases"
    return sorted(p for p in root.iterdir() if p.is_dir()) if root.is_dir() else []


def expected(case):
    return yaml.safe_load((Path(case) / "expected.yaml").read_text())


def money(value):
    return f"{Decimal(value):,.2f}" if value is not None else "—"


def load_recording(case):
    """The case's recording, {"recorded": {...}, "proposal": {...}}, or None if it has none."""
    path = Path(case) / RECORDING
    return json.loads(path.read_text()) if path.is_file() else None


def write_recording(case, result):
    """Save a live draft's accepted proposal as the case's recording, with the prompt version that produced it."""
    manifest = json.loads(Path(result.manifest_path).read_text())
    proposal = json.loads((Path(result.folder) / "proposal.json").read_text())
    recording = {"recorded": {"prompt_version": manifest["model"]["prompt_version"],
                              "model": ", ".join(manifest["model"]["served"]),
                              "date": date.today().isoformat()},
                 "proposal": proposal}
    path = Path(case) / RECORDING
    path.write_text(json.dumps(recording, indent=2, ensure_ascii=False) + "\n")
    return path


def grade(expected, result, package):
    """(checks, flag counts) for a draft case. Each check is (name, expected, got, passed)."""
    draft = json.loads(Path(result.draft_path).read_text())
    if "pricing_structure" in expected["exact"]:
        checks, kinds = compare_structure(expected, result, package, draft)
    else:
        checks, kinds = compare(expected, result)
    return checks + compare_schedule(expected, result, draft), kinds


def compare(expected, result):
    """(checks, flag counts) for a case graded on its exact pricing."""
    exact = expected["exact"]
    pricing = exact["pricing"]
    priced = result.priced
    contract = "explains_difference" in exact
    got_lines = sorted(l.amount for l in priced.lines if l.included and l.amount is not None)
    want_lines = sorted(Decimal(l["amount"]) for l in pricing["lines"] + pricing["pass_through"])
    kinds = Counter(f.kind for f in result.flags)
    checks = [("line amounts", ", ".join(map(money, want_lines)), ", ".join(map(money, got_lines)), got_lines == want_lines),
              ("complete", True, priced.complete, priced.complete)]
    if contract:
        company = exact["explains_difference"]
        checks += [
            ("total (company standard)", money(company["company_pricing_total"]), money(priced.total),
             priced.complete and priced.total == Decimal(company["company_pricing_total"])),
            ("markup percent", company["company_markup_percent"], f"{sum(c.rate for c in priced.components):g}",
             sum(c.rate for c in priced.components) == Decimal(company["company_markup_percent"])),
            ("contract_terms_not_applied", "flagged first", f"{kinds['contract_terms_not_applied']} flag(s)",
             bool(result.flags) and result.flags[0].kind == "contract_terms_not_applied"),
        ]
    else:
        components = [(c.name, c.rate, c.amount) for c in priced.components]
        want = [(m["name"], Decimal(m["percent"]), Decimal(m["amount"])) for m in pricing["markup"]]
        checks += [
            ("subtotal", money(pricing["subtotal"]), money(priced.subtotal), priced.subtotal == Decimal(pricing["subtotal"])),
            ("markup components", "; ".join(f"{n} {r:g}% {money(a)}" for n, r, a in want),
             "; ".join(f"{n} {r:g}% {money(a)}" for n, r, a in components), components == want),
            ("total", money(pricing["total"]), money(priced.total),
             priced.complete and priced.total == Decimal(pricing["total"])),
            ("no contract flag", 0, kinds["contract_terms_not_applied"], kinds["contract_terms_not_applied"] == 0),
        ]
    return checks, kinds


def compare_structure(expected, result, package, draft=None):
    """(checks, flag counts) for a case graded on structure, not a total."""
    draft = draft if draft is not None else json.loads(Path(result.draft_path).read_text())
    want = expected["exact"]["pricing_structure"]
    priced = result.priced
    rows = [(line, draft["cost_lines"][line.index]) for line in priced.lines]
    kinds = Counter(f.kind for f in result.flags)
    checks = [("complete", True, priced.complete, priced.complete)]

    def division(row):
        value = row.get("division")
        return str(value.get("value") if isinstance(value, dict) else value or "").zfill(2)

    for item in want["required_scope"]:
        hits = [line.description for line, row in rows if line.included
                and (not item.get("division") or division(row) == item["division"])
                and (not item.get("category") or line.category == item["category"])
                and any(word in line.description.lower() for word in item["any_of"])]
        checks.append((f"scope: {item['item']}", "a line", "; ".join(hits) or "none", bool(hits)))

    allowed = set(want["every_line_sourced"])
    unsourced = [f"{line.description} ({line.evidence.source if line.evidence else 'none'})"
                 for line, _ in rows if line.included and (not line.evidence or line.evidence.source not in allowed)]
    checks.append(("every line sourced", ", ".join(sorted(allowed)), "; ".join(unsourced) or "all", not unsourced))

    wrong = [f"{line.description}: {line.quantity} × {line.unit_price} ≠ {line.amount}" for line, _ in rows
             if line.included and None not in (line.quantity, line.unit_price, line.amount)
             and cents(line.quantity * line.unit_price) != line.amount]
    markup = sum((c.amount for c in priced.components), Decimal(0))
    discount = priced.discount.amount if priced.discount else Decimal(0)
    sums = priced.total == priced.subtotal + markup - discount + priced.pass_through
    checks.append(("arithmetic exact", "every line and the total multiply and add",
                   "; ".join(wrong) or ("yes" if sums else "the total doesn't add up"), not wrong and sums))

    if want.get("estimated_quantities_on_checklist"):
        estimated = [m for m in draft.get("measurements") or [] if m.get("source") == "estimate"]
        text = document_text(result.checklist_path)
        missing = [m["label"] for m in estimated if m["label"] not in text]
        if estimated and "Confirm field dimensions before sending." not in text:
            missing.append("Confirm field dimensions before sending.")
        checks.append(("estimates on the checklist", "every estimated measurement", "; ".join(missing) or "all",
                       not missing))

    applies, _, _ = gc_applies(draft["schedule"], package.values)
    gc = [line for line, _ in rows if line.category == "general_conditions"]
    included = [line for line in gc if line.included]
    rule = not included if applies is not True else all(
        line.evidence and line.evidence.source == "rate_table" for line in included)
    checks.append(("general conditions rule", "included only past the threshold, role × duration at rate",
                   f"threshold {'passed' if applies else 'not passed' if applies is False else 'undecided'}; "
                   f"{len(included)} of {len(gc)} GC line(s) included", rule))
    return checks, kinds


def compare_schedule(expected, result, draft):
    """Checks for schedule_impact_days, schedule_impact: stated, and general_conditions: none."""
    exact = expected["exact"]
    extension = draft["schedule"].get("extension_days") or {}
    known = extension.get("status") == "known"
    checks = []
    if "schedule_impact_days" in exact:
        got = extension.get("value") if known else extension.get("status", "missing")
        checks.append(("schedule impact days", exact["schedule_impact_days"], got,
                       known and Decimal(str(extension["value"])) == Decimal(str(exact["schedule_impact_days"]))))
    if exact.get("schedule_impact") == "stated":
        checks.append(("schedule impact stated", "known", extension.get("status", "missing"), known))
    if exact.get("general_conditions") == "none":
        included = [l.description for l in result.priced.lines if l.included and l.category == "general_conditions"]
        checks.append(("no general conditions", "none", "; ".join(included) or "none", not included))
    return checks
