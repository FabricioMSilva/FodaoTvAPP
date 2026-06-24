import json, re, pathlib
source = pathlib.Path(__file__).resolve().parent.parent / 'player' / 'playlists' / 'canaisfilmeseseries.m3u'
text = source.read_text(encoding='utf-8', errors='replace')
lines = [line.strip() for line in text.splitlines()]
pattern = re.compile(r'(?P<key>[^=\s]+)="(?P<value>.*?)"')
channels = []
for i, line in enumerate(lines):
    if not line.startswith('#EXTINF'):
        continue
    info = line[8:].strip()
    attrs = {m.group('key'): m.group('value') for m in pattern.finditer(info)}
    name = info.split(',', 1)[1].strip() if ',' in info else ''
    url = lines[i+1] if i+1 < len(lines) else ''
    channels.append({
        'tvg_id': attrs.get('tvg-id'),
        'tvg_name': attrs.get('tvg-name'),
        'tvg_logo': attrs.get('tvg-logo'),
        'group_title': attrs.get('group-title'),
        'name': name,
        'url': url,
    })
print(json.dumps({
    'count': len(channels),
    'groups': {g: sum(1 for c in channels if c['group_title']==g) for g in sorted({c['group_title'] for c in channels})},
    'sample': channels[:5],
}, ensure_ascii=False, indent=2))
