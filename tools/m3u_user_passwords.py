import argparse
import base64
import csv
import json
import pathlib
import secrets
import string
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import List, Optional
from urllib.parse import quote, urlparse, urlunparse


def generate_password(length: int = 12, use_symbols: bool = True) -> str:
    alphabet = string.ascii_letters + string.digits
    if use_symbols:
        alphabet += '!@#$%&*()-_=+?'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def read_usernames_from_file(path: pathlib.Path) -> List[str]:
    text = path.read_text(encoding='utf-8', errors='replace')
    return [line.strip() for line in text.splitlines() if line.strip()]


def build_user_list(prefix: str, count: int) -> List[str]:
    return [f'{prefix}{i:03d}' for i in range(1, count + 1)]


def read_m3u_source(path: pathlib.Path) -> str:
    return path.read_text(encoding='utf-8', errors='replace')


def ensure_directory(path: pathlib.Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def build_auth_url(base_url: str, username: str, password: str, playlist_path: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f'Base URL inválida: {base_url}')
    userinfo = f'{quote(username)}:{quote(password)}'
    netloc = f'{userinfo}@{parsed.netloc}'
    path = playlist_path if playlist_path.startswith('/') else '/' + playlist_path
    return urlunparse((parsed.scheme, netloc, path, '', '', ''))


def build_access_url(base_url: str, playlist_path: str) -> str:
    parsed = urlparse(base_url)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(f'Base URL inválida: {base_url}')
    path = playlist_path if playlist_path.startswith('/') else '/' + playlist_path
    return urlunparse((parsed.scheme, parsed.netloc, path, '', '', ''))


def save_credentials(
    output_dir: pathlib.Path,
    credentials: List[dict],
    save_playlists: bool,
    m3u_text: Optional[str],
    playlist_path_format: str,
    base_url: str,
) -> None:
    ensure_directory(output_dir)
    playlists_dir = output_dir / 'user_playlists'
    ensure_directory(playlists_dir)

    credentials_csv = output_dir / 'credentials.csv'
    credentials_json = output_dir / 'credentials.json'
    credentials_txt = output_dir / 'credentials.txt'
    distribution_csv = output_dir / 'distribution.csv'
    distribution_json = output_dir / 'distribution.json'

    for item in credentials:
        item['playlist_relative'] = playlist_path_format.format(username=item['username'])
        item['playlist_url'] = build_access_url(base_url, item['playlist_relative'])
        item['auth_url'] = build_auth_url(base_url, item['username'], item['password'], item['playlist_relative'])

    with credentials_csv.open('w', encoding='utf-8', newline='') as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=['username', 'password'])
        writer.writeheader()
        writer.writerows({
            'username': item['username'],
            'password': item['password'],
        } for item in credentials)

    credentials_json.write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding='utf-8')
    credentials_txt.write_text('\n'.join(f"{item['username']},{item['password']}" for item in credentials), encoding='utf-8')

    with distribution_csv.open('w', encoding='utf-8', newline='') as csv_file:
        fieldnames = ['username', 'password', 'playlist_url', 'auth_url']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows({k: item[k] for k in fieldnames} for item in credentials)

    distribution_json.write_text(json.dumps(credentials, ensure_ascii=False, indent=2), encoding='utf-8')

    if save_playlists and m3u_text is not None:
        for item in credentials:
            user_m3u = playlists_dir / f"{item['username']}.m3u"
            header = (
                f"# Generated for {item['username']}\n"
                f"# Password: {item['password']}\n"
                f"# Playlist URL: {item['auth_url']}\n"
            )
            user_m3u.write_text(header + m3u_text, encoding='utf-8')


class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


class PlaylistRequestHandler(BaseHTTPRequestHandler):
    server_version = 'M3UUserServer/1.0'
    playlist_root: pathlib.Path
    credentials: List[dict]

    def do_GET(self) -> None:
        if not self.path.startswith('/playlist/'):
            self.send_error(404, 'Not Found')
            return

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

        playlist_text = playlist_file.read_text(encoding='utf-8', errors='replace')
        self.send_response(200)
        self.send_header('Content-Type', 'application/x-mpegurl; charset=utf-8')
        self.send_header('Content-Length', str(len(playlist_text.encode('utf-8'))))
        self.end_headers()
        self.wfile.write(playlist_text.encode('utf-8'))

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
        self.send_header('WWW-Authenticate', 'Basic realm="M3U User Server"')
        self.send_header('Content-Type', 'text/plain; charset=utf-8')
        self.end_headers()
        self.wfile.write(b'Authentication required')

    def log_message(self, format: str, *args) -> None:
        sys.stdout.write('%s - - [%s] %s\n' % (self.client_address[0], self.log_date_time_string(), format % args))


