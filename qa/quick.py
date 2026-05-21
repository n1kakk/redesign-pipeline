#!/usr/bin/env python3
"""Quick universal QA check on generated HTML."""
import re, sys, json, os
sys.stdout.reconfigure(encoding="utf-8")

path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    "pipeline", "outputs", "v2", "final.html")
if not os.path.exists(path):
    print("NO FILE:", path)
    sys.exit(1)

t = open(path, encoding="utf-8").read()

print("File:", path)
print("Size:", len(t), "chars")
print(":root CSS vars:", ":root" in t)
print("IntersectionObserver:", "IntersectionObserver" in t)
emoji = bool(re.search(r'[\U0001F300-\U0001FFFF]', t))
print("Emoji found:", emoji)
print("Lorem ipsum:", "lorem" in t.lower())
print("Media queries:", len(re.findall(r"@media", t)))
print("<section> tags:", len(re.findall(r"<section", t, re.I)))

colors = set(re.findall(r"#[0-9a-fA-F]{6}", t))
print("Unique hex colors:", len(colors))

images = re.findall(r'<img[^>]*src="([^"]+)"', t, re.I)
print("Images:", len(images))

videos = re.findall(r'<video[^>]*src="([^"]+)"', t, re.I)
vimeo = re.findall(r'player\.vimeo\.com', t)
youtube = re.findall(r'youtube\.com/embed', t)
print("Videos:", len(videos), "Vimeo:", len(vimeo), "YouTube:", len(youtube))

links = re.findall(r'<a\s[^>]*href="([^"]+)"', t, re.I)
print("Links:", len(links))

sections = re.findall(r'<(?:section|header|footer)[^>]*>', t, re.I)
print("Sections (struct):", len(sections))

# Check for duplicate image srcs
image_srcs = [img.split("?")[0].split("/")[-1] for img in images]
has_dupes = len(image_srcs) != len(set(image_srcs))
print("Duplicate images:", has_dupes)

# Closing tags check
opens = t.count("<section")
closes = t.count("</section")
print("Section open/close:", opens, "/", closes)

