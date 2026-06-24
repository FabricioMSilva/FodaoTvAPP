import json
import pathlib
import requests
import urllib.parse
from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl

from backend.m3u_parser import parse_m3u_file, read_m3u_text, validate_playlist_path
from backend.user_store import UserStore

OUTPUT_DIR = pathlib.Path('users_output')
USER_STORE = UserStore(OUTPUT_DIR)
PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
PLAYLISTS_DIR = PROJECT_ROOT / 'player' / 'playlists'


def find_source_playlist() -> pathlib.Path:
    """Use the configured legacy file when present, otherwise the current playlist."""
    candidates = [
        PLAYLISTS_DIR / '2596364918xtvs-1782216748325.m3u8',
        PLAYLISTS_DIR / 'canaisfilmeseseries.m3u',
        PLAYLISTS_DIR / 'capas.m3u8',
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


SOURCE_PATH = find_source_playlist()
security = HTTPBasic()


def get_user_playlist_channels(username: str):
    playlist_file = OUTPUT_DIR / 'user_playlists' / f'{username}.m3u'
    if playlist_file.exists():
        return parse_m3u_file(playlist_file)

    if SOURCE_PATH.exists():
        return parse_m3u_file(SOURCE_PATH)

    raise HTTPException(status_code=404, detail='Playlist não encontrada para este usuário')


OUTPUT_EXTRACTION_DIR = PROJECT_ROOT / 'output_extracao'


def safe_catalog_part(value: str) -> str:
    """Keep catalog paths inside output_extracao and match extract_m3u_links.py names."""
    if not value or value in {'.', '..'} or '/' in value or '\\' in value:
        raise HTTPException(status_code=400, detail='Identificador de catálogo inválido')
    return value


def catalog_group_id(group_name: str) -> str:
    """Mirror extract_m3u_links.sanitize_filename without trusting a client path."""
    value = str(group_name).strip()
    for char in '<>:"/\\\\|?*':
        value = value.replace(char, '_')
    return safe_catalog_part(value.replace(' ', '_') or 'sem_grupo')


def read_catalog_summary() -> list[dict]:
    summary_file = OUTPUT_EXTRACTION_DIR / 'summary.json'
    if not summary_file.exists():
        raise HTTPException(status_code=404, detail='Catálogo de playlists não encontrado')
    try:
        data = json.loads(summary_file.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail='Catálogo de playlists inválido') from exc
    return [item for item in data if isinstance(item, dict)]


def normalize_catalog_channel(item: dict, content_type: str) -> dict:
    return {
        'name': item.get('name', ''),
        'url': item.get('url', ''),
        'logo': item.get('logo', ''),
        'group': item.get('group', '') or 'Outros',
        'type': item.get('type', '') or content_type,
        'tvg_id': item.get('tvg_id', ''),
        'tvg_name': item.get('tvg_name', ''),
    }


def is_adult_catalog_item(item: dict) -> bool:
    text = ' '.join([
        str(item.get('group', '')),
        str(item.get('name', '')),
        str(item.get('type', '')),
    ]).casefold()
    return any(term in text for term in ('adulto', 'adultos', '+18', 'hentai'))


def get_output_extracao_channels() -> list[dict]:
    if not OUTPUT_EXTRACTION_DIR.exists():
        raise HTTPException(status_code=404, detail='Diretório output_extracao não encontrado')

    channels = []
    for type_dir in sorted(OUTPUT_EXTRACTION_DIR.iterdir()):
        if not type_dir.is_dir():
            continue
        type_key = type_dir.name
        for group_dir in sorted(type_dir.iterdir()):
            if not group_dir.is_dir():
                continue
            playlist_file = group_dir / 'playlist.json'
            if not playlist_file.exists():
                continue
            try:
                playlist_data = json.loads(playlist_file.read_text(encoding='utf-8'))
            except json.JSONDecodeError:
                continue

            for item in playlist_data:
                if not isinstance(item, dict):
                    continue
                channels.append({
                    'name': item.get('name', ''),
                    'url': item.get('url', ''),
                    'logo': item.get('logo', ''),
                    'group': item.get('group', '') or item.get('group_title', '') or group_dir.name,
                    'type': type_key,
                    'raw': item,
                })
    return channels


def classify_channel_type(channel: dict) -> str:
    text = ' '.join([
        channel.get('group_title', ''),
        channel.get('name', ''),
        channel.get('url', ''),
    ]).lower()
    if any(term in text for term in ['filme', 'movie', 'cinema', 'film', 'flix']):
        return 'filmes'
    if any(term in text for term in ['serie', 'series', 'série', 'tv show', 'episódio', 'episode']):
        return 'series'
    if any(term in text for term in ['esporte', 'sports', 'live sports', 'futebol', 'sport']):
        return 'esportes'
    return 'ao-vivo'

app = FastAPI(title='IPTV Admin API')
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],
    allow_methods=['*'],
    allow_headers=['*'],
)
app.mount('/static', StaticFiles(directory='frontend'), name='static')


