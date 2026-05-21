#!/usr/bin/env python3
"""
Universal design prompt builder — reads parsed_site.json and generates
a complete HTML design prompt for ANY website.

Usage:
    python pipeline/generate/build_prompt.py                                          # uses parsed_site.json
    python pipeline/generate/build_prompt.py --url https://example.com                # parse + build
    python pipeline/generate/build_prompt.py --generate                               # build + generate via vLLM
    python pipeline/generate/build_prompt.py --url https://example.com --generate     # parse + build + generate
"""
import json, os, sys, re, subprocess
from typing import Optional

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
PARSED_PATH = os.path.join(BASE, "pipeline", "outputs", "parsed_site.json")
CONSTRAINTS_PATH = os.path.join(BASE, "pipeline", "outputs", "v2", "constraints.json")
OUT = os.path.join(BASE, "pipeline", "outputs", "v2")
os.makedirs(OUT, exist_ok=True)

sys.path.insert(0, BASE)


# ── helpers ────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save(name, data):
    path = os.path.join(OUT, name)
    with open(path, "w", encoding="utf-8") as f:
        if isinstance(data, (dict, list)):
            json.dump(data, f, indent=2, ensure_ascii=False)
        else:
            f.write(str(data))
    print(f"  Saved: {path}")
    return path


# ── image filter — remove trackers, pixels, recaptcha ──────────────────

TRACKER_PATTERNS = re.compile(
    r"(google-analytics|googletagmanager|facebook\.com/tr|pixel\.quantserve|"
    r"doubleclick|gtag|recaptcha|api2/anchor|no_robot|1x1|pixel\.gif|"
    r"beacon|bat\.bing|clarity)", re.I
)


def is_valid_image(img: dict) -> bool:
    src = img.get("src", "")
    tp = img.get("type", "")
    if tp == "video/embed" and "youtube" not in src and "vimeo" not in src:
        return False  # skip non-video embeds (trackers, recaptcha)
    if TRACKER_PATTERNS.search(src):
        return False
    if src.endswith(".svg") and "/images/patterns/" in src:
        return True  # patterns are decorative
    if not src.strip() or src.startswith("data:image/gif;base64"):
        return False
    if "pixel" in src.lower() and src.endswith(".gif"):
        return False
    return True


def classify_image(src: str) -> str:
    """Guess image role from URL/context."""
    s = src.lower()
    if "logo" in s and ".svg" in s:
        return "logo"
    if "hero" in s or "home-hero" in s or "slide" in s:
        return "hero_background"
    if "team" in s or "team-member" in s or "staff" in s or "portrait" in s:
        return "team_photo"
    if "office" in s or "building" in s or "exterior" in s:
        return "office_photo"
    if "pattern" in s:
        return "decorative_pattern"
    if "bg" in s or "background" in s or "section" in s:
        return "section_background"
    if "icon" in s:
        return "icon"
    if "thumbnail" in s or "thumb" in s:
        return "thumbnail"
    if "placeholder" in s:
        return None  # skip placeholders
    return "photo"  # generic


# ── color analysis ─────────────────────────────────────────────────────

def _rgb(hex_col):
    h = hex_col.lstrip("#")
    if len(h) != 6:
        return (0, 0, 0)
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))


def _luminance(hex_color):
    r, g, b = _rgb(hex_color)
    return (0.299 * r + 0.587 * g + 0.114 * b) / 255


def _saturation(hex_color):
    r, g, b = _rgb(hex_color)
    mx, mn = max(r, g, b), min(r, g, b)
    if mx == 0:
        return 0
    return (mx - mn) / mx


def _hue_group(hex_col):
    r, g, b = _rgb(hex_col)
    mx = max(r, g, b)
    if mx == 0:
        return "black"
    if min(r, g, b) / mx > 0.85:
        return "neutral"
    if r == mx and (b == 0 or g / b < 1.2):
        return "reddish"
    if g == mx and (r == 0 or b / r < 1.5):
        return "greenish"
    if b == mx or (r == 0 or (b / r > 1.2)) or (g == 0 or (b / g > 1.1)):
        return "bluish"
    return "other"


