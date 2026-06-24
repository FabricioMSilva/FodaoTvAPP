import json
import pathlib
import secrets
import string
from typing import Dict, List


def generate_password(length: int = 12, use_symbols: bool = True) -> str:
    alphabet = string.ascii_letters + string.digits
    if use_symbols:
        alphabet += '!@#$%&*()-_=+?'
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class UserStore:
    def __init__(self, output_dir: pathlib.Path):
        self.output_dir = output_dir
        self.users_file = output_dir / 'users.json'
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.users: List[Dict[str, str]] = self._load_users()

    def _load_users(self) -> List[Dict[str, str]]:
        if not self.users_file.exists():
            return []
        return json.loads(self.users_file.read_text(encoding='utf-8'))

    def save(self) -> None:
        self.users_file.write_text(json.dumps(self.users, ensure_ascii=False, indent=2), encoding='utf-8')

    def list_users(self) -> List[Dict[str, str]]:
        return list(self.users)

    def add_users(self, prefix: str, count: int, password_length: int, no_symbols: bool) -> List[Dict[str, str]]:
        start = len(self.users) + 1
        new_users: List[Dict[str, str]] = []
        for index in range(start, start + count):
            user = {
                'username': f'{prefix}{index:03d}',
                'password': generate_password(length=password_length, use_symbols=not no_symbols),
            }
            self.users.append(user)
            new_users.append(user)
        self.save()
        return new_users

    def find_user(self, username: str) -> Dict[str, str]:
        for user in self.users:
            if user['username'] == username:
                return user
        raise KeyError(f'Usuário não encontrado: {username}')

    def check_password(self, username: str, password: str) -> bool:
        try:
            user = self.find_user(username)
        except KeyError:
            return False
        return secrets.compare_digest(user['password'], password)
