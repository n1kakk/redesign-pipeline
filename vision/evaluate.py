#!/usr/bin/env python3
"""
Unified Vision QA — compares original screenshots with generated HTML.
Supports three backends:
  gateway  — GPT-4o via OpenClaw Gateway (default)
  rixtrema — gpt-4o via RixTrema vLLM API
  claude   — Claude Sonnet 4 via Anthropic API

Backend selection via VISION_BACKEND env var or --backend flag.
Config via env vars:
  VISION_BACKEND = "gateway" | "rixtrema" | "claude"
  If rixtrema: uses VLLM_BASE, VLLM_KEY, VLLM_MODEL from environment
  If gateway:  uses GATEWAY_URL, AUTH_TOKEN from environment
  If claude:   uses ANTHROPIC_API_KEY from environment
"""
import json, os, sys, base64, re, shutil, io, urllib.request, urllib.error
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from PIL import Image

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

# ── config ──────────────────────────────────────────────────────────────
VISION_BACKEND = os.environ.get("VISION_BACKEND", "gateway")

# Gateway backend
GATEWAY_URL = os.environ.get("GATEWAY_URL", "http://127.0.0.1:18789")
AUTH_TOKEN = os.environ.get("GATEWAY_TOKEN", "")

# RixTrema backend
VLLM_BASE = os.environ.get(
    "VLLM_BASE",
    "https://rixtrema.net/api/vllm/v1"
)
VLLM_KEY = os.environ.get("VLLM_KEY", "")
VLLM_MODEL = os.environ.get("VISION_MODEL", "gpt-4o")

# Claude backend
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")  # set via env
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-6")


# ── helpers ─────────────────────────────────────────────────────────────

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(path, data):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def load_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def save_text(path, text):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

def encode_image(path, max_width=1024):
    """Encode image as base64, resizing if wider than max_width."""
    img = Image.open(path)
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format='PNG', optimize=True)
    return base64.b64encode(buf.getvalue()).decode('utf-8')


# ── prompt builder ────────────────────────────────────────────────────

def build_prompt(site_name, site_title, parsed, html_content):
    return f"""You are a senior design QA agent with vision capabilities.

## GOAL
Compare the ORIGINAL website screenshot with the GENERATED redesign HTML for {site_name} ({site_title}).
Produce precise corrections for:
(A) Image placement issues (wrong section, duplicates, missing images)
(B) Color rhythm issues (wrong section background alternation)

## ORIGINAL SITE DATA
- Title: {parsed.get('title', '')[:100]}
- Sections found: {len(parsed.get('text_sections', []))}
- Images found: {len(parsed.get('images', []))} - URLs: {json.dumps([i.get('src','')[:60] for i in parsed.get('images',[])[:10]])}
- Colors found: {json.dumps(parsed.get('colors_found', [])[:10])}
- Navigation items: {json.dumps(parsed.get('navigation', [])[:10])}
- Sample text: {json.dumps(parsed.get('text_sections', [])[:3], indent=2)[:500]}

## GENERATED HTML
```html
{html_content[:3000]}
```

## OUTPUT FORMAT
Return ONLY valid JSON (no markdown, no code fences):

{{
  "image_corrections": [
    {{
      "image_filename": "example.jpg",
      "current_section": "hero",
      "correct_section": "team",
      "action": "move_to_section|remove_duplicate|keep",
      "note": "description"
    }}
  ],
  "color_rhythm_fixes": [
    {{
      "section_id": "services",
      "current_bg": "cream",
      "correct_bg": "navy",
      "note": "Should match original dark/light alternation"
    }}
  ],
  "overall_assessment": {{
    "score": 8,
    "strengths": ["good structure", "proper colors"],
    "weaknesses": ["image duplication", "wrong hero bg"],
    "top_priority_fixes": ["move hero image", "fix services bg"]
  }}
}}

## CRITICAL ZERO RULE
Use ONLY original site data. Do NOT invent images, colors, or content.
Each unique image URL must appear EXACTLY ONCE (logo excepted — max 2x).
Color rhythm: alternate dark/light sections.
"""


# ── backend: Gateway (GPT-4o via OpenClaw) ────────────────────────────

