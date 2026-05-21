#!/usr/bin/env python3
"""Parse site HTML — extract structure, content, images WITH section context."""
import re, json, sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from html.parser import HTMLParser

# Section keywords to detect from id/class
SECTION_KEYWORDS = ['hero', 'about', 'services', 'team', 'contact', 'footer', 'header',
                    'nav', 'video', 'testimonials', 'gallery', 'features', 'pricing',
                    'faq', 'news', 'blog', 'cta', 'banner', 'slideshow', 'carousel',
                    'portfolio', 'products', 'reviews', 'stats', 'mission',
                    'differentiator', 'insights', 'locations', 'subscribe']

def detect_section(tag, attrs):
    """Detect section name from tag and attributes."""
    d = dict(attrs)
    # Direct section tag
    if tag in ('section', 'header', 'footer'):
        # Check id
        sid = d.get('id', '').lower()
        for kw in SECTION_KEYWORDS:
            if kw in sid:
                return kw
        # Check class
        cls = d.get('class', '').lower()
        for kw in SECTION_KEYWORDS:
            if kw in cls:
                return kw
        # Use tag name as fallback
        if tag == 'header': return 'header'
        if tag == 'footer': return 'footer'
        if tag == 'section': return 'section'  # generic
    # Check div with section-like id/class
    if tag == 'div':
        sid = d.get('id', '').lower()
        for kw in SECTION_KEYWORDS:
            if kw in sid:
                return kw
        cls = d.get('class', '').lower()
        for kw in SECTION_KEYWORDS:
            if kw in cls:
                return kw
    return None

class SiteParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = ''
        self.in_title = False
        self.texts = []
        self.links = []
        self.images = []  # each: {type, src, alt, section}
        self.css_urls = []
        self.meta_tags = {}
        self.skip_tags = {'script', 'style', 'noscript'}
        self.in_skip = 0
        self.current_text = ''
        self.section_stack = ['page']  # track current section context

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if tag == 'title':
            self.in_title = True
        if tag in self.skip_tags:
            self.in_skip += 1

        # Detect section
        sec = detect_section(tag, attrs)
        if sec:
            self.section_stack.append(sec)

        current_section = self.section_stack[-1] if self.section_stack else 'unknown'

        if tag == 'a' and 'href' in d:
            self.links.append({'text': '', 'href': d['href'], 'rel': d.get('rel', '')})
        if tag == 'img' and 'src' in d:
            src = d['src']
            # Make absolute if relative
            if src.startswith('/') and 'wp-content' in src:
                src = 'https://rpsplanadvisor.wpenginepowered.com' + src
            self.images.append({'type': 'image', 'src': src, 'alt': d.get('alt', ''), 'section': current_section})
        if tag == 'link' and d.get('rel') in ('stylesheet', 'preload'):
            if 'href' in d:
                self.css_urls.append(d['href'])
        if tag == 'meta' and d.get('name'):
            self.meta_tags[d['name']] = d.get('content', '')
        if tag == 'meta' and d.get('property', '').startswith('og:'):
            self.meta_tags[d['property']] = d.get('content', '')
        if tag in ('video',):
            src = d.get('src', '') or d.get('data-src', '')
            poster = d.get('poster', '')
            if poster:
                self.images.append({'type': 'video-poster', 'src': poster, 'alt': '', 'section': current_section})
            if src:
                self.images.append({'type': 'video/src', 'src': src, 'alt': '', 'section': current_section})
            # Also add the video element itself with type video
            self.images.append({'type': 'video', 'src': src or 'inline', 'alt': d.get('alt', ''), 'section': current_section})
        if tag in ('iframe',):
            src = d.get('src', '') or d.get('data-src', '')
            if src:
                self.images.append({'type': 'embed', 'src': src, 'alt': d.get('title', ''), 'section': current_section})
        if tag in ('source',):
            if 'src' in d:
                self.images.append({'type': 'source', 'src': d['src'], 'alt': '', 'section': current_section})
        # Extract background images from inline style
        style_val = d.get('style', '')
        if style_val and 'background' in style_val.lower():
            bg_urls = re.findall(
                r'background(?:-image)?\s*:\s*url\([\"\']?([^\"\'\)]+)[\"\']?\)',
                style_val, re.IGNORECASE
            )
            for url in bg_urls:
                url = url.strip().rstrip(')')
                if not any(img['src'] == url for img in self.images):
                    self.images.append({'type': 'bg-image', 'src': url, 'alt': '', 'section': current_section})

    def handle_endtag(self, tag):
        if tag == 'title':
            self.in_title = False
        if tag in self.skip_tags:
            self.in_skip -= 1
        # Pop section stack if we pushed
        if detect_section(tag, [('id', ''), ('class', '')]) and len(self.section_stack) > 1:
            self.section_stack.pop()
        # Also pop for explicit section/header/footer
        if tag in ('section', 'header', 'footer') and len(self.section_stack) > 1:
            self.section_stack.pop()
        if self.current_text.strip() and self.in_skip == 0:
            self.texts.append(self.current_text.strip())
        self.current_text = ''

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        if self.in_skip == 0:
            self.current_text += data

    def extract_css_backgrounds(self, raw_html):
        """Find background-image URLs inside <style> blocks."""
        existing_srcs = {img['src'] for img in self.images}
        style_blocks = re.findall(r'<style[^>]*>([\s\S]*?)</style>', raw_html, re.IGNORECASE)
        for block in style_blocks:
            urls = re.findall(
                r'background(?:-image)?\s*:\s*url\([\"\']?([^\"\'\)]+)[\"\']?\)',
                block, re.IGNORECASE
            )
            for url in urls:
                url = url.strip().rstrip(')')
                if url not in existing_srcs:
                    self.images.append({'type': 'bg-image-css', 'src': url, 'alt': '', 'section': 'css-global'})
                    existing_srcs.add(url)

    def group_images_by_section(self):
        """Return dict of section -> [images]"""
        groups = {}
        for img in self.images:
            sec = img.get('section', 'unknown')
            if sec not in groups:
                groups[sec] = []
            groups[sec].append(img)
        return groups