def _color_distance(c1, c2):
    """Simple RGB Euclidean distance."""
    r1, g1, b1 = _rgb(c1)
    r2, g2, b2 = _rgb(c2)
    return ((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2) ** 0.5


def _brand_score(col: str) -> float:
    """Score a color on how likely it is a brand primary.
    Higher = more likely. Used for direct color scoring (no clustering)."""
    r, g, b = _rgb(col)
    lum = _luminance(col)
    sat = _saturation(col)
    hue = _hue_group(col)

    score = 50.0  # base

    # Hue preference for wealth management: blue/teal > green > neutral > other > red
    if hue in ("bluish", "greenish"):
        score += 30
    elif hue == "neutral":
        score += 10
    elif hue == "reddish":
        score -= 20

    # Dark-ish = professional, but not black
    if 0.08 < lum < 0.35:
        score += 40
    elif lum <= 0.05:
        score -= 30  # near-black (rarely brand primary)
    elif lum > 0.5:
        score -= 20  # too light for primary

    # Visible saturation = has color character
    if lum < 0.35 and sat > 0.1:
        score += 30  # dark + color = typical brand primary
    elif 0.05 < sat < 0.6 and lum >= 0.35:
        score += 20  # muted professional (mid-tones)
    elif sat < 0.03:
        score -= 30  # pure gray

    # Penalize bright accents (high sat + mid-to-high lum)
    if sat > 0.7 and lum > 0.35:
        score -= 40  # bright accent, not brand primary

    # Penalize pure grays (Elementor/theme defaults)
    if sat < 0.03:
        score -= 30

    # Penalize colors that look like WordPress block editor swatches
    # (very specific patterns)
    if (r > 220 and g < 50) or (g > 200 and r < 60) or (b > 220 and r < 40 and g < 40):
        score -= 60

    return score


def analyze_colors(colors_found: list) -> dict:
    """Pick primary, accent, dark, light from parsed colors.
    Individual color scoring (no clustering)."""
    SKIP_COLORS = {"#da532c", "#ffffff", "#00d084", "#cf2e2e", "#0693e3",
                    "#9b51e0", "#f78da7", "#abb8c3", "#e07a5f",
                    "#6ec1e4", "#61ce70", "#4054b2", "#23a455",
                    "#000000", "#333333", "#666666", "#999999",
                    "#330968", "#ff6900", "#fafae1", "#fcb900",
                    "#7bdcb5", "#8ed1fc", "#420f20", "#7a00df",
                    "#34e2e4", "#31cdcf", "#7c3754", "#721d46",
                    "#2874fc", "#7c0041", "#ab1dfe", "#4721fb",
                    "#006ba1", "#007cba", "#126670", "#005a87",
                    "#004a59", "#383e70", "#67a671", "#a06880",
                    "#020381", "#010103", "#040404", "#000",
                    "#038", "#444", "#FFF", "#ddd", "#eee",
                    "#8217", "#020381", "#32373c", "#2874fc",
                    "#dad0ec", "#fdd79a", "#faaca8", "#cccccc",
                    "#eeeeee", "#f1f1f1", "#313131"}

    # Collect valid hex colors with their scores
    scored = []
    for col in colors_found:
        m = re.search(r"#[0-9a-fA-F]{6}", col)
        if m:
            hex_col = m.group().lower()
            if hex_col not in SKIP_COLORS:
                scored.append((hex_col, _brand_score(hex_col)))

    if not scored:
        return {"primary": "#1a2332", "accent": "#b1946c", "light": "#f8f6f2", "dark": "#0a0f22"}

    # Sort by brand score, then luminance for tie-breaking
    scored.sort(key=lambda x: (-x[1], _luminance(x[0])))

    # Refine primary: if the top pick is in a hue family that appears
    # MULTIPLE times among high-scorers, prefer that family.
    top_n = [c for c, sc in scored[:10] if sc >= scored[0][1] - 10]
    from collections import Counter
    hue_counts = Counter(_hue_group(c) for c in top_n)
    best_hue = hue_counts.most_common(1)[0][0] if hue_counts else "bluish"
    def tiebreak(item):
        col, sc = item
        hue = _hue_group(col)
        hue_bonus = 0 if hue == best_hue else 1
        return (hue_bonus, -sc, _luminance(col))
    scored.sort(key=tiebreak)

    result = {}

    # Dark: lowest luminance color with reasonable brand score
    sorted_by_lum = sorted(scored, key=lambda x: _luminance(x[0]))
    for col, sc in sorted_by_lum:
        lum = _luminance(col)
        sat = _saturation(col)
        if 0.03 < lum < 0.3 and sat < 0.5:
            result["dark"] = col
            break
    if "dark" not in result:
        # Fallback: any dark color
        for col, sc in sorted_by_lum:
            if 0.02 < _luminance(col) < 0.35:
                result["dark"] = col
                break
    if "dark" not in result:
        result["dark"] = scored[0][0] if scored else "#0a0f22"

    # Light: highest luminance, not white
    sorted_rev = sorted(scored, key=lambda x: -_luminance(x[0]))
    for col, sc in sorted_rev:
        lum = _luminance(col)
        if 0.72 < lum < 0.98:
            result["light"] = col
            break
    if "light" not in result:
        result["light"] = sorted_rev[0][0] if sorted_rev else "#f8f6f2"

    # Primary: highest brand score that's not dark/light
    for col, sc in scored:
        if col not in (result.get("dark", ""), result.get("light", "")):
            sat = _saturation(col)
            if sat > 0.05:
                result["primary"] = col
                break
    if "primary" not in result:
        result["primary"] = result.get("dark", "#1a2332")

    # Accent: highest saturation color, preferring warm tones
    warm = [(col, sc) for col, sc in scored
            if col not in (result.get("dark", ""), result.get("light", ""), result.get("primary", ""))
            and 0.2 < _luminance(col) < 0.8]
    if not warm:
        warm = [(col, sc) for col, sc in scored
                if col not in (result.get("dark", ""), result.get("light", ""), result.get("primary", ""))]

    def warm_score(col):
        r, g, b = _rgb(col)
        if r > g and r > b and g > 50:
            return 2  # gold/amber
        if b > r and b > g:
            return 1  # blue
        return 0

    warm.sort(key=lambda x: (_saturation(x[0]), warm_score(x[0])), reverse=True)
    result["accent"] = warm[0][0] if warm else result["primary"]

    return result


# ── content extraction ─────────────────────────────────────────────────

def extract_content_sections(text_sections: list) -> list:
    """Extract meaningful content blocks from parsed text.
    Aggressively filters nav, UI text, form labels, and footer junk."""
    NAV_WORDS = {
        "home", "overview", "services", "municipal bonds", "contact", "client login",
        "careers", "videos", "sitemap", "disclosures", "privacy policy",
        "our expertise", "our clients", "asset protection", "pricing service",
        "market yields", "glossary", "institutional trading", "brokercheck",
        "about", "our team", "meet our team", "join our team", "about us",
        "mission & vision", "how we\u2019re different", "collateral archive",
        "market commentaries",
        "skip", "skip to content", "skip to main content",
    }
    # Words that mark a line as UI/navigation rather than content
    UI_PREFIXES = {"close ", "open ", "search", "menu", "toggle", "back to", "view all"}
    FORM_WORDS = {"first name", "last name", "phone", "email", "zip", "submit", "sign up", "comments"}
    FOOTER_WORDS = {"copyright", "\u00a9", "all rights reserved", "member of",
                     "connect with us", "our offices"}
    WEEKDAYS = {"monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"}

    long_texts = []
    short_notes = []

    for t in text_sections:
        t_s = t.strip()
        if not t_s or len(t_s) < 3:
            continue
        t_lower = t_s.lower()

        # Skip pure nav items
        if t_lower in NAV_WORDS or t_lower.rstrip("+") in NAV_WORDS:
            continue
        if any(t_lower.startswith(p) for p in UI_PREFIXES):
            continue
        # Skip form labels
        if any(fw in t_lower for fw in FORM_WORDS) and len(t_s) < 50:
            continue
        # Skip legal/footer
        if any(lw in t_lower for lw in FOOTER_WORDS):
            continue
        # Skip single weekday references
        if t_lower.rstrip(",.") in WEEKDAYS:
            continue
        # Skip single icons/plus signs
        stripped = t_s.rstrip("+").strip()
        if len(stripped) <= 2 or stripped in {"+", "overview", "municipal bonds", "services"}:
            continue

        if len(t_s) >= 60:
            long_texts.append(t_s)
        elif len(t_s) >= 10 and len(t_s) < 60:
            short_notes.append(t_s)

    # Pair headings with body text using original order
    sections = []

    # Build ordered list with types, preserving original sequence
    all_annotated = []
    for t_s, kind in [(t, 'long') for t in long_texts] + [(t, 'short') for t in short_notes]:
        idx = text_sections.index(t_s) if t_s in text_sections else -1
        all_annotated.append((idx, t_s, kind))
    all_annotated.sort(key=lambda x: x[0])

    # Pair: short heading followed by long text = one section
    for idx, item, kind in all_annotated:
        if kind == 'long':
            sections.append(item[:300])
        else:
            # Only include short items if they look like real headings
            if len(item) >= 15 and not any(c in item.lower() for c in ['close ', 'open ']):
                sections.append(item)

    return sections[:20]


# ── build prompt ───────────────────────────────────────────────────────

def build_prompt(parsed: dict) -> str:
    site_name = parsed.get("title", "Wealth Management Firm").replace(" |", ",").split(",")[0].strip()
    og_desc = parsed.get("meta_tags", {}).get("og:description", "") or parsed.get("meta_tags", {}).get("description", "")

    # Colors
    colors = analyze_colors(parsed.get("colors_found", []))
    colors_text = (
        f"  - Primary: {colors.get('primary', '#212E62')}\n"
        f"  - Accent: {colors.get('accent', '#B1946C')}\n"
        f"  - Light bg: {colors.get('light', '#F7F5F0')}\n"
        f"  - Dark: {colors.get('dark', '#0A0F22')}"
    )

    # Images
    images = [i for i in parsed.get("images", []) if is_valid_image(i)]
    real_images = [i for i in images if i.get("type") == "image"]
    video_embeds = [i for i in images if i.get("type") == "video/embed"]

    # Identify logo, video sources, and bg images
    logo_img = None
    hero_imgs = []
    other_imgs = []
    seen_srcs = set()

    # Also handle type=source (mp4) and type=bg-image-css
    video_sources = []
    bg_images = []
    for img in parsed.get("images", []):
        src = img.get("src", "")
        typ = img.get("type", "")
        if typ == "source" and src.lower().endswith(".mp4"):
            if src not in seen_srcs:
                seen_srcs.add(src)
                video_sources.append(src)
        elif typ == "bg-image-css":
            if src not in seen_srcs:
                seen_srcs.add(src)
                bg_images.append(src)

    for img in real_images:
        src = img.get("src", "")
        if src in seen_srcs:
            continue
        seen_srcs.add(src)
        role = classify_image(src)
        if role == "logo":
            logo_img = src
        elif role == "hero_background":
            hero_imgs.append(src)
        elif role and role != "decorative_pattern":
            other_imgs.append(src)

    images_text = ""
    if logo_img:
        images_text += f"  - LOGO: {logo_img}\n"
    if hero_imgs:
        for hi in hero_imgs[:5]:
            images_text += f"  - HERO background: {hi}\n"
    if other_imgs:
        images_text += f"  - Other photos:\n"
        for oi in other_imgs[:10]:
            images_text += f"    * {oi}\n"

    for ve in video_embeds[:3]:
        src = ve.get("src", "")
        if "youtube" in src or "vimeo" in src:
            images_text += f"  - VIDEO embed: {src}\n"

    for vs in video_sources[:3]:
        images_text += f"  - VIDEO source: {vs}\n"

    if bg_images:
        for bg in bg_images[:3]:
            images_text += f"  - BACKGROUND image: {bg}\n"

    # Add section context for images (from images_by_section)
    images_by_sec = parsed.get("images_by_section", {})
    if images_by_sec:
        images_text += "\n  ## IMAGE PLACEMENT (section context from original site):\n"
        for sec, imgs in sorted(images_by_sec.items()):
            if sec == 'css-global':
                continue
            valid = [i for i in imgs if i.get('src', '') and 'pixel' not in i.get('src', '').lower()]
            if valid:
                images_text += f"  Section '{sec}':\n"
                for img in valid[:5]:
                    src = img['src']
                    stype = img.get('type', 'image')
                    if len(src) > 80:
                        src = src[:80] + '...'
                    images_text += f"    - [{stype}] {src}\n"

    # Navigation
    nav = parsed.get("navigation", [])
    nav_text = ""
    if nav and isinstance(nav, list):
        items = [n for n in nav if isinstance(n, str) and len(n) > 2][:12]
        if items:
            nav_text = "  - " + "\n  - ".join(items)

    # Content sections
    sections = extract_content_sections(parsed.get("text_sections", []))
    content_text = ""
    for i, sec in enumerate(sections[:15]):
        label = sec.split(".")[0].strip() if "." in sec else sec.split(" ")[0].strip()
        content_text += f"  [{i+1}] {label[:60]}:\n"
        content_text += f"       {sec[:200]}\n"

    # Constraints
    constraints_text = ""
    if os.path.exists(CONSTRAINTS_PATH):
        cons = load_json(CONSTRAINTS_PATH)
        for key, val in cons.items():
            if key == "harmony_audit" or key == "qa_criteria":
                continue
            if isinstance(val, str) and len(val) < 600:
                constraints_text += f"- {key}: {val}\n"
            elif isinstance(val, dict):
                desc = val.get("description", "")
                if desc:
                    constraints_text += f"- {key}: {desc}\n"

    # Determine site type
    site_text = site_name.lower()
    if any(w in site_text for w in ["wealth", "financial", "investment", "capital", "asset", "portfolio"]):
        firm_type = "wealth_management / financial services"
        vibe_text = "trustworthy, premium, established, professional"
        typography = "Serif for headings (elegant, traditional), clean sans-serif for body"
    elif any(w in site_text for w in ["law", "legal", "attorney", "counsel"]):
        firm_type = "legal services"
        vibe_text = "authoritative, precise, confident"
        typography = "Classic serif for headings, professional sans-serif for body"
    elif any(w in site_text for w in ["tech", "software", "digital", "consulting"]):
        firm_type = "professional services / technology"
        vibe_text = "modern, innovative, clean, bold"
        typography = "Modern sans-serif for both headings and body"
    else:
        firm_type = "professional services"
        vibe_text = "professional, trustworthy, modern"
        typography = "Clean sans-serif for both headings and body"

    prompt = f"""You are a senior web designer. Generate a complete self-contained HTML page for **{site_name}**.

## BRAND
- **Name:** {site_name}
- **Description:** {og_desc[:200] if og_desc else 'Professional services firm'}
- **Colors:**
{colors_text}
- **Typography:** {typography}
- **Vibe:** {vibe_text}
- **Site Type:** {firm_type}

## IMAGES (use these exact URLs)
{images_text or 'N/A — use gradients/patterns as backgrounds'}
CRITICAL: Every image URL must appear EXACTLY ONCE (except logo: max 2 — header + footer).

## CONTENT (from original site — use ONLY this, no placeholder text)
{content_text or 'Use professional placeholder content appropriate for this firm type.'}

## SUGGESTED SECTION STRUCTURE
1. HEADER (with logo + navigation + CTA)
2. HERO (full-viewport, background image + dark overlay + main headline)
3. ABOUT / INTRO (2-column: text + image)
4. SERVICES / OFFERINGS (grid or cards)
5. WHY US / DIFFERENTIATOR (stats, trust signals)
6. TEAM (optional — cards with photos)
7. NEWS / INSIGHTS (optional)
8. CONTACT (with form)
9. FOOTER (multi-column, links + logo + legal)

Adjust section count to fit the actual content. Do NOT add sections that weren't in the original site content.

{'' if not nav_text else f'''## NAVIGATION ITEMS (from original site)
{nav_text}
'''}
## CONSTRAINTS (critical — from 5+ real-world iterations)
{constraints_text}

## DESIGN REQUIREMENTS
- :root CSS variables for ALL design tokens (colors, fonts, spacing, transitions)
- Responsive: desktop 1440px, tablet 1024px, mobile 768px
- All sections: max-width 1280px (--content-max), consistent padding
- Scroll-triggered animations via IntersectionObserver (fade-up, stagger on grids)
- Hover effects: transform (no background-size change), border-color transitions
- NO emoji in HTML, CSS, or comments (zero tolerance)
- Mobile: hamburger nav at 768px, body scroll lock, accordion close-others
- Desktop nav: horizontal flex, dropdown on hover, no JS for submenus
- Hero: full-screen bg image, dark overlay, staggered entrance, scroll indicator
- All links: real URLs from original site (use #section-id if none available)
- 2-col grids: balanced proportions (1fr/1fr or 1.2fr/1fr max)
- Logo visible (min 60px height header, min 40px footer), contrast against bg
- Every image EXACTLY ONCE (logo excepted — 2x max)
- NO lorem ipsum — only real content from the ORIGINAL site

Output ONLY the complete HTML file — no explanations, no markdown fences."""
    return prompt


# ── main ────────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Universal design prompt builder")
    parser.add_argument("--url", help="Parse a site first, then build prompt")
    parser.add_argument("--generate", action="store_true", help="Generate HTML via vLLM after building prompt")
    parser.add_argument("--model", help="vLLM model name override")
    parser.add_argument("--parsed", default=PARSED_PATH, help="Path to parsed_site.json")
    args = parser.parse_args()

    # Step 0: Parse if URL provided
    if args.url:
        print(f"[0] Parsing: {args.url}")
        raw_path = os.path.join(BASE, "pipeline", "outputs", "raw_homepage.html")
        subprocess.run(f'curl -sL "{args.url}" -o "{raw_path}"', shell=True, cwd=BASE)
        subprocess.run("python pipeline/parse/parse_site.py", shell=True, cwd=BASE)
        print()

    # Load parsed data
    if not os.path.exists(args.parsed):
        print(f"ERROR: {args.parsed} not found. Run parse_site.py first or use --url")
        return 1

    parsed = load_json(args.parsed)

    # Build prompt
    print(f"[1] Building prompt for: {parsed.get('title', 'Unknown')[:60]}")
    prompt = build_prompt(parsed)
    prompt_path = save("harmony_prompt.txt", prompt)
    print(f"    {len(prompt)} chars ~ {len(prompt)//4} tokens")

    # Optional: detect structure info for tracking
    info = {
        "site": parsed.get("title", ""),
        "colors_found": len(parsed.get("colors_found", [])),
        "images_found": len([i for i in parsed.get("images", []) if is_valid_image(i)]),
        "sections_extracted": len(extract_content_sections(parsed.get("text_sections", []))),
    }
    save("01_site_data.json", info)

    # Generate HTML
    if args.generate:
        print(f"\n[2] Generating HTML via vLLM...")
        from pipeline.generate.vllm import generate_html
        html = generate_html(prompt, model=args.model, out_path=os.path.join(OUT, "final.html"))
        print(f"    Generated: {len(html):,} chars")

    print(f"\nDone. Prompt: {prompt_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())







