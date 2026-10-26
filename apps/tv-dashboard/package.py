#!/usr/bin/env python3
"""Build and validate an UNSIGNED widget ZIP. Never signs or contacts a TV."""

import argparse
from html.parser import HTMLParser
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parent
FILES = ('config.xml', 'index.html', 'style.css', 'settings.js', 'app.js', 'icon.svg')
NS = {'w': 'http://www.w3.org/ns/widgets', 't': 'http://tizen.org/ns/widgets'}
PRIVILEGES = {
    'http://tizen.org/privilege/application.launch',
    'http://tizen.org/privilege/tv.window',
}


class LocalReferences(HTMLParser):
    def __init__(self):
        super().__init__()
        self.references = []

    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if key in ('src', 'href'):
                self.references.append(value)


def validate(contents):
    """Validate actual archive bytes, not a source-tree substring checklist."""
    if set(contents) != set(FILES):
        raise ValueError('Archive must contain only the six allowlisted runtime files')
    config = ET.fromstring(contents['config.xml'])
    if config.tag != '{http://www.w3.org/ns/widgets}widget':
        raise ValueError('Invalid widget namespace')
    app = config.find('t:application', NS)
    if app is None or app.get('required_version') != '4.0':
        raise ValueError('Tizen 4.0 is required')
    if app.get('id') != 'TvHome0001.TVHome' or app.get('package') != 'TvHome0001':
        raise ValueError('Unexpected application identity')
    profile = config.find('t:profile', NS)
    if profile is None or profile.get('name') != 'tv-samsung':
        raise ValueError('Samsung TV profile is required')
    if {p.get('name') for p in config.findall('t:privilege', NS)} != PRIVILEGES:
        raise ValueError('Unexpected privileges')
    if config.findall('w:access', NS):
        raise ValueError('No network access entries permitted')
    for tag in ('content', 'icon'):
        element = config.find('w:' + tag, NS)
        if element is None or element.get('src') not in contents:
            raise ValueError('Missing local ' + tag)
    page = LocalReferences()
    page.feed(contents['index.html'].decode('utf-8'))
    for reference in page.references:
        if reference not in contents:
            raise ValueError('Non-local or missing HTML reference: ' + str(reference))
    css = contents['style.css'].decode('utf-8')
    if re.search(r'@import|url\s*\(', css, re.I):
        raise ValueError('Stylesheet must not fetch assets')
    icon = ET.fromstring(contents['icon.svg'])
    if icon.tag != '{http://www.w3.org/2000/svg}svg':
        raise ValueError('Invalid SVG icon')
    if not all(contents.values()):
        raise ValueError('Empty runtime file')


def validate_archive(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate ZIP entries')
        if archive.testzip() is not None:
            raise ValueError('Corrupt ZIP entry')
        validate({name: archive.read(name) for name in names})


def build(output):
    output = Path(output)
    if output.suffix != '.wgt':
        raise ValueError('Output must have .wgt extension')
    contents = {name: (ROOT / name).read_bytes() for name in FILES}
    validate(contents)
    if output.exists():
        raise FileExistsError('Refusing to overwrite existing package: ' + str(output))
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'x', zipfile.ZIP_DEFLATED) as archive:
        for name, data in contents.items():
            info = zipfile.ZipInfo(name, (2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, data)
    validate_archive(output)
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT / '.work/tv-dashboard/TVHome-unsigned.wgt')
    parser.add_argument('--validate', type=Path, help='Validate an existing unsigned archive instead')
    args = parser.parse_args()
    if args.validate:
        validate_archive(args.validate)
        print('PASS: unsigned archive structure, XML, local assets and privilege allowlist')
    else:
        print('UNSIGNED, NOT INSTALLABLE: ' + str(build(args.output)))
        print('PASS: ZIP integrity, root config.xml, TV profile, local assets, no signatures or keys')
