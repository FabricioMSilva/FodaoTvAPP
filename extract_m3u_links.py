#!/usr/bin/env python3
"""Extrai URLs válidas de stream de um arquivo M3U/M3U8 e gera JSON classificado."""

import argparse
import csv
import json
import re
import sys
from pathlib import Path

EXTINF_ATTRS_RE = re.compile(r'(?P<key>[^=\s,]+)="(?P<value>[^"]*)"')
URL_RE = re.compile(r'^(https?://|rtmp://|udp://|rtsp://|mms://)', re.IGNORECASE)


def is_valid_url(url):
    url = url.strip()
    return bool(URL_RE.match(url)) or url.lower().endswith('.m3u8')


def find_default_source():
    base_dir = Path(__file__).resolve().parent
    candidate_paths = [
        base_dir / 'player' / 'playlists' / 'canaisfilmeseseries.m3u',
        base_dir / 'player' / 'playlists' / 'capas.m3u8',
    ]
    for candidate in candidate_paths:
        if candidate.exists():
            return candidate

    for ext in ('*.m3u', '*.m3u8'):
        matches = sorted((base_dir / 'player' / 'playlists').glob(ext))
        if matches:
            return matches[0]

    raise FileNotFoundError('Nenhum arquivo M3U/M3U8 encontrado em player/playlists')


def parse_m3u(source_path):
    if not source_path:
        source_path = find_default_source()

    source_path = Path(source_path)
    if not source_path.exists() and not source_path.is_absolute():
        source_path = Path(__file__).resolve().parent / source_path

    if not source_path.exists():
        raise FileNotFoundError(f'Arquivo não encontrado: {source_path}')

    lines = [line.rstrip() for line in source_path.read_text(encoding='utf-8', errors='replace').splitlines()]
    entries = []
    i = 0

    while i < len(lines):
        line = lines[i].strip()
        if line.startswith('#EXTINF'):
            raw = line
            content = line[8:].strip()
            attrs_part = content
            name = ''
            if ',' in content:
                attrs_part, name = content.split(',', 1)
                name = name.strip()

            attrs = {m.group('key').lower(): m.group('value') for m in EXTINF_ATTRS_RE.finditer(attrs_part)}
            url = ''
            j = i + 1
            while j < len(lines):
                next_line = lines[j].strip()
                if not next_line or next_line.startswith('#EXTBG'):
                    j += 1
                    continue
                if next_line.startswith('#'):
                    break
                url = next_line
                break

            if url and is_valid_url(url):
                entries.append({
                    'name': name,
                    'url': url,
                    'group': attrs.get('group-title', ''),
                    'logo': attrs.get('tvg-logo', ''),
                    'raw_type': attrs.get('type', ''),
                    'type': classify_entry_type(name, attrs.get('type', ''), attrs.get('group-title', ''), url),
                    'raw': raw,
                })
            i = j
        else:
            i += 1

    return entries


def classify_entry_type(name, raw_type, group, url):
    text = ' '.join([raw_type or '', group or '', name or '', url or '']).lower()
    if any(term in text for term in ['serie', 'series', 'série', 'tv show', 'episódio', 'episode', 'sxx e', 'sxxep']):
        return 'series'
    if any(term in text for term in ['filme', 'movie', 'cinema', 'flix', '/movie/', '/movies/']):
        return 'filmes'
    if any(term in text for term in ['live', 'ao vivo', 'ao-vivo', 'tv ao vivo', 'tv ao-vivo', 'ao-vivo']):
        return 'ao-vivo'
    if any(term in text for term in ['esporte', 'sports', 'futebol', 'sport']):
        return 'esportes'
    if raw_type:
        return raw_type.lower()
    if group:
        return group.lower()
    return 'unknown'


def write_text(entries, output_path):
    Path(output_path).write_text('\n'.join(entry['url'] for entry in entries), encoding='utf-8')


def write_json(entries, output_path):
    Path(output_path).write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding='utf-8')


def write_csv(entries, output_path):
    with open(output_path, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=['name', 'url', 'group', 'logo', 'raw_type', 'type'])
        writer.writeheader()
        writer.writerows(entries)


