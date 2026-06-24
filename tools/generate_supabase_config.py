"""Generate the browser-safe Supabase configuration from the local .env file."""

from __future__ import annotations

import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / '.env'
OUTPUT_FILE = PROJECT_ROOT / 'frontend' / 'supabase-config.js'


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip()
    return values


def main() -> None:
    if not ENV_FILE.exists():
        raise SystemExit('Crie o arquivo .env a partir de .env.example antes de gerar a configuração.')
    values = read_env(ENV_FILE)
    url = values.get('SUPABASE_URL', '')
    anon_key = values.get('SUPABASE_ANON_KEY', '')
    if not url or not anon_key:
        raise SystemExit('SUPABASE_URL e SUPABASE_ANON_KEY são obrigatórias no .env.')
    payload = json.dumps({'url': url, 'anonKey': anon_key}, ensure_ascii=False)
    OUTPUT_FILE.write_text(
        '// Generated from .env. This file only contains the public Supabase key.\n'
        f'window.HAVK_SUPABASE_CONFIG = Object.freeze({payload});\n',
        encoding='utf-8',
    )
    print(f'Configuração pública criada em {OUTPUT_FILE.relative_to(PROJECT_ROOT)}')


if __name__ == '__main__':
    main()