class GenerateRequest(BaseModel):
    users: int = Field(..., gt=0)
    username_prefix: str = 'user'
    password_length: int = Field(12, gt=5)
    no_symbols: bool = False
    base_url: HttpUrl = Field(default='http://localhost:8000')
    playlist_path: str = Field(default='playlist/{username}.m3u')


@app.get('/')
def index():
    return RedirectResponse(url='/static/index.html')


@app.get('/admin')
def admin_redirect():
    return RedirectResponse(url='/static/index.html')


@app.get('/player')
def player_redirect():
    return RedirectResponse(url='/static/player.html')


@app.get('/users')
def list_users():
    return USER_STORE.list_users()


def authenticate_user(username: str, credentials: HTTPBasicCredentials = Depends(security)):
    if credentials.username != username or not USER_STORE.check_password(username, credentials.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Credenciais inválidas',
            headers={'WWW-Authenticate': 'Basic'},
        )
    return True


def verify_query_user(username: str, password: str) -> None:
    """Compatibility helper for the browser player query-string API."""
    if not USER_STORE.check_password(username, password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Credenciais inválidas')
    try:
        USER_STORE.find_user(username)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail='Usuário não encontrado') from exc


@app.get('/api/catalog')
def catalog(username: str, password: str):
    """Small index used at player startup; never loads the playlist entries."""
    verify_query_user(username, password)
    totals: dict[str, int] = {}
    groups: dict[str, int] = {}
    for item in read_catalog_summary():
        if is_adult_catalog_item(item):
            continue
        content_type = item.get('type', 'outros')
        totals[content_type] = totals.get(content_type, 0) + int(item.get('count', 0))
        groups[content_type] = groups.get(content_type, 0) + 1
    return {
        'categories': [
            {'id': key, 'count': totals[key], 'groups': groups[key]}
            for key in sorted(totals)
        ]
    }


@app.get('/api/catalog/groups')
def catalog_groups(content_type: str, username: str, password: str):
    """Return only group labels/counts for one category."""
    verify_query_user(username, password)
    content_type = safe_catalog_part(content_type)
    groups = []
    for item in read_catalog_summary():
        if item.get('type') != content_type or is_adult_catalog_item(item):
            continue
        group_id = catalog_group_id(item.get('group') or 'sem_grupo')
        groups.append({
            'id': group_id,
            'name': item.get('group') or 'Sem grupo',
            'count': int(item.get('count', 0)),
        })
    return {'content_type': content_type, 'groups': sorted(groups, key=lambda group: group['name'].casefold())}


@app.get('/api/catalog/adult/groups')
def adult_catalog_groups(username: str, password: str):
    """Adult-only groups are intentionally absent from the ordinary catalog."""
    verify_query_user(username, password)
    groups = []
    for item in read_catalog_summary():
        if not is_adult_catalog_item(item):
            continue
        content_type = safe_catalog_part(item.get('type', 'outros'))
        groups.append({
            'id': catalog_group_id(item.get('group') or 'sem_grupo'),
            'name': item.get('group') or 'Conteúdo adulto',
            'count': int(item.get('count', 0)),
            'content_type': content_type,
        })
    return {'groups': sorted(groups, key=lambda group: (group['content_type'], group['name'].casefold()))}


@app.get('/api/proxy-m3u')
def proxy_m3u(url: str):
    """Proxy any remote M3U/M3U8 fetch to work around browser CORS restrictions."""
    if not url:
        raise HTTPException(status_code=400, detail='Parâmetro url é obrigatório')
    try:
        response = requests.get(url, timeout=20, headers={
            'User-Agent': 'HAVKIPTV/1.0',
            'Accept': 'application/vnd.apple.mpegurl, application/x-mpegURL, */*',
        })
        response.raise_for_status()
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f'Falha ao buscar M3U remoto: {exc}') from exc
    return Response(content=response.text, media_type='text/plain')


@app.get('/api/catalog/channels')
def catalog_channels(content_type: str, group_id: str, username: str, password: str):
    """Load one playlist.json only after the viewer selects its group."""
    verify_query_user(username, password)
    content_type = safe_catalog_part(content_type)
    group_id = safe_catalog_part(group_id)
    playlist_file = OUTPUT_EXTRACTION_DIR / content_type / group_id / 'playlist.json'
    if not playlist_file.exists():
        raise HTTPException(status_code=404, detail='Grupo de canais não encontrado')
    try:
        data = json.loads(playlist_file.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=500, detail='Playlist do grupo inválida') from exc
    channels = [normalize_catalog_channel(item, content_type) for item in data if isinstance(item, dict) and item.get('url')]
    return {'content_type': content_type, 'group_id': group_id, 'total': len(channels), 'streams': channels}