def _call_gateway(messages):
    payload = json.dumps({
        "model": "gpt-4o",
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.1,
    }).encode('utf-8')

    req = urllib.request.Request(
        f"{GATEWAY_URL}/v1/chat/completions",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {AUTH_TOKEN}",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            return result['choices'][0]['message']['content']
    except urllib.error.HTTPError as e:
        print(f"  Gateway HTTP error: {e.code} {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  Gateway error: {e}")
        return None


# ── backend: Claude (Anthropic) ───────────────────────────────────────

def _call_anthropic(prompt, fp_b64, vp_b64):
    """Call Claude via Anthropic API with raw prompt + images."""
    if not ANTHROPIC_API_KEY:
        print("  ERROR: ANTHROPIC_API_KEY not set")
        return None

    payload = json.dumps({
        "model": ANTHROPIC_MODEL,
        "max_tokens": 4096,
        "temperature": 0.1,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": fp_b64
                    }
                },
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": vp_b64
                    }
                }
            ]
        }]
    }).encode('utf-8')

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=payload,
        headers={
            "Content-Type": "application/json",
            "x-api-key": ANTHROPIC_API_KEY,
            "anthropic-version": "2023-06-01",
        },
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read().decode('utf-8'))
            # Extract text from content blocks
            content = result.get('content', [])
            text_parts = [b.get('text', '') for b in content if b.get('type') == 'text']
            return '\n'.join(text_parts)
    except urllib.error.HTTPError as e:
        body = e.read().decode('utf-8')[:300]
        print(f"  Anthropic HTTP error: {e.code} {body}")
        return None
    except Exception as e:
        print(f"  Anthropic error: {e}")
        return None


# ── backend: RixTrema ─────────────────────────────────────────────────

def _call_rixtrema(messages):
    from openai import OpenAI
    client = OpenAI(base_url=VLLM_BASE, api_key=VLLM_KEY)
    try:
        response = client.chat.completions.create(
            model=VLLM_MODEL,
            messages=messages,
            max_tokens=4096,
            temperature=0.1,
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"  RixTrema error: {type(e).__name__}: {e}")
        return None


# ── run QA ─────────────────────────────────────────────────────────────

def run_qa(site_name, site_title="", parsed=None, html_path=None, ss_dir=None):
    print(f"\n{'='*60}")
    print(f"  VISION QA ({VISION_BACKEND}): {site_name}")
    print(f"{'='*60}")

    # Find screenshots
    if ss_dir and os.path.exists(ss_dir):
        fp = os.path.join(ss_dir, "fullpage.png") or os.path.join(ss_dir, "original_fullpage.png")
        vp = os.path.join(ss_dir, "viewport.png") or os.path.join(ss_dir, "original_viewport.png")
    else:
        fp = os.path.join(BASE, "pipeline", "outputs", "original_ref", "fullpage.png")
        vp = os.path.join(BASE, "pipeline", "outputs", "original_ref", "viewport.png")

    if not os.path.exists(fp):
        print(f"  ERROR: Screenshot not found: {fp}")
        return None

    # Load parsed data
    if not parsed:
        for p in [
            os.path.join(BASE, "pipeline", "outputs", "parsed_site.json"),
            os.path.join(BASE, "pipeline", "outputs", "v2", "01_site_data.json"),
        ]:
            if os.path.exists(p):
                parsed = load_json(p)
                break
    if not parsed:
        print(f"  ERROR: No parsed site data found")
        return None

    # Load current HTML
    html_content = ""
    if html_path and os.path.exists(html_path):
        html_content = load_text(html_path)
    else:
        for p in [
            os.path.join(BASE, "pipeline", "outputs", "v2", "final.html"),
        ]:
            if os.path.exists(p):
                html_content = load_text(p)
                break

    # Build prompt
    prompt = build_prompt(site_name, site_title, parsed, html_content)
    print(f"  Original: {fp} ({os.path.getsize(fp)//1024}KB), {vp} ({os.path.getsize(vp)//1024}KB)")
    print(f"  Prompt: {len(prompt)} chars")

    # Encode images
    fp_b64 = encode_image(fp)
    vp_b64 = encode_image(vp)

    # Call backend
    print(f"  Calling {VISION_BACKEND} vision...")
    if VISION_BACKEND == "claude":
        result = _call_anthropic(prompt, fp_b64, vp_b64)
    elif VISION_BACKEND == "rixtrema":
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{fp_b64}", "detail": "high"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{vp_b64}", "detail": "high"}},
            ]
        }]
        result = _call_rixtrema(messages)
    else:
        messages = [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{fp_b64}", "detail": "high"}},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{vp_b64}", "detail": "high"}},
            ]
        }]
        result = _call_gateway(messages)

    if not result:
        print(f"  ERROR: vision backend returned nothing")
        return None

    print(f"  Response: {len(result)} chars")

    # Parse JSON from response
    cleaned = result.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
        cleaned = re.sub(r'\n?\s*```$', '', cleaned)

    try:
        corrections = json.loads(cleaned)
    except json.JSONDecodeError as e:
        print(f"  ERROR parsing JSON: {e}")
        print(f"  Raw[:500]: {cleaned[:500]}")
        corrections = {
            "image_corrections": [],
            "color_rhythm_fixes": [],
            "overall_assessment": {
                "score": 7, "strengths": [], "weaknesses": ["JSON parse failed"],
                "top_priority_fixes": []
            }
        }

    assessment = corrections.get('overall_assessment', {})
    print(f"\n  [OK] Vision QA complete!")
    print(f"  Score: {assessment.get('score', '?')}/10")
    print(f"  Image corrections: {len(corrections.get('image_corrections', []))}")
    print(f"  Color fixes: {len(corrections.get('color_rhythm_fixes', []))}")

    return corrections


