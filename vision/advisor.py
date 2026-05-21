#!/usr/bin/env python3
"""
Vision Advisor — OpenAI vision post-processing for the redesign pipeline.

This script is called AFTER DeepSeek generates the HTML.
It uses GPT-4o vision to analyze the ORIGINAL site screenshot and the GENERATED HTML,
then produces structured corrections for:
  1. Image placement (moving images to correct sections)
  2. Color rhythm (fixing section background alternation)

Flow:
  DeepSeek generates → final.html
  [THIS SCRIPT] → vision_corrections.json
  fix script applies corrections to final.html
  → Playwright screenshots → QA

Usage (as sub-agent prompt):
  Read pipeline/outputs/v2/final.html
  Read pipeline/outputs/v2/vision_prompt.txt
  Read pipeline/outputs/original_ref/fullpage.png (image)
  Read pipeline/outputs/original_ref/viewport.png (image)
  Output: pipeline/outputs/v2/vision_corrections.json
"""
import json, os, sys
from urllib.parse import urlparse

BASE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
OUT = os.path.join(BASE, "pipeline", "outputs", "v2")
RAW = os.path.join(BASE, "pipeline", "outputs")

PROMPT_TEMPLATE = """You are a senior design QA agent with vision capabilities.

## GOAL
Compare the ORIGINAL website screenshot with the GENERATED redesign HTML.
Produce precise corrections for: (A) incorrect image placement, (B) broken color rhythm.

## INPUT
1. Original screenshot (fullpage.png) — the ACTUAL live website
2. Original viewport screenshot (viewport.png) — what users see above the fold
3. Generated HTML — the redesign we want to fix
4. Image mapping — where each image SHOULD go based on the original

## IMAGE PLACEMENT RULES
Look at the original screenshot carefully. For EACH image:
- Which SECTION does it appear in? (hero, team, services, news, about, etc.)
- What ROLE does it play? (background, team photo, profile, icon, thumbnail, etc.)
- Is it used ONCE or multiple times? (duplication is forbidden)

For the GENERATED HTML, check:
1. Is each image in the CORRECT section?
2. Are any images DUPLICATED across sections?
3. Are any images MISSING from expected sections?
4. Are image sizes/proportions appropriate for their role?

## COLOR RHYTHM RULES
The original page has a specific section background rhythm.
Analyze the original screenshot and identify the background color pattern.
Then check the generated HTML against it.

Common patterns for wealth management sites:
- Dark (navy) ↔ Light (cream/white) alternation
- Hero: full-bleed dark with image overlay
- Services: dark background, light text
- Team: light background with cards
- Footer: dark

Check for:
1. Does the DARK/LIGHT alternation feel right?
2. Are any sections using the WRONG background color?
3. Are there sections with WHITE bg that should be CREAM?
4. Are adjacent sections too similar in color (no visual breathing)?

## OUTPUT FORMAT
Return a JSON object with this EXACT structure:

{
  "image_corrections": [
    {
      "image_filename": "bill-bolas.jpg",
      "current_section": "hero",
      "correct_section": "team",
      "current_role": "hero_background",
      "correct_role": "team_photo",
      "action": "move_to_section|remove_duplicate|keep|resize",
      "note": "This is a team member photo used correctly in team section"
    }
  ],
  "color_rhythm_fixes": [
    {
      "section_id": "services",
      "current_bg": "cream",
      "correct_bg": "navy",
      "note": "Services section should be on dark navy background to match original rhythm"
    }
  ],
  "image_mapping_context": {IMAGE_MAPPING_CONTEXT}
}

IMPORTANT:
- Every unique image URL should appear EXACTLY ONCE in the generated HTML
- Hero background is the ONLY place where the hero image belongs
- Team photos belong ONLY in the team section
- Logo belongs in header AND footer (only exception for duplication)
- Respond ONLY with the JSON object, no markdown or commentary
"""


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def load_text(path):
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def save_json(data, name):
    path = os.path.join(OUT, name)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  Saved: {path}")
    return path


def build_prompt():
    """Build the vision prompt with all context embedded."""
    # Load image mapping if exists
    mapping_path = os.path.join(OUT, "image_mapping.json")
    image_context = "(no mapping available)"
    if os.path.exists(mapping_path):
        mapping = load_json(mapping_path)
        image_context = mapping.get('section_context', image_context)
    
    # Check for original screenshots
    screenshots_info = []
    for name in ['fullpage.png', 'viewport.png']:
        path = os.path.join(RAW, "original_ref", name)
        if os.path.exists(path):
            size = os.path.getsize(path)
            screenshots_info.append(f"  - {name} ({size//1024}KB)")
    
    screenshots_block = '\n'.join(screenshots_info) if screenshots_info else "  (not found)"
    
    prompt = PROMPT_TEMPLATE.replace(
        '{IMAGE_MAPPING_CONTEXT}',
        image_context
    )
    
    return prompt


def build_prompt_file():
    """Save the vision prompt for sub-agent use."""
    prompt = build_prompt()
    path = save_json({"prompt": prompt}, "vision_prompt.json")
    
    # Also save a text version for easy reading
    text_path = os.path.join(OUT, "vision_prompt.txt")
    with open(text_path, 'w', encoding='utf-8') as f:
        f.write(prompt)
    print(f"  Saved: {text_path}")
    
    return prompt


def main():
    print("Vision Advisor — building prompt for GPT-4o vision analysis")
    print(f"  Screenshots expected: outputs/original_ref/fullpage.png, viewport.png")
    print(f"  Image mapping: outputs/v2/image_mapping.json")
    print(f"  Generated HTML: outputs/v2/final.html")
    
    prompt = build_prompt_file()
    
    print(f"\n  Prompt built ({len(prompt)} chars)")
    print(f"\nInstructions for sub-agent:")
    print(f"  1. Read pipeline/outputs/v2/vision_prompt.json")
    print(f"  2. View pipeline/outputs/original_ref/fullpage.png")
    print(f"  3. View pipeline/outputs/original_ref/viewport.png")  
    print(f"  4. Read pipeline/outputs/v2/final.html")
    print(f"  5. Write analysis to pipeline/outputs/v2/vision_corrections.json")
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