@app.post('/generate')
def generate_users(request: GenerateRequest):
    if not validate_playlist_path(request.playlist_path):
        raise HTTPException(status_code=400, detail='playlist_path deve conter {username}')
    if not SOURCE_PATH.exists():
        raise HTTPException(status_code=500, detail='Arquivo M3U de origem não encontrado')

    users = USER_STORE.add_users(
        prefix=request.username_prefix,
        count=request.users,
        password_length=request.password_length,
        no_symbols=request.no_symbols,
    )

    m3u_text = read_m3u_text(SOURCE_PATH)
    playlist_dir = OUTPUT_DIR / 'user_playlists'
    playlist_dir.mkdir(parents=True, exist_ok=True)

    for user in users:
        playlist_file = playlist_dir / f"{user['username']}.m3u"
        header = (
            f"# Generated for {user['username']}\n"
            f"# Password: {user['password']}\n"
            f"# Playlist URL: {request.base_url.rstrip('/')}" + f"/{request.playlist_path.format(username=user['username'])}\n"
        )
        playlist_file.write_text(header + m3u_text, encoding='utf-8')

    auth_users = []
    for user in users:
        auth_users.append({
            'username': user['username'],
            'password': user['password'],
            'playlist_url': f"{request.base_url.rstrip('/')}/{request.playlist_path.format(username=user['username'])}",
            'auth_url': f"{request.base_url.scheme}://{user['username']}:{user['password']}@{request.base_url.host}{':' + str(request.base_url.port) if request.base_url.port else ''}/{request.playlist_path.format(username=user['username'])}",
        })

    return {
        'generated': auth_users,
        'output_folder': str(OUTPUT_DIR.resolve()),
    }


@app.get('/playlist/{username}.m3u')
def get_playlist(username: str, authorized: bool = Depends(authenticate_user)):
    try:
        USER_STORE.find_user(username)
    except KeyError:
        raise HTTPException(status_code=404, detail='Usuário não encontrado')

    playlist_file = OUTPUT_DIR / 'user_playlists' / f'{username}.m3u'
    if not playlist_file.exists():
        raise HTTPException(status_code=404, detail='Playlist não encontrada')

    return Response(content=playlist_file.read_text(encoding='utf-8'), media_type='application/vnd.apple.mpegurl')


def render_m3u_from_channels(channels: list[dict]) -> str:
    lines = ['#EXTM3U']
    for item in channels:
        meta = []
        if item.get('logo'):
            meta.append(f'tvg-logo="{item["logo"]}"')
        group = item.get('group', '') or 'Outros'
        meta.append(f'group-title="{group}"')
        name = item.get('name', '') or 'Canal'
        lines.append(f'#EXTINF:-1 {" ".join(meta)},{name}')
        lines.append(item.get('url', ''))
    return '\n'.join(lines)

@app.get('/api/playlist_source')
def playlist_source(username: str, password: str, source: str = 'user'):
    if not USER_STORE.check_password(username, password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Credenciais inválidas',
            headers={'WWW-Authenticate': 'Basic'},
        )

    try:
        USER_STORE.find_user(username)
    except KeyError:
        raise HTTPException(status_code=404, detail='Usuário não encontrado')

    if source == 'output_extracao':
        channels = get_output_extracao_channels()
        if not channels:
            raise HTTPException(status_code=404, detail='Nenhum canal encontrado em output_extracao')
        return Response(content=render_m3u_from_channels(channels), media_type='application/vnd.apple.mpegurl')

    if not SOURCE_PATH.exists():
        raise HTTPException(status_code=404, detail='Fonte de playlist não encontrada')

    return Response(content=SOURCE_PATH.read_text(encoding='utf-8'), media_type='application/vnd.apple.mpegurl')


def rewrite_hls_playlist(text: str, base_url: str) -> str:
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            resolved = urllib.parse.urljoin(base_url, stripped)
            line = f"/proxy?url={urllib.parse.quote(resolved, safe='')}"
        lines.append(line)
    return '\n'.join(lines)


