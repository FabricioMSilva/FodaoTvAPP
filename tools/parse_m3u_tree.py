import json
import pathlib
import re
from collections import defaultdict
from typing import Any, Dict, List, Tuple

SOURCE = pathlib.Path(__file__).resolve().parent.parent / 'player' / 'playlists' / 'canaisfilmeseseries.m3u'
OUTPUT_DIR = pathlib.Path('m3u_tree_output')

ATTR_PATTERN = re.compile(r'(?P<key>[^=\s]+)="(?P<value>.*?)"')


def parse_m3u(path: pathlib.Path) -> List[Dict[str, str]]:
    text = path.read_text(encoding='utf-8', errors='replace')
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    channels = []
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


def branch_tree(tree: Dict[str, Any], keys: List[str], channel: Dict[str, str]) -> None:
    if not keys:
        tree.setdefault('_channels', []).append(channel)
        return
    head, *tail = keys
    branch = tree.setdefault(head, {})
    branch.setdefault('_channels', [])
    if not tail:
        branch['_channels'].append(channel)
    else:
        branch_tree(branch, tail, channel)


def add_channel_to_tree(tree: Dict[str, Any], group_title: str, channel: Dict[str, str]) -> None:
    if not group_title:
        branch_tree(tree, ['Sem Grupo'], channel)
        return
    parts = [part.strip() for part in group_title.split('|') if part.strip()]
    branch_tree(tree, parts, channel)


def tree_to_text(tree: Dict[str, Any], indent: int = 0) -> List[str]:
    lines = []
    prefix = '  ' * indent
    channels = tree.get('_channels', [])
    if channels:
        for ch in channels:
            lines.append(f"{prefix}- {ch['name']} | {ch['url']}")
    for key in sorted(k for k in tree.keys() if k != '_channels'):
        lines.append(f"{prefix}{key}")
        lines.extend(tree_to_text(tree[key], indent + 1))
    return lines


def build_group_map(channels: List[Dict[str, str]]) -> Dict[str, List[Dict[str, str]]]:
    groups: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for ch in channels:
        groups[ch['group_title']].append(ch)
    return dict(sorted(groups.items(), key=lambda item: item[0] or ''))


def save_outputs(tree: Dict[str, Any], groups: Dict[str, List[Dict[str, str]]]) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUTPUT_DIR / 'm3u_tree.json').write_text(json.dumps(tree, ensure_ascii=False, indent=2), encoding='utf-8')
    (OUTPUT_DIR / 'm3u_groups.json').write_text(json.dumps(groups, ensure_ascii=False, indent=2), encoding='utf-8')
    text_lines = tree_to_text(tree)
    (OUTPUT_DIR / 'm3u_tree.txt').write_text('\n'.join(text_lines), encoding='utf-8')
    with (OUTPUT_DIR / 'm3u_flat_links.txt').open('w', encoding='utf-8') as out:
        for group, items in groups.items():
            out.write(f'== {group or "Sem Grupo"} ==\n')
            for ch in items:
                out.write(f"{ch['name']} | {ch['url']}\n")
            out.write('\n')


def main() -> None:
    if not SOURCE.exists():
        raise FileNotFoundError(f'Fonte M3U não encontrada: {SOURCE}')

    channels = parse_m3u(SOURCE)
    tree: Dict[str, Any] = {}
    for ch in channels:
        add_channel_to_tree(tree, ch['group_title'], ch)

    groups = build_group_map(channels)
    save_outputs(tree, groups)
    print(f'Parsed {len(channels)} channels into tree output at {OUTPUT_DIR.resolve()}')
    print(f'Groups: {len(groups)}')


if __name__ == '__main__':
    main()