def extract_colors(html):
    colors = set()
    for m in re.finditer(r'#[0-9a-fA-F]{3,8}', html):
        colors.add(m.group())
    for m in re.finditer(r'rgba?\s*\([^)]+\)', html):
        colors.add(m.group())
    return sorted(colors, key=lambda c: (len(c), c))


def extract_fonts(html):
    fonts = set()
    for m in re.finditer(r"font-family\s*:\s*['\"]?([^;'\"}]+)", html):
        fonts.add(m.group(1).strip())
    for m in re.finditer(r'family=([^&"\']+)', html):
        for name in m.group(1).split('%7C'):
            fonts.add(name.replace('+', ' '))
    return sorted(fonts)


def main():
    path = 'pipeline/outputs/raw_homepage.html'
    with open(path, 'r', encoding='utf-8') as f:
        raw_html = f.read()

    parser = SiteParser()
    parser.feed(raw_html)
    parser.extract_css_backgrounds(raw_html)

    colors = extract_colors(raw_html)
    fonts = extract_fonts(raw_html)
    nav_texts = [t.strip() for t in parser.texts if len(t.strip()) < 50 and t.strip()]

    # Group images/videos by section
    section_images = parser.group_images_by_section()

    data = {
        'title': parser.title,
        'meta_tags': parser.meta_tags,
        'text_sections': list(dict.fromkeys(parser.texts)),
        'links': parser.links,
        'images': parser.images,
        'images_by_section': section_images,  # NEW: section -> images
        'css_urls': list(set(parser.css_urls)),
        'colors_found': colors,
        'fonts_found': fonts,
        'navigation': nav_texts[:30],
        'total_html_size': len(raw_html),
    }

    out = 'pipeline/outputs/parsed_site.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f'OK Parsed: {len(raw_html)} bytes -> {len(json.dumps(data))} chars of structured data')
    print(f'   Title: {parser.title[:80]}')
    print(f'   Text sections: {len(data["text_sections"])}')
    print(f'   Links: {len(data["links"])}')
    print(f'   Images: {len(data["images"])}')
    print(f'   Sections with images: {list(section_images.keys())}')
    for sec, imgs in sorted(section_images.items()):
        types = {i['type'] for i in imgs}
        print(f'      {sec}: {len(imgs)} items ({", ".join(sorted(types))})')
    print(f'   CSS files: {len(data["css_urls"])}')
    print(f'   Colors: {len(colors)}')
    print(f'   Fonts: {len(fonts)}')
    print(f'   Nav items: {len(nav_texts)}')
    print(f'OK Saved to: {out}')


if __name__ == '__main__':
    main()

