import subprocess
import sys
from pathlib import Path

project_dir = Path(__file__).resolve().parent
PROJECT_ROOT = project_dir.parent

if __name__ == '__main__':
    python_exe = sys.executable
    logo_path = PROJECT_ROOT / 'frontend' / 'Copilot_20260622_114444.png'
    add_data = f'{logo_path};frontend' if logo_path.exists() else None
    cmd = [
        python_exe,
        '-m', 'PyInstaller',
        '--noconfirm',
        '--onefile',
        '--windowed',
        '--name', 'FodaoPlayer',
    ]
    if add_data:
        cmd += ['--add-data', add_data]
    cmd.append('iptv_player.py')
    subprocess.run(cmd, cwd=str(project_dir))
