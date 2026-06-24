import webbrowser
import pathlib
import subprocess

BASE_DIR = pathlib.Path(__file__).resolve().parent
PROJECT_ROOT = BASE_DIR.parent

if __name__ == '__main__':
    try:
        subprocess.Popen(['python', 'iptv_player.py'], cwd=str(BASE_DIR))
    except FileNotFoundError:
        print('Não foi possível iniciar o player Python. Verifique se o Python está instalado.')
    webbrowser.open_new_tab((PROJECT_ROOT / 'frontend' / 'player.html').as_uri())
