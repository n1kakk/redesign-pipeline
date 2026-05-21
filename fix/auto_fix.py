#!/usr/bin/env python3
"""
auto_fix.py — Universal post-generation fixer for redesign HTML.

Detects and fixes common issues that DeepSeek generates because it
doesn't see screenshots: wrong image placement, broken color rhythm,
invisible text, missing content, broken section layouts.

Usage:
  python pipeline/fix/auto_fix.py <output_dir>
  python pipeline/fix/auto_fix.py pipeline/outputs/transcend
  python pipeline/fix/auto_fix.py pipeline/outputs/v2
"""
import json, os, re, sys
from pathlib import Path

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))


# ═══════════════════════════════════════════════════════════════
#  UTILITY
# ═══════════════════════════════════════════════════════════════

def resolve(p):
    return os.path.join(BASE, p)

def load_html(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def save_html(html, path):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(html)

def load_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def log(fixes, msg):
    fixes.append(msg)
    print(f"  {msg}")

def css_rule(html, class_name):
    """Find a CSS rule for a class."""
    m = re.search(r'\.' + re.escape(class_name) + r'\s*\{[^}]*\}', html, re.DOTALL)
    return m.group(0) if m else None

def css_bg(rule):
    """Extract background value from a CSS rule."""
    if not rule: return None
    m = re.search(r'background(?:-color)?:\s*([^;}]+)', rule)
    return m.group(1).strip() if m else None

def css_color(rule):
    """Extract color value from a CSS rule."""
    if not rule: return None
    m = re.search(r'(?<!background-)color:\s*([^;}]+)', rule)
    return m.group(1).strip() if m else None

def var_name(val):
    """Extract CSS variable name from a value like var(--cream)."""
    m = re.search(r'var\(--([^)]+)\)', val or '')
    return m.group(1) if m else val.lower().replace('#', '') if val else ''

def is_dark(val):
    """Check if a color value is dark."""
    v = var_name(val).lower()
    if v in ('navy', 'primary', 'dark', '--color-primary', '#212e62', 'navy'):
        return True
    return False

def is_light(val):
    """Check if a color value is light."""
    v = var_name(val).lower()
    if v in ('cream', 'white', 'light', '--color-cream', '--color-white'):
        return True
    # Check hex
    if val and val.startswith('#'):
        try:
            r, g, b = int(val[1:3], 16), int(val[3:5], 16), int(val[5:7], 16)
            return (r + g + b) / 3 > 150
        except: pass
    return False

def next_line(html, pos):
    """Find next newline from position."""
    return html.find('\n', pos)

def insert_after(html, marker, text):
    """Insert text after the last occurrence of marker."""
    idx = html.rfind(marker)
    if idx > 0:
        idx = html.find('\n', idx)
        return html[:idx+1] + text + '\n' + html[idx+1:]
    return html


# ═══════════════════════════════════════════════════════════════
#  FIXERS — each returns (html, [messages])
# ═══════════════════════════════════════════════════════════════

def fix_color_contrast(html, fixes, context):
    """
    Ensure text is visible on its background.
    - Dark section (navy) → light text
    - Light section (cream/white) → dark text
    """
    # Known dark sections (navy bg)
    dark_sections = {'hero', 'approach-section', 'philosophy', 'differentiator',
                      'services-section', 'contact-section', 'site-footer', 'footer',
                      'subscribe-section', 'rethinking-section'}
    # Known light sections (cream bg)
    light_sections = {'team-section', 'about-section', 'video-blocks-section',
                       'news-section', 'intelligence', 'who-we-are', 'locations',
                       'sports-spotlight', 'contact'}

    # Fix 1: .section-subtitle on light sections — should be dark, not var(--text-muted)
    for sec in light_sections:
        # Get the section's bg color
        rule = css_rule(html, sec)
        bg = css_bg(rule)
        if bg and is_light(bg):
            # This section is light bg — text should NOT be white/light
            sub_rule = css_rule(html, 'section-subtitle')
            if sub_rule:
                sub_color = css_color(sub_rule)
                if sub_color and 'white' in sub_color.lower():
                    old = sub_color
                    html = html.replace(sub_color, '#555', 1)
                    log(fixes, f"[contrast] section-subtitle in .{sec}: {old} -> #555")
                    continue

            # Check inline subtitle text color for this section
            pattern = re.compile(
                r'\.' + re.escape(sec) + r'\s*\.section-subtitle\s*\{[^}]*\}',
                re.DOTALL
            )
            specific_rule = pattern.search(html)
            if not specific_rule and sub_rule:
                # No specific rule for this light section — add one
                new_rule = f'\n.{sec} .section-subtitle {{\n  color: #555;\n}}\n'
                html = insert_after(html, f'.{sec}' + '{', new_rule)
                log(fixes, f"[contrast] Added .{sec} .section-subtitle {{ color: #555 }}")
    
    # Fix 2: dark section with dark text
    for sec in dark_sections:
        rule = css_rule(html, sec)
        bg = css_bg(rule)
        if bg and is_dark(bg):
            # Check if text color is set and too dark
            for cls in ['p', 'h1', 'h2', 'h3', 'h4', 'span', 'a:not(.btn-primary)']:
                # Just check if there's a p tag color — if not, check the section's text color
                pass  # Most sections inherit properly

    return html


def fix_image_placement(html, fixes, context):
    """
    Fix image issues:
    - Remove images from buttons/labels
    - Fix duplicated images (except logo x2)
    - Check the differentiator image isn't in news
    """
    mapping = context.get('image_mapping', [])
    
    # Collect all image URLs used
    image_urls = set()
    for m in re.finditer(r'(?:url\("([^"]+\.(?:jpg|png|webp))"\)|src="([^"]+\.(?:jpg|png|webp|svg))")', html):
        url = m.group(1) or m.group(2)
        fname = url.split('/')[-1].split('?')[0]
        image_urls.add((fname, url))
    
    for fname, url in image_urls:
        # Check if image is used as button background
        for m in re.finditer(r'class="[^"]*btn(?:-primary|-outline)[^"]*"[^>]*background-image[^}]*' + re.escape(fname), html):
            # Find the background-image rule and replace it
            ctx_start = m.start()
            chunk = html[ctx_start:ctx_start+400]
            bg_m = re.search(r'background-image:\s*url\([^)]+\)', chunk)
            if bg_m:
                html = html.replace(bg_m.group(), 'background: var(--gold);')
                log(fixes, f"[images] Removed '{fname}' from button bg")
        
        # Check for image in cta-link
        for m in re.finditer(r'class="[^"]*cta-link[^"]*"[^>]*background-image[^}]*' + re.escape(fname), html):
            chunk = html[m.start():m.start()+400]
            bg_m = re.search(r'background-image:\s*url\([^)]+\)', chunk)
            if bg_m:
                html = html.replace(bg_m.group(), 'background: transparent')
                log(fixes, f"[images] Removed '{fname}' from cta-link bg")
        
        # Count appearances — logo can be 2x, everything else 1x
        is_logo = 'logo' in fname.lower()
        limit = 2 if is_logo else 1
        count = html.count(fname)
        
        if count > limit:
            # Find and comment out extra occurrences
            # Skip the first `limit` occurrences
            found = 0
            for m in re.finditer(re.escape(fname), html):
                if found >= limit:
                    pos = m.start()
                    chunk = html[max(0,pos-200):pos+len(fname)+50]
                    if not is_logo or 'btn' not in chunk:
                        # Replace this occurrence
                        old_chunk = chunk
                        new_chunk = chunk
                        # Try to replace the background-image or src
                        bg_img_m = re.search(r'(background-image:\s*)url\("[^"]*' + re.escape(fname) + r'[^"]*"\)', chunk)
                        if bg_img_m:
                            new_chunk = chunk.replace(bg_img_m.group(1) + bg_img_m.group(2) if bg_img_m.lastindex else bg_img_m.group(0),
                                                     bg_img_m.group(1) + 'linear-gradient(135deg, var(--color-primary), var(--color-accent))')
                            html = html.replace(old_chunk, new_chunk, 1)
                            log(fixes, f"[images] Duplicate '{fname}' replaced with gradient")
                            break
                        else:
                            # For <img> tags, we can't easily remove them inline
                            pass
                found += 1
                if found > limit + 2:  # safety
                    break
    
    return html


def fix_color_rhythm(html, fixes, context):
    """
    Ensure proper dark/light section alternation.
    Strips white bg sections that should be cream.
    """
    # White sections that should be cream
    white_sections_to_fix = ['sports-spotlight', 'contact', 'news-section']
    
    for sec in white_sections_to_fix:
        rule = css_rule(html, sec)
        if rule:
            bg = css_bg(rule)
            if bg and ('white' in bg.lower() or '#ffffff' in bg.lower()):
                new_rule = rule.replace(bg, 'var(--color-cream, #F7F5F0)')
                html = html.replace(rule, new_rule)
                log(fixes, f"[rhythm] .{sec}: white -> cream")
    
    return html


def fix_video_section(html, fixes, context):
    """
    Ensure video blocks are on the SAME background, not split dark/cream.
    Look for multiple video-* classes and merge them if they're split.
    """
    # Check if there's a video-section--dark (should NOT exist)
    if 'video-section--dark' in html:
        # Find the CSS rule and HTML tag
        rule = css_rule(html, 'video-section--dark')
        if rule:
            # Change to cream to match the other video section
            new_rule = rule.replace('var(--navy)', 'var(--cream)').replace('var(--color-primary)', 'var(--cream)')
            html = html.replace(rule, new_rule)
            log(fixes, "[video] Merged video-section--dark to cream")
    
    # Check if video blocks are in two separate section tags vs one
    video_sections = list(re.finditer(r'<section[^>]*video[^>]*>', html))
    if len(video_sections) > 1:
        log(fixes, f"[video] Found {len(video_sections)} separate video sections (may need manual merge)")
    
    return html


def fix_content(html, fixes, context):
    """
    Ensure all key content from parsed site is present.
    Fix DeepSeek rewriting things like 'Our Wealth Management Services' 
    instead of 'Reinvigorating portfolios.'
    """
    parsed = context.get('parsed_site', {})
    sections = parsed.get('text_sections', [])
    
    # Known rewrites DeepSeek frequently does
    rewrites = {
        'Our Wealth Management Services': 'Reinvigorating portfolios.',
        'Our Services': 'SERVICES',
        'Comprehensive solutions designed to address every aspect': 'We broaden your investing options to better serve your needs.',
        'Learn More': 'See how',  # partial — only in approach/team/services context
    }
    
    for wrong, correct in rewrites.items():
        if wrong in html:
            # Only replace if the context matches (services section for services text)
            if 'Reinvigorating' in wrong or 'Services' in wrong or 'portfolios' in correct:
                # This is a services rewrite
                if wrong in html:
                    html = html.replace(wrong, correct, 1)
                    log(fixes, f"[content] '{wrong[:40]}' -> '{correct[:40]}'")
    
    return html


def fix_section_backgrounds(html, fixes, context):
    """
    Ensure all major sections have explicit background set.
    Sections without bg look transparent/inherited which breaks rhythm.
    """
    # Sections that MUST have a bg set
    required_bgs = {
        'approach-section': 'var(--color-primary, #212E62)',
        'services-section': 'var(--color-primary, #212E62)',
        'contact-section': 'var(--color-primary, #212E62)',
        'news-section': 'var(--color-cream, #F7F5F0)',
        'team-section': 'var(--color-cream, #F7F5F0)',
        'about-section': 'var(--color-cream, #F7F5F0)',
    }
    
    for sec, default_bg in required_bgs.items():
        rule = css_rule(html, sec)
        if rule:
            bg = css_bg(rule)
            if not bg:
                # No bg in CSS rule — add it
                rule_end = rule.rfind('}')
                new_rule = rule[:rule_end] + f'\n  background: {default_bg};\n' + rule[rule_end:]
                html = html.replace(rule, new_rule)
                log(fixes, f"[bg] .{sec}: added background: {default_bg}")
        else:
            # No CSS rule at all — might not be a section in this design
            pass
    
    return html


# ═══════════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    # Determine output directory
    if len(sys.argv) > 1:
        out_dir = sys.argv[1]
    else:
        # Auto-detect from context
        out_dir = resolve("pipeline/outputs/transcend")
    
    if not os.path.isabs(out_dir):
        out_dir = resolve(out_dir)
    
    html_path = os.path.join(out_dir, "design.html")
    if not os.path.exists(html_path):
        # Try final.html (v2 convention)
        html_path = os.path.join(out_dir, "final.html")
    
    if not os.path.exists(html_path):
        print(f"ERROR: No design.html or final.html found in {out_dir}")
        return 1
    
    print(f"auto_fix.py — {out_dir}")
    print(f"  Reading: {html_path}")
    
    # Load context
    context = {
        'html': html_path,
        'parsed_site': load_json(resolve("pipeline/outputs/parsed_site.json")),
        'image_mapping': load_json(os.path.join(out_dir, "image_mapping.json")),
    }
    
    html = load_html(html_path)
    all_fixes = []
    
    # Run fixers in order
    fixers = [
        ("Section backgrounds", fix_section_backgrounds),
        ("Color rhythm", fix_color_rhythm),
        ("Video section", fix_video_section),
        ("Color contrast", fix_color_contrast),
        ("Image placement", fix_image_placement),
        ("Content", fix_content),
    ]
    
    for name, fixer in fixers:
        before = len(all_fixes)
        html = fixer(html, all_fixes, context)
        after = len(all_fixes)
        if after > before:
            print(f"  [{name}] {after - before} fix(es)")
        else:
            print(f"  [{name}] OK")
    
    # Save
    save_html(html, html_path)
    
    # Report
    report = {
        'dir': out_dir,
        'file': os.path.basename(html_path),
        'total_fixes': len(all_fixes),
        'fixes': all_fixes,
    }
    report_path = os.path.join(out_dir, "auto_fix_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    
    print(f"\n  Total: {len(all_fixes)} fixes applied")
    print(f"  Report: {report_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())




