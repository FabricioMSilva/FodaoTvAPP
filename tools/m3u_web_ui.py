import html
import io
import pathlib
import sys
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, List

ROOT_DIR = pathlib.Path(__file__).resolve().parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import m3u_user_passwords as app

HOST = '0.0.0.0'
PORT = 8080

DEFAULT_OUTPUT = pathlib.Path('users_output')
DEFAULT_SOURCE = pathlib.Path(__file__).resolve().parent.parent / 'player' / 'playlists' / 'canaisfilmeseseries.m3u'


def render_form(values: Dict[str, str], message: str = '', errors: List[str] = None) -> str:
    errors = errors or []
    message_html = f'<p style="color:green">{html.escape(message)}</p>' if message else ''
    error_html = ''.join(f'<p style="color:red">{html.escape(error)}</p>' for error in errors)
    save_playlists_checked = 'checked' if values.get('save_playlists') == 'on' else ''

    return f"""<!doctype html>
<html lang="pt-BR">
<head>
  <meta charset="utf-8">
  <title>IPTV M3U User Generator</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; }}
    input, label, textarea {{ display: block; margin-top: 8px; width: 100%; max-width: 800px; }}
    .panel {{ margin-bottom: 24px; padding: 16px; border: 1px solid #ddd; border-radius: 8px; background: #fafafa; }}
    .files a {{ display: block; margin: 4px 0; }}
    .small {{ font-size: 0.9em; color: #555; }}
    button {{ margin-top: 12px; padding: 10px 18px; font-size: 1em; }}
  </style>
</head>
<body>
  <h1>IPTV M3U User Generator</h1>
  <div class="panel">
    <h2>Configuração</h2>
    {message_html}
    {error_html}
    <form method="post" action="/generate">
      <label>Arquivo M3U de origem
        <input type="text" name="source" value="{html.escape(values.get('source', str(DEFAULT_SOURCE)))}" />
      </label>
      <label>Número de usuários
        <input type="number" name="users" value="{html.escape(values.get('users', '10'))}" min="1" />
      </label>
      <label>Prefixo de usuário
        <input type="text" name="username_prefix" value="{html.escape(values.get('username_prefix', 'user'))}" />
      </label>
      <label>Tamanho da senha
        <input type="number" name="password_length" value="{html.escape(values.get('password_length', '12'))}" min="6" />
      </label>
      <label>
        <input type="checkbox" name="no_symbols" {'checked' if values.get('no_symbols') == 'on' else ''} /> Gerar senhas sem símbolos
      </label>
      <label>
        <input type="checkbox" name="save_playlists" {save_playlists_checked} /> Salvar playlists individuais por usuário
      </label>
      <label>URL base para distribuição
        <input type="text" name="base_url" value="{html.escape(values.get('base_url', f'http://localhost:{PORT}'))}" />
        <span class="small">Ex: http://localhost:8000</span>
      </label>
      <label>Caminho da playlist na URL
        <input type="text" name="playlist_path" value="{html.escape(values.get('playlist_path', 'playlist/{username}.m3u'))}" />
        <span class="small">Deve conter {{username}}.</span>
      </label>
      <label>Saída
        <input type="text" name="output" value="{html.escape(values.get('output', str(DEFAULT_OUTPUT)))}" />
      </label>
      <button type="submit">Gerar credenciais</button>
    </form>
  </div>
  <div class="panel">
    <h2>Resultado</h2>
    <p class="small">Use o botão acima para gerar usuários e arquivos. Depois, você pode abrir os arquivos gerados na lista abaixo.</p>
    {render_output_files(values.get('output', str(DEFAULT_OUTPUT)))}
  </div>
</body>
</html>"""


