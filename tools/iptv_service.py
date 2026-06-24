import argparse
import base64
import csv
import json
import pathlib
import re
import secrets
import string
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any, Dict, List
from urllib.parse import quote, urlparse, urlunparse

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


def generate_password(length: int = 12, use_symbols: bool = True) -> str:
    alphabet = string.ascii_letters + string.digits
    if use_symbols:
        alphabet += '!@#$%&*()-_=+?'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def load_users(users_file: pathlib.Path) -> List[Dict[str, str]]:
    if not users_file.exists():
        return []
    return json.loads(users_file.read_text(encoding='utf-8'))


def save_users(users_file: pathlib.Path, users: List[Dict[str, str]]) -> None:
    users_file.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding='utf-8')


def ensure_directory(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_auth_url(base_url: str, username: str, password: str, playlist_path: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f'Base URL inválida: {base_url}')
    userinfo = f'{quote(username)}:{quote(password)}'
    return urlunparse((parsed.scheme, f'{userinfo}@{parsed.netloc}', playlist_path if playlist_path.startswith('/') else '/' + playlist_path, '', '', ''))


def build_access_url(base_url: str, playlist_path: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f'Base URL inválida: {base_url}')
    return urlunparse((parsed.scheme, parsed.netloc, playlist_path if playlist_path.startswith('/') else '/' + playlist_path, '', '', ''))


def create_user_playlists(
    output_dir: pathlib.Path,
    channels_text: str,
    users: List[Dict[str, str]],
    playlist_path_format: str,
    base_url: str,
) -> None:
    playlists_dir = output_dir / 'user_playlists'
    ensure_directory(playlists_dir)
    for user in users:
        user['playlist_relative'] = playlist_path_format.format(username=user['username'])
        user['playlist_url'] = build_access_url(base_url, user['playlist_relative'])
        user['auth_url'] = build_auth_url(base_url, user['username'], user['password'], user['playlist_relative'])
        playlist_file = playlists_dir / f"{user['username']}.m3u"
        header = (
            f"# Generated for {user['username']}\n"
            f"# Password: {user['password']}\n"
            f"# Playlist URL: {user['auth_url']}\n"
            "# NOTE: use username/password in your IPTV player or use the auth url.\n"
        )
        playlist_file.write_text(header + channels_text, encoding='utf-8')


def save_distribution_files(output_dir: pathlib.Path, users: List[Dict[str, str]]) -> None:
    ensure_directory(output_dir)
    credentials_csv = output_dir / 'credentials.csv'
    distribution_csv = output_dir / 'distribution.csv'
    distribution_json = output_dir / 'distribution.json'

    with credentials_csv.open('w', encoding='utf-8', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=['username', 'password'])
        writer.writeheader()
        writer.writerows({'username': u['username'], 'password': u['password']} for u in users)

    with distribution_csv.open('w', encoding='utf-8', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=['username', 'password', 'playlist_url', 'auth_url'])
        writer.writeheader()
        writer.writerows(
            {
                'username': u['username'],
                'password': u['password'],
                'playlist_url': u['playlist_url'],
                'auth_url': u['auth_url'],
            }
            for u in users
        )

    distribution_json.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding='utf-8')


