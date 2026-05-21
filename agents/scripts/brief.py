#!/usr/bin/env python3
"""
Agent 1: Design Brief — analyzes a parsed site and produces a structured creative brief.
Input:  pipeline/outputs/parsed_site.json  (from parse_site.py)
Output: pipeline/outputs/v2/brief.json
"""
import json, sys, os

# This agent runs as a spawned sub-agent with deepseek
# It receives the parsed site data and outputs a brief

def generate_brief(site_data):
    # This would be the prompt sent to DeepSeek
    # For now, we structure the data that will be sent
    return {
        "site_type": "wealth_management",
        "brand_personality": "trustworthy, premium, established",
        "target_audience": "HNWI, family offices, professionals",
        "design_direction": {
            "vibe": "luxury minimal",
            "layout": "vertical scroll, full-bleed hero",
            "typography_style": "serif heading + clean sans body",
            "color_mood": "dark navy + warm gold accent",
            "animations": "subtle scroll reveals, staggered entries",
            "key_sections": [
                "hero", "about", "services", "differentiator",
                "intelligence", "locations", "contact"
            ]
        },
        "content_focus": [
            "trust signals (stats, awards, longevity)",
            "personal relationships (team, bios)",
            "service depth (estate, sports, charitable)"
        ],
        "competitor_avoid": "generic stock photos, template feel",
        "raw_site_data": site_data
    }

if __name__ == "__main__":
    path = sys.argv[1] if len(sys.argv) > 1 else "pipeline/outputs/parsed_site.json"
    with open(path, 'r', encoding='utf-8') as f:
        site_data = json.load(f)
    
    brief = generate_brief(site_data)
    
    out = "pipeline/outputs/v2/brief.json"
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(brief, f, indent=2, ensure_ascii=False)
    print(f"Brief saved to {out}")