def render_output_files(output_dir: str) -> str:
    path = pathlib.Path(output_dir)
    if not path.exists():
        return '<p>Nenhum arquivo ainda. Gere credenciais primeiro.</p>'
    entries = []
    for file_path in sorted(path.rglob('*')):
        if file_path.is_file():
            rel_path = file_path.relative_to(path).as_posix()
            url = f'/download/{urllib.parse.quote(rel_path)}'
            entries.append(f'<a href="{url}" target="_blank">{html.escape(rel_path)}</a>')
    if not entries:
        return '<p>A pasta de saída está vazia.</p>'
    return '<div class="files">' + ''.join(entries) + '</div>'


class M3UWebHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith('/download/'):
            self.serve_download()
            return
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        values = {k: v[0] for k, v in params.items()}
        if 'output' not in values:
            values['output'] = str(DEFAULT_OUTPUT)
        self.wfile.write(render_form(values).encode('utf-8'))

    def do_POST(self) -> None:
        if self.path != '/generate':
            self.send_error(404, 'Not Found')
            return
        content_type = self.headers.get('Content-Type', '')
        length = int(self.headers.get('Content-Length', '0'))
        body = self.rfile.read(length)
        values = urllib.parse.parse_qs(body.decode('utf-8'), keep_blank_values=True)
        fields = {k: v[0] for k, v in values.items()}
        fields.setdefault('output', str(DEFAULT_OUTPUT))
        fields.setdefault('base_url', f'http://{HOST}:{PORT}')
        fields.setdefault('playlist_path', 'playlist/{username}.m3u')
        errors = []

        try:
            source_path = pathlib.Path(fields['source'])
            if not source_path.exists():
                errors.append(f'Arquivo M3U não encontrado: {fields["source"]}')
                raise ValueError
            usernames = app.build_user_list(fields.get('username_prefix', 'user'), int(fields.get('users', '10')))
            if fields.get('user_file'):
                pass
            credentials = [
                {
                    'username': username,
                    'password': app.generate_password(length=int(fields.get('password_length', '12')), use_symbols=fields.get('no_symbols') != 'on'),
                }
                for username in usernames
            ]
            m3u_text = app.read_m3u_source(source_path)
            output_dir = pathlib.Path(fields['output'])
            app.save_credentials(
                output_dir=output_dir,
                credentials=credentials,
                save_playlists=True,
                m3u_text=m3u_text,
                playlist_path_format=fields.get('playlist_path', 'playlist/{username}.m3u'),
                base_url=fields.get('base_url', f'http://{HOST}:{PORT}'),
            )
            message = f'Geradas {len(credentials)} credenciais em {output_dir.resolve()}.'
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(render_form(fields, message=message).encode('utf-8'))
        except ValueError:
            self.send_response(400)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(render_form(fields, message='', errors=errors).encode('utf-8'))
        except Exception as exc:
            self.send_response(500)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            error_message = f'Erro interno: {html.escape(str(exc))}'
            self.wfile.write(render_form(fields, message='', errors=[error_message]).encode('utf-8'))

    def serve_download(self) -> None:
        rel_path = urllib.parse.unquote(self.path[len('/download/'):])
        output_dir = pathlib.Path(self.get_output_dir())
        file_path = (output_dir / rel_path).resolve()
        if not str(file_path).startswith(str(output_dir.resolve())) or not file_path.exists():
            self.send_error(404, 'File not found')
            return
        with file_path.open('rb') as f:
            data = f.read()
        self.send_response(200)
        self.send_header('Content-Type', 'application/octet-stream')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Content-Disposition', f'attachment; filename="{file_path.name}"')
        self.end_headers()
        self.wfile.write(data)

    def get_output_dir(self) -> str:
        query = urllib.parse.urlparse(self.path).query
        params = urllib.parse.parse_qs(query)
        return params.get('output', [str(DEFAULT_OUTPUT)])[0]

    def log_message(self, format: str, *args) -> None:
        pass


def run_server() -> None:
    server = ThreadingHTTPServer((HOST, PORT), M3UWebHandler)
    print(f'Serving web interface at http://{HOST}:{PORT}/')
    server.serve_forever()


if __name__ == '__main__':
    run_server()