def add_users(users: List[Dict[str, str]], prefix: str, count: int, password_length: int, no_symbols: bool) -> List[Dict[str, str]]:
    start = len(users) + 1
    for i in range(start, start + count):
        users.append({
            'username': f'{prefix}{i:03d}',
            'password': generate_password(length=password_length, use_symbols=not no_symbols),
        })
    return users


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class PlaylistRequestHandler(BaseHTTPRequestHandler):
    playlist_root: pathlib.Path
    credentials: List[Dict[str, str]]

    def do_GET(self) -> None:
        if self.path.startswith('/playlist/'):  # /playlist/<username>.m3u
            self.handle_playlist_request()
            return

        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        html_response = (
            '<html><body><h1>IPTV Service Running</h1>'
            '<p>Use /playlist/&lt;username&gt;.m3u with Basic Auth to access.</p>'
            '</body></html>'
        )
        self.wfile.write(html_response.encode('utf-8'))

    def handle_playlist_request(self) -> None:
        username = pathlib.Path(self.path[len('/playlist/'):]).stem
        if not username:
            self.send_error(404, 'Not Found')
            return

        if not self.check_auth(username):
            self.require_auth()
            return

        playlist_file = self.playlist_root / f'{username}.m3u'
        if not playlist_file.exists():
            self.send_error(404, 'Playlist not found')
            return

        content = playlist_file.read_text(encoding='utf-8', errors='replace')
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-mpegurl; charset=utf-8')
        self.send_header('Content-Length', str(len(content.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(content.encode('utf-8'))

    def check_auth(self, username: str) -> bool:
        header = self.headers.get('Authorization')
        if not header or not header.startswith('Basic '):
            return False
        token = header.split(' ', 1)[1].strip()
        try:
            decoded = base64.b64decode(token).decode('utf-8')
        except Exception:
            return False
        if ':' not in decoded:
            return False
        user, password = decoded.split(':', 1)
        if user != username:
            return False
        for item in self.credentials:
            if item['username'] == user and item['password'] == password:
                return True
        return False

    def require_auth(self) -> None:
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm="IPTV Service"')
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'Authentication required')

    def log_message(self, format: str, *args) -> None:
        sys.stdout.write('%s - - [%s] %s\n' % (self.client_address[0], self.log_date_time_string(), format % args))


def run_server(host: str, port: int, playlist_root: pathlib.Path, credentials: List[Dict[str, str]]) -> None:
    handler = PlaylistRequestHandler
    handler.playlist_root = playlist_root
    handler.credentials = credentials
    server = ThreadedHTTPServer((host, port), handler)
    print(f'Serving playlists at http://{host}:{port}/playlist/<username>.m3u')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped')
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(description='IPTV user and playlist manager.')
    parser.add_argument('--source', required=True, help='Caminho do M3U de origem')
    parser.add_argument('--output', default='users_output', help='Pasta de saída para arquivos gerados')
    parser.add_argument('--users', type=int, default=1, help='Número de novos usuários a criar')
    parser.add_argument('--username-prefix', default='user', help='Prefixo para nomes de usuário')
    parser.add_argument('--password-length', type=int, default=12, help='Tamanho das senhas')
    parser.add_argument('--no-symbols', action='store_true', help='Gerar senhas sem símbolos')
    parser.add_argument('--base-url', default='http://localhost:8080', help='URL base para geração de links')
    parser.add_argument('--playlist-path', default='playlist/{username}.m3u', help='Caminho de playlist na URL')
    parser.add_argument('--serve', action='store_true', help='Iniciar servidor HTTP após gerar usuários')
    parser.add_argument('--host', default='0.0.0.0', help='Host do servidor HTTP')
    parser.add_argument('--port', type=int, default=8080, help='Porta do servidor HTTP')
    args = parser.parse_args()

    source_path = pathlib.Path(args.source)
    if not source_path.exists():
        raise FileNotFoundError(f'Arquivo M3U não encontrado: {source_path}')

    output_dir = pathlib.Path(args.output)
    users_file = output_dir / 'users.json'
    ensure_directory(output_dir)

    users = load_users(users_file)
    users = add_users(users, args.username_prefix, args.users, args.password_length, args.no_symbols)
    save_users(users_file, users)

    channels_text = source_path.read_text(encoding='utf-8', errors='replace')
    create_user_playlists(output_dir, channels_text, users, args.playlist_path, args.base_url)
    save_distribution_files(output_dir, users)

    print(f'Geradas {args.users} novos usuários. Saída em: {output_dir.resolve()}')
    print(f'Use as URLs em distribution.csv ou os arquivos em {output_dir / "user_playlists"}.')

    if args.serve:
        playlist_root = output_dir / 'user_playlists'
        if not playlist_root.exists():
            raise FileNotFoundError(f'Pasta de playlists não encontrada: {playlist_root}')
        run_server(args.host, args.port, playlist_root, users)


if __name__ == '__main__':
    main()
