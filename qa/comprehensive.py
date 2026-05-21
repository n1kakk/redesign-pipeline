#!/usr/bin/env python3
"""Universal QA — checks HTML against parsed_site.json. Not tied to any specific site."""
import json, os, re, sys
sys.stdout.reconfigure(encoding="utf-8")

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
HTML_PATH = os.path.join(BASE, "pipeline", "outputs", "v2", "final.html")
PARSED_PATH = os.path.join(BASE, "pipeline", "outputs", "parsed_site.json")

if not os.path.exists(HTML_PATH):
    print("ERROR: final.html not found"); sys.exit(1)

html = open(HTML_PATH, encoding="utf-8").read()
parsed = json.load(open(PARSED_PATH, encoding="utf-8")) if os.path.exists(PARSED_PATH) else {}

checks = []
warnings = []

# 1. BASIC HTML
checks.append(("DOCTYPE", "<!DOCTYPE html>" in html))
checks.append(("Viewport meta tag", 'name="viewport"' in html or "viewport" in html[:500]))
checks.append(("UTF-8 charset", 'charset="UTF-8"' in html or "charset=utf-8" in html.lower()))
checks.append((":root CSS variables", ":root" in html))
checks.append(("</html> present", "</html>" in html))
checks.append(("</body> present", "</body>" in html))

# 2. CONTENT from original
text_sections = parsed.get("text_sections", [])
title = parsed.get("title", "")

if title:
    t = title.replace(" |", "").replace(" -", "").strip()[:40]
    checks.append(("Title: '" + t + "'", t.lower() in html.lower()))

meta_desc = (parsed.get("meta_tags", {}).get("og:description", "") or
             parsed.get("meta_tags", {}).get("description", ""))
if meta_desc:
    sd = meta_desc[:30].split(".")[0]
    checks.append(("Meta description content", sd.lower() in html.lower()))

long_texts = [t.strip() for t in text_sections if len(t.strip()) >= 60]
if long_texts:
    found = 0
    for t in long_texts[:20]:
        for phrase in t.split(". ")[:2]:
            if len(phrase) > 20 and phrase in html:
                found += 1
                break
    ratio = found / max(len(long_texts[:20]), 1)
    checks.append(("Content match: " + str(found) + "/" + str(len(long_texts[:20])), ratio >= 0.6))

# 3. IMAGES
images = [i for i in parsed.get("images", []) if i.get("src", "").startswith("http")]
if images:
    found_imgs = sum(1 for i in images if i["src"] in html)
    checks.append(("Images from original: " + str(found_imgs) + "/" + str(len(images)), found_imgs >= len(images) * 0.7))
    for i in images:
        c = html.count(i["src"])
        if c > 3:
            warnings.append("Image " + i["src"].split("/")[-1][:40] + " appears " + str(c) + "x")

# 4. COLORS
colors_set = set(parsed.get("colors_found", []))
html_colors = set(re.findall(r"#[0-9a-fA-F]{6}", html))
parsed_hex = {c for c in colors_set if re.match(r"^#[0-9a-fA-F]{6}$", c)}
if parsed_hex:
    matched = len(parsed_hex & html_colors)
    checks.append(("Colors matched: " + str(matched) + "/" + str(len(parsed_hex)), matched / len(parsed_hex) >= 0.5))

# 5. LINKS
all_links = [l["href"] for l in parsed.get("links", []) if l.get("href", "").startswith("http")]
if all_links:
    found_links = sum(1 for href in all_links[:30] if href in html)
    limit = min(len(all_links), 30)
    checks.append(("Links matched: " + str(found_links) + "/" + str(limit), found_links >= limit * 0.5))

# 6. NAV
nav_items = parsed.get("navigation", []) or parsed.get("nav_items", [])
if nav_items:
    found_nav = sum(1 for item in nav_items[:15] if isinstance(item, str) and item in html)
    limit = min(len(nav_items), 15)
    checks.append(("Nav items matched: " + str(found_nav) + "/" + str(limit), found_nav >= limit * 0.4))

# 7. ANIMATIONS
checks.append(("IntersectionObserver", "IntersectionObserver" in html))
checks.append(("Scroll reveal class", ".visible" in html or "fade" in html))
checks.append(("CSS transitions (hover)", "transition" in html))

# 8. RESPONSIVE
checks.append(("Media queries (@media)", "@media" in html))
checks.append(("Flexbox or Grid layout", "grid" in html or "flex" in html))
checks.append(("Mobile nav (hamburger/menu-toggle)", "hamburger" in html.lower() or "menu-toggle" in html))

# 9. QUALITY
checks.append(("No lorem ipsum", "lorem" not in html.lower()))
checks.append(("No archive.org URLs", "archive.org" not in html))
checks.append(("No broken HTML comments", html.count("<!-") == html.count("<!--")))
checks.append(("HTML size >= 3KB", len(html) >= 3000))
checks.append(("HTML size <= 200KB", len(html) <= 200000))

# 10. SECTION BALANCE
s_opens = len(re.findall(r"<section\b", html))
s_closes = len(re.findall(r"</section>", html))
checks.append(("Sections balanced (" + str(s_opens) + "/" + str(s_closes) + ")",
              s_opens == s_closes or abs(s_opens - s_closes) <= 1))

hf_opens = len(re.findall(r"<(?:header|footer)\b", html))
hf_closes = len(re.findall(r"</(?:header|footer)>", html))
checks.append(("Header/Footer balanced (" + str(hf_opens) + "/" + str(hf_closes) + ")", hf_opens == hf_closes))

# 11. FORMS
checks.append(("Submit form exists", "form" in html and ("action=" in html or "onsubmit" in html)))

# OUTPUT — recount to be safe
oks = 0
for _, ok in checks:
    if ok:
        oks += 1
total = len(checks)
score = round(oks / total, 2) if total > 0 else 0

site_name = title[:50] if title else "unknown"
print("=== Universal QA:", site_name, "===")
print("  HTML:", len(html), "chars,", html.count(chr(10)), "lines")
print("  Parsed:", len(text_sections), "texts,", len(images), "images,", len(colors_set), "colors")
print()

for name, ok in checks:
    print(" ", "PASS" if ok else "FAIL", name)

if warnings:
    print()
    print("  Warnings (" + str(len(warnings)) + "):")
    for w in warnings:
        print("     ", w)

print()
print(" ", oks, "/", total, "passed")
print("  SCORE:", score, "(PASS)" if score >= 0.85 else "(FAIL)")

# SAVE REPORT
report = {
    "overall_score": score,
    "passed": oks,
    "total": total,
    "chars": len(html),
    "lines": html.count(chr(10)),
    "site": site_name,
    "pass_fail": [{"check": name, "pass": ok} for name, ok in checks],
    "warnings": warnings,
    "failed_checks": [name for name, ok in checks if not ok]
}
out_dir = os.path.dirname(HTML_PATH)
report_path = os.path.join(out_dir, "qa_report.json")
with open(report_path, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)
print()
print("  Report:", report_path)