@app.get('/proxy')
def proxy(url: HttpUrl):
    try:
        remote = requests.get(str(url), stream=True, timeout=20, headers={'User-Agent': 'Mozilla/5.0'})
    except requests.RequestException as exc:
        raise HTTPException(status_code=502, detail=f'Erro ao buscar recurso remoto: {exc}')

    if remote.status_code != 200:
        raise HTTPException(status_code=remote.status_code, detail=f'Falha remota: {remote.reason}')

    content_type = remote.headers.get('Content-Type', 'application/octet-stream')
    remote_url = remote.url

    if 'mpegurl' in content_type.lower() or remote_url.lower().split('?', 1)[0].endswith('.m3u8'):
        # Only playlists are read in memory. Reading media segments here consumed
        # their response before StreamingResponse could send them to the browser.
        remote_text = remote.text
        remote.close()
        stripped = remote_text.strip()
        if not stripped.startswith('#EXTM3U'):
            error_detail = stripped.replace('\n', ' ')[:300]
            raise HTTPException(status_code=502, detail=f'Fonte remota retornou playlist inválida: {error_detail}')

        rewritten = rewrite_hls_playlist(remote_text, remote_url)
        return Response(content=rewritten, media_type='application/vnd.apple.mpegurl')

    def stream_remote():
        try:
            yield from remote.iter_content(chunk_size=64 * 1024)
        finally:
            remote.close()

    headers = {}
    if remote.headers.get('Content-Length'):
        headers['Content-Length'] = remote.headers['Content-Length']
    if remote.headers.get('Accept-Ranges'):
        headers['Accept-Ranges'] = remote.headers['Accept-Ranges']
    return StreamingResponse(stream_remote(), media_type=content_type, headers=headers)


@app.get('/api/player_api')
def player_api(username: str, password: str, action: str = 'get_vod_streams', source: str = 'user'):
    if not USER_STORE.check_password(username, password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Credenciais inválidas',
            headers={'WWW-Authenticate': 'Basic'},
        )

    try:
        USER_STORE.find_user(username)
    except KeyError:
        raise HTTPException(status_code=404, detail='Usuário não encontrado')

    if source == 'output_extracao':
        channels = get_output_extracao_channels()
    else:
        channels = get_user_playlist_channels(username)

    parsed = []
    for channel in channels:
        parsed.append({
            'name': channel.get('name', ''),
            'url': channel.get('url', ''),
            'logo': channel.get('logo', '') if source == 'output_extracao' else channel.get('tvg_logo', ''),
            'group': channel.get('group', '') if source == 'output_extracao' else channel.get('group_title', '') or 'Outros',
            'type': channel.get('type', 'unknown') if source == 'output_extracao' else classify_channel_type(channel),
            'tvg_id': channel.get('tvg_id', ''),
            'tvg_name': channel.get('tvg_name', ''),
        })

    if action == 'get_vod_streams':
        streams = [item for item in parsed if item['type'] in ('filmes', 'series', 'esportes', 'ao-vivo')]
    elif action == 'get_live_streams':
        streams = [item for item in parsed if item['type'] == 'ao-vivo']
    elif action == 'get_categories':
        categories = {}
        for item in parsed:
            categories[item['type']] = categories.get(item['type'], 0) + 1
        return {'categories': categories}
    else:
        raise HTTPException(status_code=400, detail=f'Ação inválida: {action}')

    return {
        'user': username,
        'action': action,
        'total': len(streams),
        'streams': streams,
    }


@app.get('/api/streams')
def streams_api(username: str, password: str, action: str = 'all', source: str = 'user'):
    if not USER_STORE.check_password(username, password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='Credenciais inválidas',
            headers={'WWW-Authenticate': 'Basic'},
        )

    try:
        USER_STORE.find_user(username)
    except KeyError:
        raise HTTPException(status_code=404, detail='Usuário não encontrado')

    if source == 'output_extracao':
        channels = get_output_extracao_channels()
    else:
        channels = get_user_playlist_channels(username)

    parsed = []
    for channel in channels:
        parsed.append({
            'name': channel.get('name', ''),
            'url': channel.get('url', ''),
            'logo': channel.get('logo', '') if source == 'output_extracao' else channel.get('tvg_logo', ''),
            'group': channel.get('group', '') if source == 'output_extracao' else channel.get('group_title', '') or 'Outros',
            'type': channel.get('type', 'unknown') if source == 'output_extracao' else classify_channel_type(channel),
            'tvg_id': channel.get('tvg_id', ''),
            'tvg_name': channel.get('tvg_name', ''),
        })

    if action == 'live':
        streams = [item for item in parsed if item['type'] == 'ao-vivo']
    elif action == 'vod':
        streams = [item for item in parsed if item['type'] in ('filmes', 'series', 'esportes', 'ao-vivo')]
    elif action == 'categories':
        categories = {}
        for item in parsed:
            categories[item['type']] = categories.get(item['type'], 0) + 1
        return {'categories': categories}
    else:
        streams = parsed

    return {
        'user': username,
        'action': action,
        'total': len(streams),
        'streams': streams,
    }
