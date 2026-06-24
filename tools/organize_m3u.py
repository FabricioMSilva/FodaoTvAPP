import argparse
import json
import pathlib
import re
import unicodedata


def sanitize_filename(value: str, max_length: int = 120) -> str:
    value = unicodedata.normalize('NFKD', value)
    value = value.encode('ascii', 'ignore').decode('ascii')
    value = re.sub(r'[<>:"/\\|?*]', '_', value)
    value = re.sub(r'\s+', ' ', value).strip()
    value = value[:max_length].rstrip(' ._')
    return value or 'unnamed'


def parse_m3u(path: pathlib.Path):
    text = path.read_text(encoding='utf-8', errors='replace')
    lines = [line.strip() for line in text.splitlines()]
    attr_pattern = re.compile(r'(?P<key>[^=\s]+)="(?P<value>.*?)"')
    channels = []
    nested_m3u = []

    for idx, line in enumerate(lines):
        if not line.startswith('#EXTINF'):
            continue
        info = line[8:].strip()
        attrs = {m.group('key'): m.group('value') for m in attr_pattern.finditer(info)}
        name = info.split(',', 1)[1].strip() if ',' in info else ''
        url = lines[idx + 1].strip() if idx + 1 < len(lines) else ''
        channels.append({
            'tvg_id': attrs.get('tvg-id', ''),
            'tvg_name': attrs.get('tvg-name', ''),
            'tvg_logo': attrs.get('tvg-logo', ''),
            'group_title': attrs.get('group-title', '').strip(),
            'name': name,
            'url': url,
        })
        if url.lower().endswith('.m3u'):
            nested_m3u.append(url)

    return channels, nested_m3u


def organize_output(channels, output_root: pathlib.Path):
    groups = {}
    for channel in channels:
        group_key = channel['group_title'] or 'Sem Grupo'
        groups.setdefault(group_key, []).append(channel)

    output_root.mkdir(parents=True, exist_ok=True)
    summary = {
        'total_channels': len(channels),
        'total_groups': len(groups),
        'groups': {group: len(items) for group, items in sorted(groups.items())},
    }

    (output_root / 'groups_summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    (output_root / 'groups_summary.txt').write_text('\n'.join(f'{group}: {len(items)}' for group, items in sorted(groups.items())), encoding='utf-8')

    all_channels_path = output_root / 'all_channels.json'
    all_channels_path.write_text(json.dumps(channels, ensure_ascii=False, indent=2), encoding='utf-8')

    for group_name, items in groups.items():
        safe_group_name = sanitize_filename(group_name)
        group_dir = output_root / safe_group_name
        group_dir.mkdir(parents=True, exist_ok=True)

        lines = [f"{item['name']} | {item['url']}" for item in items]
        (group_dir / 'links.txt').write_text('\n'.join(lines), encoding='utf-8')
        (group_dir / 'channels.json').write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding='utf-8')
        (group_dir / 'channels_summary.txt').write_text(f"Group: {group_name}\nCount: {len(items)}\n", encoding='utf-8')

    return summary


def main():
    parser = argparse.ArgumentParser(description='Organize M3U channels into grouped folders.')
    parser.add_argument('source', nargs='?', default=str(pathlib.Path(__file__).resolve().parent.parent / 'player' / 'playlists' / 'canaisfilmeseseries.m3u'), help='Source M3U file path')
    parser.add_argument('output', nargs='?', default='m3u_output', help='Output folder name')
    args = parser.parse_args()

    source_path = pathlib.Path(args.source)
    if not source_path.exists():
        raise FileNotFoundError(f'Source file not found: {source_path}')

    output_root = pathlib.Path(args.output).resolve()
    channels, nested_m3u = parse_m3u(source_path)
    summary = organize_output(channels, output_root)

    print(f'Parsed {len(channels)} channels into {len(summary["groups"])} groups.')
    print(f'Output written to: {output_root}')
    if nested_m3u:
        nested_path = output_root / 'nested_m3u_urls.txt'
        nested_path.write_text('\n'.join(sorted(set(nested_m3u))), encoding='utf-8')
        print(f'Nested .m3u URLs found: {len(nested_m3u)} (listed in {nested_path})')


if __name__ == '__main__':
    main()
