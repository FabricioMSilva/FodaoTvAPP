import pathlib
import re
from typing import Dict, List

ATTR_PATTERN = re.compile(r'(?P<key>[^=\s]+)="(?P<value>.*?)"')


def parse_m3u_file(source_path: pathlib.Path) -> List[Dict[str, str]]:
    text = source_path.read_text(encoding='utf-8', errors='replace')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    channels: List[Dict[str, str]] = []

    for i, line in enumerate(lines):
        if not line.startswith('#EXTINF'):
            continue
        info = line[8:].strip()
        attrs = {m.group('key'): m.group('value') for m in ATTR_PATTERN.finditer(info)}
        name = info.split(',', 1)[1].strip() if ',' in info else ''
        url = lines[i + 1] if i + 1 < len(lines) else ''
        channels.append({
            'tvg_id': attrs.get('tvg-id', ''),
            'tvg_name': attrs.get('tvg-name', ''),
            'tvg_logo': attrs.get('tvg-logo', ''),
            'group_title': attrs.get('group-title', '').strip(),
            'name': name,
            'url': url,
        })

    return channels


def read_m3u_text(source_path: pathlib.Path) -> str:
    return source_path.read_text(encoding='utf-8', errors='replace')


def validate_playlist_path(value: str) -> bool:
    return '{username}' in value
