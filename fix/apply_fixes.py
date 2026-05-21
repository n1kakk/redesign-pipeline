#!/usr/bin/env python3
"""
Apply Vision Corrections — applies image placement + color rhythm fixes to final.html.

Input:  pipeline/outputs/v2/vision_corrections.json
        pipeline/outputs/v2/final.html
Output: pipeline/outputs/v2/final.html (updated)
"""
import json, os, sys, re

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(BASE, "pipeline", "outputs", "v2")

def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()

def save_text(text, path):
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)

# CSS variable name to actual hex
BG_MAP = {
    'navy': 'var(--color-primary)',
    'cream': 'var(--color-cream)',
    'white': 'var(--color-white)',
    'dark': '#121A36',
}


def fix_images(html, corrections, image_mapping):
    """
    Apply image placement corrections.
    
    corrections = [
      {
        "image_filename": "bill-bolas.jpg",
        "current_section": "hero",
        "correct_section": "team",
        "action": "move_to_section|remove_duplicate|keep|resize"
      }
    ]
    """
    applied = []
    
    # Build URL-to-filename map from image_mapping
    url_to_file = {}
    for img in image_mapping.get('images', []):
        fname = img['url'].split('/')[-1].split('?')[0].lower()
        url_to_file[fname] = img['url']
    
    for corr in corrections:
        action = corr.get('action', 'keep')
        fname = corr.get('image_filename', '').lower()
        
        if action == 'keep':
            continue
        
        if action == 'remove_duplicate':
            # Find and remove duplicate background-image references
            # Find the URL in the HTML
            url = url_to_file.get(fname)
            if not url:
                continue
            
            # Find the SECOND occurrence of this URL in HTML
            # (first is correct, second+ are duplicates)
            indices = []
            idx = 0
            while True:
                idx = html.find(url, idx)
                if idx == -1:
                    break
                indices.append(idx)
                idx += 1
            
            if len(indices) >= 2:
                # Find the section containing the duplicate
                for dup_idx in indices[1:]:
                    # Replace the duplicate with a gradient fallback
                    before = html[max(0, dup_idx-300):dup_idx]
                    # Find the background-image property
                    m = re.search(r'background-(?:image\s*:\s*)?url\([\'"]?[^\'"()]*[\'"]?\)', 
                                  html[dup_idx-200:dup_idx+50], re.IGNORECASE)
                    if m:
                        start = max(0, dup_idx-200 + m.start())
                        end = dup_idx-200 + m.end()
                        html = html[:start] + replace_bg_with_gradient(html[start:end], fname) + html[end:]
                        applied.append(f"  [FIX] Removed duplicate '{fname}' — replaced with gradient")
                        continue
                    
                    # Try harder — find background-image in CSS block
                    css_idx = html.rfind('background-image:', dup_idx-500, dup_idx+50)
                    if css_idx > 0:
                        end_idx = html.find(';', css_idx)
                        if end_idx > 0:
                            start_css = html.rfind('{', css_idx-1000, css_idx)
                            if start_css < 0:
                                start_css = css_idx
                            html = html[:css_idx] + f'/* corrected: */ background-image: linear-gradient(135deg, var(--color-primary), var(--color-accent))' + html[end_idx+1:]
                            applied.append(f"  [FIX] Replaced duplicate bg '{fname}' with gradient")
                            continue
                    
                    # Last resort: just comment it out
                    html = html[:dup_idx] + f'/* DUPLICATE_REMOVED */ ' + html[dup_idx:]
                    applied.append(f"  [FIX] Commented out duplicate '{fname}'")
        
        elif action in ('move_to_section', 'resize'):
            # For now, resize fixes are applied through CSS
            if action == 'resize':
                # Try to find and fix object-fit/background-size
                url = url_to_file.get(fname)
                if url and url in html:
                    # Check if it needs background-size: cover
                    idx = html.find(url)
                    near = html[idx-500:idx+100]
                    if 'background-size' not in near and 'object-fit' not in near:
                        # Find the style tag
                        style_start = html.rfind('<style', 0, idx)
                        if style_start >= 0:
                            style_end = html.find('</style>', style_start)
                            # Add size fix near the beginning of CSS
                            insert = html.rfind('}', idx-2000, idx)
                            if insert > style_start:
                                # Find class from context
                                class_m = re.search(r'class="([^"]*)"', html[idx-800:idx])
                                if class_m:
                                    cls = class_m.group(1).split()[0]
                                    fix_css = f'\n.{cls} {{ background-size: cover; background-position: center; }}\n'
                                    html = html[:insert+1] + fix_css + html[insert+1:]
                                    applied.append(f"  [FIX] Added background-size:cover for '{fname}' (class .{cls})")
    
    return html, applied


def replace_bg_with_gradient(excerpt, fname):
    """Replace a background-image URL with a gradient."""
    # Replace url(...) with gradient
    new_excerpt = re.sub(
        r'background-image\s*:\s*url\([^)]+\)',
        'background-image: linear-gradient(135deg, var(--color-primary), var(--color-accent))',
        excerpt
    )
    if new_excerpt == excerpt:
        # Try without "image"
        new_excerpt = re.sub(
            r'background:\s*[^;]*url\([^)]+\)',
            'background: linear-gradient(135deg, var(--color-primary), var(--color-accent))',
            excerpt
        )
    if new_excerpt == excerpt:
        # Just inline comment
        new_excerpt = '/* removed */'
    return new_excerpt


