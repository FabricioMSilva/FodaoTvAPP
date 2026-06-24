"""Import the locally extracted catalogue into Supabase.

Run only after applying supabase/migrations/20260624_000001_initial_catalog.sql.
The script reads credentials from the ignored root .env file.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import requests


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CATALOG_DIR = PROJECT_ROOT / 'output_extracao'
ENV_FILE = PROJECT_ROOT / '.env'
BATCH_SIZE = 250


def read_env() -> dict[str, str]:
    values: dict[str, str] = {}
    for line in ENV_FILE.read_text(encoding='utf-8').splitlines():
        if not line or line.lstrip().startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def api_request(method: str, path: str, values: dict[str, str], **kwargs: Any) -> requests.Response:
    key = values.get('SUPABASE_SERVICE_ROLE_KEY', '')
    if not key:
        raise RuntimeError('SUPABASE_SERVICE_ROLE_KEY não configurada no .env.')
    response = requests.request(
        method,
        f"{values['SUPABASE_URL'].rstrip('/')}/rest/v1/{path}",
        headers={
            'apikey': key,
            'Authorization': f'Bearer {key}',
            'Content-Type': 'application/json',
            'Prefer': 'resolution=merge-duplicates,return=representation',
        },
        timeout=45,
        **kwargs,
    )
    response.raise_for_status()
    return response


def chunks(items: list[dict[str, Any]], size: int = BATCH_SIZE):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def main() -> None:
    if not CATALOG_DIR.exists():
        raise SystemExit('output_extracao não existe. Gere o catálogo antes de importar.')
    values = read_env()
    if not values.get('SUPABASE_URL'):
        raise SystemExit('SUPABASE_URL não configurada no .env.')

    categories = api_request('GET', 'categories?select=id,slug', values).json()
    category_ids = {item['slug']: item['id'] for item in categories}
    imported = 0

    for category_dir in sorted(path for path in CATALOG_DIR.iterdir() if path.is_dir()):
        slug = category_dir.name
        category_id = category_ids.get(slug)
        if not category_id:
            print(f'Categoria ignorada, sem registro no Supabase: {slug}')
            continue

        for group_dir in sorted(path for path in category_dir.iterdir() if path.is_dir()):
            playlist_file = group_dir / 'playlist.json'
            if not playlist_file.exists():
                continue
            playlist = json.loads(playlist_file.read_text(encoding='utf-8'))
            if not isinstance(playlist, list):
                continue
            group_name = next((str(item.get('group', '')).strip() for item in playlist if isinstance(item, dict) and item.get('group')), group_dir.name)
            group_response = api_request(
                'POST',
                'content_groups?on_conflict=category_id,name',
                values,
                json=[{'category_id': category_id, 'name': group_name}],
            ).json()
            group_id = group_response[0]['id']
            streams: list[dict[str, Any]] = []
            for item in playlist:
                if not isinstance(item, dict) or not item.get('url') or not item.get('name'):
                    continue
                streams.append({
                    'category_id': category_id,
                    'group_id': group_id,
                    'name': str(item['name']).strip(),
                    'stream_url': str(item['url']).strip(),
                    'logo_url': str(item.get('logo', '') or '').strip() or None,
                    'stream_type': str(item.get('type', slug) or slug),
                    'is_active': True,
                    'metadata': item,
                })
            for batch in chunks(streams):
                api_request('POST', 'streams?on_conflict=group_id,name', values, json=batch)
            imported += len(streams)
            print(f'{slug} / {group_name}: {len(streams)} links importados')

    print(f'Importação concluída: {imported} links processados.')


if __name__ == '__main__':
    main()