def sanitize_filename(value):
    value = str(value).strip()
    invalid_chars = r'<>:"/\\|?*'
    for ch in invalid_chars:
        value = value.replace(ch, '_')
    value = value.replace(' ', '_')
    if not value:
        return 'sem_grupo'
    return value[:200]


def group_entries(entries):
    grouped = {}
    for entry in entries:
        type_key = entry.get('type', 'unknown') or 'unknown'
        group_key = entry.get('group', '') or 'sem_grupo'
        grouped.setdefault(type_key, {}).setdefault(group_key, []).append(entry)
    return grouped


def write_grouped_entries(entries, output_dir, fmt):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    grouped = group_entries(entries)
    summary = {}

    for type_key, groups in grouped.items():
        type_dir = output_dir / sanitize_filename(type_key)
        type_dir.mkdir(parents=True, exist_ok=True)
        summary[type_key] = {}

        for group_key, group_entries_list in groups.items():
            safe_group = sanitize_filename(group_key)
            group_dir = type_dir / safe_group
            group_dir.mkdir(parents=True, exist_ok=True)
            summary[type_key][group_key] = len(group_entries_list)

            out_file = group_dir / f'playlist.{fmt}'
            if fmt == 'json':
                write_json(group_entries_list, out_file)
            elif fmt == 'csv':
                write_csv(group_entries_list, out_file)
            elif fmt == 'text':
                write_text(group_entries_list, out_file)

    write_json([
        {'type': type_key, 'group': group_key, 'count': count}
        for type_key, groups in summary.items()
        for group_key, count in groups.items()
    ], output_dir / 'summary.json')


def main():
    parser = argparse.ArgumentParser(description='Extrai links de um arquivo M3U/M3U8.')
    parser.add_argument('source', nargs='?', default=None, help='Caminho do arquivo M3U ou M3U8')
    parser.add_argument('-o', '--output', help='Caminho do arquivo de saída. Se omitido, imprime no stdout.')
    parser.add_argument('--output-dir', help='Diretório base para salvar arquivos organizados por type/group.')
    parser.add_argument('-f', '--format', choices=['text', 'json', 'csv'], default='json', help='Formato de saída')
    parser.add_argument('--unique', action='store_true', help='Remover URLs duplicadas')
    parser.add_argument('--only', choices=['tv', 'filmes', 'series', 'esportes', 'all'], default='all', help='Filtrar por tipo com base na categoria ou nome')
    args = parser.parse_args()

    entries = parse_m3u(args.source)

    if args.only != 'all':
        filter_map = {
            'tv': ['ao-vivo', 'live', 'tv'],
            'filmes': ['filmes', 'filme', 'movie', 'cinema', 'flix'],
            'series': ['series', 'serie', 'série', 'tv show', 'episode', 'episódio'],
            'esportes': ['esportes', 'esporte', 'sports', 'futebol', 'sport'],
        }
        terms = filter_map[args.only]
        entries = [entry for entry in entries if any(term in entry['type'] for term in terms)]

    if args.unique:
        seen = set()
        unique_entries = []
        for entry in entries:
            if entry['url'] not in seen:
                seen.add(entry['url'])
                unique_entries.append(entry)
        entries = unique_entries

    if args.output_dir:
        write_grouped_entries(entries, args.output_dir, args.format)
        print(f'Saída organizada em: {args.output_dir}')
        return

    if args.output:
        output_path = Path(args.output)
        if args.format == 'text':
            write_text(entries, output_path)
        elif args.format == 'json':
            write_json(entries, output_path)
        elif args.format == 'csv':
            write_csv(entries, output_path)
        print(f'Saída gravada em: {output_path}')
    else:
        if args.format == 'text':
            print('\n'.join(entry['url'] for entry in entries))
        elif args.format == 'json':
            print(json.dumps(entries, ensure_ascii=False, indent=2))
        elif args.format == 'csv':
            writer = csv.DictWriter(sys.stdout, fieldnames=['name', 'url', 'group', 'logo', 'raw_type', 'type'])
            writer.writeheader()
            writer.writerows(entries)


if __name__ == '__main__':
    main()
