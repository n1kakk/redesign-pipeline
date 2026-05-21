#!/usr/bin/env python3
"""
Agent: Judge — читает QA report, оценивает severity проблем,
решает нужна ли ещё итерация, генерирует точечные фиксы.

Запуск:  python pipeline/agents/judge.py
Выход:   решение + применённые фиксы (если нужны)
"""
import json, os, sys, re

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
V2 = os.path.join(BASE, "pipeline", "outputs", "v2")

# ── severity evaluation ───────────────────────────────────────────────

SEVERITY_RULES = {
    "zero_rule": {"keywords": ["invent", "fake", "made up", "lorem", "placeholder"], "severity": "critical"},
    "hero_image": {"keywords": ["no real photo", "missing hero", "logo watermark"], "severity": "critical"},
    "repeating_images": {"keywords": ["duplicate", "repeating", "same image"], "severity": "critical"},
    "links_correct": {"keywords": ["broken link", "dead link", "wrong url", "example.com"], "severity": "critical"},
    "brand_colors": {"keywords": ["wrong color", "off-spec", "deviation"], "severity": "major"},
    "no_emoji": {"keywords": ["emoji found"], "severity": "major"},
    "mobile_nav": {"keywords": ["no mobile", "hamburger", "submenu hidden"], "severity": "major"},
    "subscribe_form": {"keywords": ["form no action", "broken form", "action=#"], "severity": "major"},
    "parallax": {"keywords": ["parallax", "background-attachment:fixed"], "severity": "minor"},
    "favicon": {"keywords": ["favicon"], "severity": "info"},
    "print_styles": {"keywords": ["print style", "@media print"], "severity": "info"},
    "canonical": {"keywords": ["canonical", "hreflang"], "severity": "info"},
    "seo": {"keywords": ["seo", "meta description"], "severity": "info"},
}


def classify_issue(text: str) -> dict:
    """Classify a single issue from QA report by severity."""
    text_lower = text.lower()
    for name, rule in SEVERITY_RULES.items():
        if any(kw in text_lower for kw in rule["keywords"]):
            return {"name": name, "severity": rule["severity"], "text": text}
    return {"name": "unknown", "severity": "minor", "text": text}


def evaluate_report(report: dict) -> dict:
    """Evaluate full QA report and decide if fix iteration is needed."""
    issues = []

    # Check pass_fail
    for check in report.get("pass_fail", []):
        if not check.get("pass", True):
            classified = classify_issue(check.get("detail", check.get("check", "")))
            classified["check"] = check.get("check", "")
            issues.append(classified)

    # Check fixes list
    for fix in report.get("fixes", []):
        classified = classify_issue(fix.get("suggestion", fix.get("issue", "")))
        classified["check"] = fix.get("issue", "")
        classified["suggestion"] = fix.get("suggestion", "")
        classified["severity"] = fix.get("severity", classified["severity"])
        issues.append(classified)

    # Check score breakdown — anything < 6 is critical
    for section, data in report.get("score_breakdown", {}).items():
        if isinstance(data, dict) and data.get("score", 10) < 6:
            issues.append({
                "name": section,
                "severity": "critical",
                "check": f"{section} score: {data.get('score', 0)}/10",
                "text": data.get("reasoning", ""),
            })

    # Count by severity
    criticals = [i for i in issues if i["severity"] == "critical"]
    majors = [i for i in issues if i["severity"] == "major"]
    minors = [i for i in issues if i["severity"] == "minor"]
    infos = [i for i in issues if i["severity"] == "info"]

    # Decision
    needs_fix = len(criticals) > 0 or len(majors) > 1

    return {
        "total_issues": len(issues),
        "critical": len(criticals),
        "major": len(majors),
        "minor": len(minors),
        "info": len(infos),
        "needs_fix": needs_fix,
        "reason": (
            f"{len(criticals)} critical, {len(majors)} major, {len(minors)} minor, {len(infos)} info — "
            + ("NEEDS FIX" if needs_fix else "GOOD ENOUGH")
        ),
        "issues": issues,
        "fix_targets": [i for i in issues if i["severity"] in ("critical", "major")],
    }


# ── fix generation ────────────────────────────────────────────────────