def fix_color_rhythm(html, corrections):
    """
    Apply color rhythm corrections.
    
    corrections = [
      {
        "section_id": "services",
        "current_bg": "cream",
        "correct_bg": "navy",
      }
    ]
    """
    applied = []
    
    for corr in corrections:
        sec_id = corr.get('section_id', '')
        correct_bg = corr.get('correct_bg', '').lower()
        current_bg = corr.get('current_bg', '').lower()
        
        if not sec_id or not correct_bg or current_bg == correct_bg:
            continue
        
        # Map color name to CSS class
        bg_class_map = {
            'navy': 'section-navy',
            'cream': 'section-cream',
            'white': 'section-white',
            'dark': 'section-dark',
        }
        
        correct_class = bg_class_map.get(correct_bg)
        current_class = bg_class_map.get(current_bg)
        
        if not correct_class or not current_class:
            continue
        
        # Find the section by ID
        pattern = rf'(<(?:section|div)[^>]*?\s+id=["\']{re.escape(sec_id)}["\'][^>]*?)\b{re.escape(current_class)}\b'
        replacement = rf'\1{correct_class}'
        new_html, count = re.subn(pattern, replacement, html)
        if count > 0:
            html = new_html
            applied.append(f"  [FIX] Section '{sec_id}': {current_bg} → {correct_bg}")
            continue
        
        # Try finding by class
        pattern2 = rf'(<(?:section|div)[^>]*?class=["\'][^"\']*?\b{re.escape(sec_id)}\b[^>]*?)\b{re.escape(current_class)}\b'
        replacement2 = rf'\1{correct_class}'
        new_html, count = re.subn(pattern2, replacement2, html)
        if count > 0:
            html = new_html
            applied.append(f"  [FIX] Section '{sec_id}' (by class): {current_bg} → {correct_bg}")
            continue
        
        # Last resort: find section with this id and change its class
        pattern3 = rf'(id=["\']{re.escape(sec_id)}["\'][^>]*?class=["\'][^"\']*?)({re.escape(current_class)})([^"\']*?["\'])'
        replacement3 = rf'\g<1>{correct_class}\g<3>'
        new_html, count = re.subn(pattern3, replacement3, html)
        if count > 0:
            html = new_html
            applied.append(f"  [FIX] Section '{sec_id}' (loose): {current_bg} → {correct_bg}")
            continue
        
        # Try inline style background-color
        pattern4 = rf'(id=["\']{re.escape(sec_id)}["\'][^>]*?background-color:\s*)#[0-9A-Fa-f]+'
        correct_hex = {
            'navy': '#212E62',
            'cream': '#F7F5F0',
            'white': '#FFFFFF',
            'dark': '#121A36',
        }.get(correct_bg)
        if correct_hex:
            new_html, count = re.subn(pattern4, rf'\g<1>{correct_hex}', html)
            if count > 0:
                html = new_html
                applied.append(f"  [FIX] Section '{sec_id}' (inline): bg → {correct_hex}")
    
    return html, applied


def main():
    corrections_path = os.path.join(OUT, "vision_corrections.json")
    mapping_path = os.path.join(OUT, "image_mapping.json")
    html_path = os.path.join(OUT, "final.html")
    
    if not os.path.exists(corrections_path):
        print("ERROR: vision_corrections.json not found. Run vision_advisor.py first.")
        return 1
    
    if not os.path.exists(html_path):
        print("ERROR: final.html not found.")
        return 1
    
    corrections = load_json(corrections_path)
    mapping = load_json(mapping_path) if os.path.exists(mapping_path) else {}
    html = load_text(html_path)
    
    all_applied = []
    
    # 1. Fix images
    img_fixes = corrections.get('image_corrections', [])
    if img_fixes:
        print(f"Applying {len(img_fixes)} image corrections...")
        html, img_applied = fix_images(html, img_fixes, mapping)
        all_applied.extend(img_applied)
    
    # 2. Fix color rhythm
    color_fixes = corrections.get('color_rhythm_fixes', [])
    if color_fixes:
        print(f"Applying {len(color_fixes)} color rhythm fixes...")
        html, color_applied = fix_color_rhythm(html, color_fixes)
        all_applied.extend(color_applied)
    
    # Save updated HTML
    save_text(html, html_path)
    
    print(f"\nApplied {len(all_applied)} fixes:")
    for a in all_applied:
        print(a)
    
    if not all_applied:
        print("  No fixes applied (all OK or no matches found)")
    
    # Save fix report
    report = {
        'total_fixes': len(all_applied),
        'image_fixes': len(img_fixes),
        'color_fixes': len(color_fixes),
        'applied': all_applied,
    }
    report_path = os.path.join(OUT, "vision_fix_report.json")
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"  Report: {report_path}")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