def run_server(host: str, port: int, playlist_root: pathlib.Path, credentials: List[dict]) -> None:
    handler = PlaylistRequestHandler
    handler.playlist_root = playlist_root
    handler.credentials = credentials
    server = ThreadedHTTPServer((host, port), handler)
    print(f'Serving playlists at http://{host}:{port}/playlist/<username>.m3u')
    print('Use browser or IPTV player with basic auth credentials.')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\nServer stopped')
        server.server_close()


def main() -> None:
    parser = argparse.ArgumentParser(
        description='Gera senhas para vários usuários a partir de um arquivo M3U e pode servir playlists protegidos.'
    )
    parser.add_argument('--source', required=True, help='Caminho do arquivo M3U de origem.')
    parser.add_argument('--users', type=int, default=10, help='Número de usuários para gerar quando não usar --user-file.')
    parser.add_argument('--user-file', help='Arquivo de texto com nomes de usuário, um por linha. Se fornecido, ignora --users.')
    parser.add_argument('--username-prefix', default='user', help='Prefixo usado para nomes de usuário gerados automaticamente.')
    parser.add_argument('--password-length', type=int, default=12, help='Tamanho das senhas geradas.')
    parser.add_argument('--no-symbols', action='store_true', help='Gerar senhas sem caracteres especiais.')
    parser.add_argument('--output', default='users_output', help='Pasta de saída para credenciais e playlists geradas.')
    parser.add_argument('--save-playlists', action='store_true', help='Gerar um arquivo .m3u separado para cada usuário contendo o mesmo conteúdo original.')
    parser.add_argument('--serve', action='store_true', help='Iniciar um servidor HTTP local para servir as playlists protegidas por autenticação BASIC.')
    parser.add_argument('--host', default='0.0.0.0', help='Host do servidor HTTP quando usar --serve.')
    parser.add_argument('--port', type=int, default=8000, help='Porta do servidor HTTP quando usar --serve.')
    parser.add_argument('--base-url', help='URL base usada para gerar links de distribuição. Ex: http://meuserverdor.com:8000')
    parser.add_argument('--playlist-path', default='playlist/{username}.m3u', help='Caminho da playlist na URL. Deve incluir {username}.')
    args = parser.parse_args()

    source_path = pathlib.Path(args.source)
    if not source_path.exists():
        raise FileNotFoundError(f'Arquivo M3U não encontrado: {source_path}')

    if args.user_file:
        user_path = pathlib.Path(args.user_file)
        if not user_path.exists():
            raise FileNotFoundError(f'Arquivo de usuários não encontrado: {user_path}')
        usernames = read_usernames_from_file(user_path)
        if not usernames:
            raise ValueError('O arquivo de usuários está vazio ou não contém nomes válidos.')
    else:
        if args.users < 1:
            raise ValueError('O número de usuários deve ser maior que zero.')
        usernames = build_user_list(args.username_prefix, args.users)

    if '{username}' not in args.playlist_path:
        raise ValueError('O argumento --playlist-path deve conter {username}.')

    m3u_text = read_m3u_source(source_path)
    if not m3u_text.strip().startswith('#EXTM3U'):
        raise ValueError('O arquivo M3U deve começar com #EXTM3U.')

    credentials = []
    for username in usernames:
        credentials.append({
            'username': username,
            'password': generate_password(length=args.password_length, use_symbols=not args.no_symbols),
        })

    output_dir = pathlib.Path(args.output)
    base_url = args.base_url.strip() if args.base_url else f'http://{args.host}:{args.port}'
    save_credentials(output_dir, credentials, True, m3u_text, args.playlist_path, base_url)

    print(f'Geradas {len(credentials)} credenciais em: {output_dir.resolve()}')
    print('Arquivos criados: credentials.csv, credentials.json, credentials.txt, distribution.csv, distribution.json')
    if args.save_playlists:
        print(f'Playlists por usuário em: {output_dir / "user_playlists"}')

    if args.serve:
        playlist_root = output_dir / 'user_playlists'
        if not playlist_root.exists():
            raise FileNotFoundError(f'Pasta de playlists não encontrada: {playlist_root}')
        run_server(args.host, args.port, playlist_root, credentials)


if __name__ == '__main__':
    main()
