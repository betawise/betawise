#!/usr/bin/env python3
"""Check repository documentation paths, resources, reference links and anchors.

Requires markdown-it-py. Checks first-party tracked/nonignored working-tree docs;
submodule documentation and external websites are outside this local audit.
"""
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
import re
import subprocess
import sys
import unicodedata
from urllib.parse import unquote, urlsplit

from markdown_it import MarkdownIt

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = {'.md', '.markdown', '.html', '.htm', '.rst'}
ANCHOR_DOCUMENTS = DOCUMENTS | {'.svg'}


class HTMLLinks(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = set()
        self.links = []

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        self.anchors.update(attrs[key] for key in ('id', 'name') if attrs.get(key))
        self.links.extend(attrs[key] for key in ('href', 'src', 'poster', 'xlink:href') if attrs.get(key))
        if tag == 'object' and attrs.get('data'):
            self.links.append(attrs['data'])
        if attrs.get('srcset') and not attrs['srcset'].startswith('data:'):
            self.links.extend(item.strip().split()[0] for item in attrs['srcset'].split(',') if item.strip())


def parse_document(path):
    text = path.read_text(errors='replace')
    html = HTMLLinks()
    links, anchors, reference_errors = [], set(), []
    if path.suffix.lower() not in {'.md', '.markdown'}:
        html.feed(text)
        return html.anchors, html.links, reference_errors
    environment = {}
    tokens = MarkdownIt('commonmark').parse(text, environment)
    suffixes = Counter()
    for index, token in enumerate(tokens):
        if token.type == 'heading_open':
            children = tokens[index + 1].children or []
            title = ''.join(child.content for child in children if child.type in {'text', 'code_inline', 'image'})
            base = ''.join(char for char in title.lower()
                           if char.isalnum() or char in '_- ' or unicodedata.category(char).startswith('M')).replace(' ', '-')
            slug = base
            while slug in anchors:
                suffixes[base] += 1
                slug = f'{base}-{suffixes[base]}'
            anchors.add(slug)
        if token.type in {'html_block', 'html_inline'}:
            html.feed(token.content)
        if token.type == 'inline':
            prose = re.sub(r'`+[^`]*`+', '', token.content)
            for match in re.finditer(r'(?<!!)\[([^\]\n]+)\]\[([^\]\n]*)\]', prose):
                label = ' '.join((match[2] or match[1]).split()).upper()
                if label not in environment.get('references', {}):
                    reference_errors.append(f'undefined reference {match[0]}')
        for child in token.children or []:
            if child.type == 'link_open':
                links.append(child.attrGet('href'))
            elif child.type == 'image':
                links.append(child.attrGet('src'))
            elif child.type == 'html_inline':
                html.feed(child.content)
    return anchors | html.anchors, links + html.links, reference_errors


def main():
    output = subprocess.check_output(['git', '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard'], text=True)
    names = {name for name in output.splitlines() if (ROOT / name).is_file()}
    documents = sorted(name for name in names if Path(name).suffix.lower() in DOCUMENTS)
    cache = {}
    issues, checked, images = [], 0, set()

    def parsed(path):
        if path not in cache:
            cache[path] = parse_document(path)
        return cache[path]

    for name in documents:
        source = ROOT / name
        _, links, references = parsed(source)
        issues.extend((name, message) for message in references)
        for target in links:
            if not target:
                continue
            uri = urlsplit(target)
            relative = uri.path
            if uri.scheme or uri.netloc:
                match = re.fullmatch(r'/(?:isotherm|betawise)/betawise/(?:blob|tree)/(HEAD|main|master)/(.+)', uri.path)
                if uri.netloc != 'github.com' or not match:
                    continue
                relative = '/' + match[2]
            checked += 1
            fragment = unquote(uri.fragment)
            relative = unquote(relative)
            path = ((ROOT / relative.lstrip('/')) if relative.startswith('/')
                    else source.parent / relative if relative else source).resolve()
            error = None
            if not path.is_relative_to(ROOT):
                error = 'outside the repository'
            elif not path.exists():
                error = 'missing file'
            elif path.is_dir():
                readme = next((path / child for child in ('README.md', 'readme.md', 'README.markdown', 'README.rst', 'README')
                               if (path / child).is_file()), None)
                if fragment and readme is None:
                    error = 'directory has no anchor document'
                elif readme:
                    path = readme
            elif path.relative_to(ROOT).as_posix() not in names:
                error = 'resource is only an ignored/generated output'
            if not error and fragment:
                if path.suffix.lower() in ANCHOR_DOCUMENTS:
                    if fragment.removeprefix('user-content-') not in parsed(path)[0]:
                        error = 'missing anchor'
                elif re.fullmatch(r'L\d+(?:-L?\d+)?', fragment):
                    if int(re.findall(r'\d+', fragment)[-1]) > len(path.read_text(errors='replace').splitlines()):
                        error = 'line anchor past end'
                elif path.suffix.lower() != '.pdf':
                    error = 'unsupported anchor on a non-document resource'
            if error:
                issues.append((name, f'{target}: {error}'))
            elif path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.gif', '.webp'}:
                images.add(path)
    # Image integrity is a local file check, not a visual screen-test oracle.
    from PIL import Image
    for image in sorted(images):
        try:
            with Image.open(image) as opened:
                opened.verify()
        except Exception as error:
            issues.append((str(image.relative_to(ROOT)), f'invalid image: {error}'))
    for name, message in issues:
        print(f'{name}: {message}', file=sys.stderr)
    if issues:
        print(f'FAIL: {len(issues)} broken links/resources', file=sys.stderr)
        return 1
    print(f'PASS {len(documents)} documents, {checked} internal links/resources, {len(images)} valid images; no broken paths, anchors or reference links')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