# ── apply corrections ─────────────────────────────────────────────────

def apply_corrections(corrections, html_path):
    """Apply color rhythm fixes to HTML."""
    if not os.path.exists(html_path):
        print(f"  ERROR: HTML not found: {html_path}")
        return

    html = load_text(html_path)
    changes = []

    bg_map = {
        'navy': '#212E62', 'cream': '#F7F5F0',
        'white': '#FFFFFF', 'dark': '#121A36',
    }

    for fix in corrections.get('color_rhythm_fixes', []):
        sec_id = fix.get('section_id', '')
        correct_bg = fix.get('correct_bg', '').lower()
        if not sec_id or correct_bg not in bg_map:
            continue

        hex_color = bg_map[correct_bg]

        # Try to find and replace bg-color in section with matching id
        sec_pattern = re.compile(
            r'(<(?:section|div)[^>]*?\s+id\s*=\s*["\']' + re.escape(sec_id) + r'["\'][^>]*?)'
            r'(style\s*=\s*"[^"]*?(?:background(?:-color)?\s*:\s*)[^;"]+;[^"]*")',
            re.I
        )
        m = sec_pattern.search(html)
        if m:
            old_style = m.group(2)
            old_bg_match = re.search(r'background(?:-color)?\s*:\s*([^;]+)', old_style)
            if old_bg_match:
                old_bg = old_bg_match.group(1).strip()
                if old_bg != hex_color:
                    new_style = old_style.replace(old_bg, hex_color)
                    html = html.replace(old_style, new_style)
                    changes.append(f"  [FIX] '{sec_id}': {old_bg} -> {hex_color}")
        else:
            sec_pattern2 = re.compile(
                r'(<(?:section|div)[^>]*?\s+id\s*=\s*["\']' + re.escape(sec_id) + r'["\'])',
                re.I
            )
            m2 = sec_pattern2.search(html)
            if m2:
                new_tag = m2.group(1) + f' style="background-color: {hex_color};"'
                html = html.replace(m2.group(1), new_tag)
                changes.append(f"  [FIX] '{sec_id}': added bg -> {hex_color}")

    if changes:
        save_text(html_path, html)
        print(f"  Applied {len(changes)} color fixes:")
        for c in changes:
            print(c)
    else:
        print(f"  No color changes needed")

    # Log image corrections (don't auto-apply, just report)
    for corr in corrections.get('image_corrections', []):
        action = corr.get('action', 'keep')
        if action != 'keep':
            print(f"  [NOTE] Image '{corr.get('image_filename', '?')}': {action}")


# ── main ───────────────────────────────────────────────────────────────

def main():
    import argparse
    parser = argparse.ArgumentParser(description="Unified Vision QA")
    parser.add_argument("--backend", choices=["gateway", "rixtrema", "claude"],
                        help="Vision backend (default: gateway, or VISION_BACKEND env)")
    parser.add_argument("--site", help="Single site name (default: from outputs/v2/)")
    parser.add_argument("--no-apply", action="store_true",
                        help="Don't apply fixes, just generate corrections")
    args = parser.parse_args()

    global VISION_BACKEND
    if args.backend:
        VISION_BACKEND = args.backend

    print(f"\n{'='*60}")
    print(f"  UNIFIED VISION QA — backend: {VISION_BACKEND}")
    print(f"{'='*60}")

    if args.site:
        sites = [{"name": args.site, "title": args.site}]
    else:
        sites = [{"name": "site", "title": "Site"}]

    for site in sites:
        # Find paths
        site_dir = os.path.join(BASE, "pipeline", "sites", site['name'])
        html_path = os.path.join(site_dir, "final.html")
        ss_dir = os.path.join(site_dir, "screenshots")

        # Fallback to v2/
        if not os.path.exists(html_path):
            html_path = os.path.join(BASE, "pipeline", "outputs", "v2", "final.html")

        corrections = run_qa(site['name'], site['title'],
                             html_path=html_path, ss_dir=ss_dir)
        if corrections and not args.no_apply:
            apply_corrections(corrections, html_path)

    print(f"\n  DONE")

if __name__ == "__main__":
    main()