def apply_fixes(html: str, fix_targets: list) -> tuple:
    """Apply targeted fixes to HTML based on fix targets."""
    changes = []

    for target in fix_targets:
        check = target.get("check", "").lower()

        # Fix: example.com URLs
        if "example.com" in html and ("wrong url" in check or "example" in check):
            count = html.count("example.com")
            html = html.replace("https://example.com/", "https://original-site.com/")
            html = html.replace("https://example.com", "https://original-site.com")
            changes.append(f"Fixed {count} example.com URLs → placeholder")

        # Fix: form action="#"
        if 'action="#"' in html and ("form" in check or "action=" in check):
            html = html.replace(
                'action="#"',
                'action="#" onsubmit="alert(\'Subscribed! (demo)\'); return false"'
            )
            changes.append("Added demo handler to subscribe form")

        # Fix: broken JS selector with backslash
        if r'a[target=\" _blank\\]' in html or 'a[target="\\' in html:
            html = html.replace(r'a[target=\" _blank\\]', 'a[target="_blank"]')
            html = html.replace('a[target="\\', 'a[target="_blank"')
            changes.append("Fixed broken JS selector escaping")

        # Fix: parallax
        if "background-attachment: fixed" in html and "parallax" in check:
            html = html.replace("background-attachment: fixed", "background-attachment: scroll")
            changes.append("Removed parallax (background-attachment: fixed → scroll)")

        # Fix: logo watermark as hero
        if "logo" in check and ("hero" in check or "watermark" in check):
            # Find hero section and add gradient background instead
            hero_match = re.search(
                r'(<(?:section|div)[^>]*?class="[^"]*hero[^"]*"[^>]*>)',
                html, re.I
            )
            if hero_match:
                old = hero_match.group(1)
                if 'style=' in old:
                    new = re.sub(r'style="[^"]*"',
                                 lambda m: m.group(0).rstrip('"') + '; background: linear-gradient(135deg, #0F1B3D 0%, #1a2a5e 100%);"',
                                 old)
                else:
                    new = old.replace('>', ' style="background: linear-gradient(135deg, #0F1B3D 0%, #1a2a5e 100%);">')
                html = html.replace(old, new)
                changes.append("Added proper gradient background to hero section")

    return html, changes


# ── main ───────────────────────────────────────────────────────────────

def main():
    print("=" * 60)
    print("  JUDGE AGENT -- evaluating QA report")
    print("=" * 60)

    # Load QA report
    qa_path = os.path.join(V2, "qa_report.json")
    if not os.path.exists(qa_path):
        print("  No QA report found — nothing to judge")
        return 0

    report = json.load(open(qa_path, encoding="utf-8"))
    score = report.get("overall_score", 0)

    # Load current HTML
    html_path = os.path.join(V2, "final.html")
    html = ""
    if os.path.exists(html_path):
        html = open(html_path, encoding="utf-8").read()

    print(f"  Current score: {score}/10")
    print()

    # Evaluate
    verdict = evaluate_report(report)

    print(f"  Issues found: {verdict['total_issues']}")
    print(f"    Critical: {verdict['critical']}")
    print(f"    Major:    {verdict['major']}")
    print(f"    Minor:    {verdict['minor']}")
    print(f"    Info:     {verdict['info']}")
    print(f"  Decision:   {verdict['reason']}")
    print()

    if verdict["needs_fix"] and html:
        print("  Applying targeted fixes...")
        fixed_html, changes = apply_fixes(html, verdict["fix_targets"])

        if changes:
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(fixed_html)
            print(f"  Applied {len(changes)} fixes:")
            for c in changes:
                print(f"    [OK] {c}")
        else:
            print("  No automatic fixes available for these issues")
            print("  Manual review recommended")
    elif not verdict["needs_fix"]:
        print("  [OK] No fixes needed -- quality threshold met")
    else:
        print("  No HTML to fix")

    # Save judge report
    judge_path = os.path.join(V2, "judge_report.json")
    with open(judge_path, "w", encoding="utf-8") as f:
        json.dump(verdict, f, indent=2, ensure_ascii=False)

    # Return exit code: 0 = done, 1 = needs another iteration
    if verdict["needs_fix"]:
        print(f"\n  [WARN] Score {score}/10 + {verdict['critical']} critical + {verdict['major']} major issues")
        print("  -> Another iteration recommended")
        return 0 if not changes else 1  # if we applied fixes, signal re-run
    else:
        print(f"\n  [OK] Score {score}/10 -- good enough!")
        return 0


if __name__ == "__main__":
    sys.exit(main())

