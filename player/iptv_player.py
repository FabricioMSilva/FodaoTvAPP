from pathlib import Path
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

try:
    import requests
except ImportError:
    requests = None

from PyQt6.QtCore import QUrl, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import (
    QApplication,
    QWidget,
    QPushButton,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QLabel,
    QMessageBox,
    QInputDialog,
    QHBoxLayout,
    QVBoxLayout,
    QFrame,
    QTabWidget,
)
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtMultimediaWidgets import QVideoWidget


def parse_m3u_text(text):
    lines = [line.rstrip() for line in text.splitlines()]
    channels = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line or not line.startswith('#EXTINF'):
            index += 1
            continue

        info = line[8:].strip()
        attrs = {}
        name = info
        if ',' in info:
            attr_part, name_part = info.split(',', 1)
            name = name_part.strip()
            attr_parts = attr_part.split()
            for part in attr_parts:
                if '=' in part:
                    key, value = part.split('=', 1)
                    attrs[key.strip()] = value.strip().strip('"').strip(',')

        url = ''
        next_index = index + 1
        while next_index < len(lines):
            next_line = lines[next_index].strip()
            if not next_line:
                next_index += 1
                continue
            if next_line.startswith('#EXTINF'):
                break
            if next_line.startswith('#'):
                next_index += 1
                continue
            url = next_line
            break

        channels.append({
            'name': name,
            'url': url,
            'info': info,
            'group': attrs.get('group-title', 'Sem grupo'),
            'logo': attrs.get('tvg-logo', ''),
            'type': attrs.get('type', '').lower(),
        })
        index = next_index + 1
    return channels


def load_playlist_from_file(path):
    with open(path, 'r', encoding='utf-8', errors='replace') as handle:
        return parse_m3u_text(handle.read())


def load_playlist_from_url(url):
    request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        with urlopen(request, timeout=20) as response:
            text = response.read().decode('utf-8', errors='replace')
    except HTTPError as exc:
        raise RuntimeError(f'Erro HTTP {exc.code}: {exc.reason}') from exc
    except URLError as exc:
        raise RuntimeError(f'Falha na rede: {exc.reason}') from exc
    return parse_m3u_text(text)


DATA_FILE = Path('fodao_player_data.json')
APP_LOGO_PATH = Path(__file__).resolve().parent / 'frontend' / 'Copilot_20260622_114444.png'
DEFAULT_PLAYLIST_FILE = Path(__file__).resolve().parent / 'playlists' / 'J193C3484h-1782142237176.m3u8'


def classify_channel_category(channel):
    text = ' '.join([
        channel.get('group', ''),
        channel.get('name', ''),
        channel.get('info', ''),
    ]).lower()
    if any(keyword in text for keyword in ['filme', 'movie', 'cinema', 'movies', 'filmes', 'flix', 'box office']):
        return 'Filmes'
    if any(keyword in text for keyword in ['serie', 'series', 'tv show', 'temporada', 'episódio', 'episodio', 'season', 'seasons']):
        return 'Séries'
    return 'Canais'


def load_saved_data():
    if DATA_FILE.exists():
        try:
            import json
            return json.loads(DATA_FILE.read_text(encoding='utf-8'))
        except Exception:
            return {}
    return {}


def save_saved_data(data):
    import json
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')


class IPTVPlayerWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('Fodão Player')
        self.setMinimumSize(1200, 720)
        self.setAcceptDrops(True)

        if APP_LOGO_PATH.exists():
            self.setWindowIcon(QIcon(str(APP_LOGO_PATH)))
            self.app_logo = QPixmap(str(APP_LOGO_PATH)).scaled(48, 48, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        else:
            self.app_logo = None

        self.channels = []
        self.current_playlist = []
        self.categories = {'Todos': [], 'Canais': [], 'Filmes': [], 'Séries': []}
        self.groups_by_category = {'Todos': {}, 'Canais': {}, 'Filmes': {}, 'Séries': {}}
        self.data = load_saved_data()
        self.logo_cache = {}

        self.media_player = QMediaPlayer(self)
        self.audio_output = QAudioOutput(self)
        self.media_player.setAudioOutput(self.audio_output)

        self.video_widget = QVideoWidget(self)
        self.media_player.setVideoOutput(self.video_widget)

        self.build_ui()
        self.apply_styles()
        self.media_player.errorOccurred.connect(self.on_player_error)

        self.load_default_playlist()

    def build_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(12)

        title_bar = QHBoxLayout()
        title_icon = QLabel()
        if self.app_logo:
            title_icon.setPixmap(self.app_logo)
            title_icon.setFixedSize(48, 48)
        title_label = QLabel('Fodão Player')
        title_label.setObjectName('titleLabel')
        title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title_bar.addWidget(title_icon)
        title_bar.addWidget(title_label, 1)
        title_bar.setContentsMargins(0, 0, 0, 0)
        main_layout.addLayout(title_bar)

        toolbar_frame = QFrame()
        toolbar_frame.setObjectName('toolbarFrame')
        toolbar_layout = QHBoxLayout(toolbar_frame)
        toolbar_layout.setContentsMargins(10, 10, 10, 10)
        toolbar_layout.setSpacing(10)

        self.profile_input = QLineEdit()
        self.profile_input.setPlaceholderText('Perfil')
        self.profile_input.setFixedWidth(180)
        self.profile_input.editingFinished.connect(self.refresh_saved_content)
        toolbar_layout.addWidget(self.profile_input)

        self.save_playlist_button = QPushButton('Salvar playlist')
        self.save_playlist_button.clicked.connect(self.save_current_playlist)
        self.save_playlist_button.setEnabled(False)
        toolbar_layout.addWidget(self.save_playlist_button)

        self.reload_button = QPushButton('Recarregar playlist')
        self.reload_button.clicked.connect(self.load_default_playlist)
        toolbar_layout.addWidget(self.reload_button)

        self.playlist_info_label = QLabel(f'Playlist fixa: {DEFAULT_PLAYLIST_FILE.name}')
        self.playlist_info_label.setObjectName('playlistInfo')
        toolbar_layout.addWidget(self.playlist_info_label, 2)

        main_layout.addWidget(toolbar_frame)

        self.main_tab_widget = QTabWidget()
        self.main_tab_widget.setObjectName('mainTabWidget')
        self.main_tab_widget.setTabPosition(QTabWidget.TabPosition.North)

        player_tab = QWidget()
        player_layout = QVBoxLayout(player_tab)
        player_layout.setSpacing(10)

        self.video_frame = QFrame()
        self.video_frame.setObjectName('videoPanel')
        self.video_frame.setFrameShape(QFrame.Shape.StyledPanel)
        self.video_frame_layout = QVBoxLayout(self.video_frame)
        self.video_frame_layout.setContentsMargins(0, 0, 0, 0)
        self.video_frame_layout.addWidget(self.video_widget)

        self.welcome_label = QLabel('Carregue uma playlist M3U para começar\nArraste o arquivo aqui ou cole o link acima')
        self.welcome_label.setObjectName('welcomeLabel')
        self.welcome_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.welcome_label.setWordWrap(True)
        self.video_frame_layout.addWidget(self.welcome_label)

        player_layout.addWidget(self.video_frame, 3)

        info_frame = QFrame()
        info_frame.setObjectName('sectionFrame')
        info_layout = QVBoxLayout(info_frame)
        info_layout.setContentsMargins(12, 12, 12, 12)
        info_layout.setSpacing(6)

        self.current_channel_label = QLabel('Nenhum canal selecionado')
        self.current_channel_label.setObjectName('sectionLabel')
        info_layout.addWidget(self.current_channel_label)
        self.status_label = QLabel('Carregando playlist fixa...')
        info_layout.addWidget(self.status_label)
        self.favorites_info = QLabel('Favoritos: 0')
        info_layout.addWidget(self.favorites_info)

        player_layout.addWidget(info_frame)

        buttons_layout = QHBoxLayout()
        self.stop_button = QPushButton('Parar')
        self.stop_button.clicked.connect(self.stop_video)
        self.stop_button.setEnabled(False)
        buttons_layout.addWidget(self.stop_button)

        self.play_button = QPushButton('Reproduzir selecionado')
        self.play_button.clicked.connect(self.play_selected_channel)
        self.play_button.setEnabled(False)
        buttons_layout.addWidget(self.play_button)

        player_layout.addLayout(buttons_layout)
        self.main_tab_widget.addTab(player_tab, 'Player')

        browse_tab = QWidget()
        browse_layout = QHBoxLayout(browse_tab)
        browse_layout.setSpacing(10)

        navigation_panel = QFrame()
        navigation_panel.setObjectName('sectionFrame')
        navigation_layout = QVBoxLayout(navigation_panel)
        navigation_layout.setContentsMargins(12, 12, 12, 12)
        navigation_layout.setSpacing(10)

        section_label = QLabel('Explorar Canais')
        section_label.setObjectName('sectionLabel')
        navigation_layout.addWidget(section_label)

        self.category_tabs = QTabWidget()
        for category_name in ['Todos', 'Canais', 'Filmes', 'Séries']:
            page = QWidget()
            page_layout = QVBoxLayout(page)
            page_layout.setContentsMargins(0, 0, 0, 0)
            page_layout.addStretch()
            self.category_tabs.addTab(page, category_name)
        self.category_tabs.currentChanged.connect(self.on_category_changed)
        navigation_layout.addWidget(self.category_tabs)

        navigation_layout.addWidget(QLabel('Grupos / Categorias'))
        self.group_list = QListWidget()
        self.group_list.itemSelectionChanged.connect(self.on_group_selection_changed)
        navigation_layout.addWidget(self.group_list)

        navigation_layout.addWidget(QLabel('Playlists salvas'))
        self.saved_playlists_list = QListWidget()
        self.saved_playlists_list.itemActivated.connect(self.load_saved_playlist)
        navigation_layout.addWidget(self.saved_playlists_list)

        self.show_favorites_button = QPushButton('Mostrar favoritos')
        self.show_favorites_button.setCheckable(True)
        self.show_favorites_button.clicked.connect(self.filter_channels)
        self.show_favorites_button.setEnabled(False)
        navigation_layout.addWidget(self.show_favorites_button)
        browse_layout.addWidget(navigation_panel, 1)

        channel_panel = QFrame()
        channel_panel.setObjectName('sectionFrame')
        channel_layout = QVBoxLayout(channel_panel)
        channel_layout.setContentsMargins(12, 12, 12, 12)
        channel_layout.setSpacing(10)

        channel_layout.addWidget(QLabel('Buscar canal'))
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText('Buscar por nome, grupo ou texto')
        self.search_input.textChanged.connect(self.filter_channels)
        channel_layout.addWidget(self.search_input)

        self.channel_list = QListWidget()
        self.channel_list.itemActivated.connect(self.play_selected_channel)
        self.channel_list.itemSelectionChanged.connect(self.on_channel_selection_changed)
        channel_layout.addWidget(self.channel_list)

        self.favorite_button = QPushButton('Favoritar canal')
        self.favorite_button.clicked.connect(self.toggle_favorite)
        self.favorite_button.setEnabled(False)
        channel_layout.addWidget(self.favorite_button)
        browse_layout.addWidget(channel_panel, 2)

        self.main_tab_widget.addTab(browse_tab, 'Explorar')

        config_tab = QWidget()
        config_layout = QVBoxLayout(config_tab)
        config_layout.setSpacing(10)

        settings_frame = QFrame()
        settings_frame.setObjectName('sectionFrame')
        settings_layout = QVBoxLayout(settings_frame)
        settings_layout.setContentsMargins(12, 12, 12, 12)
        settings_layout.setSpacing(10)

        settings_label = QLabel('Configurações de playlist')
        settings_label.setObjectName('sectionLabel')
        settings_layout.addWidget(settings_label)
        settings_layout.addWidget(QLabel('O aplicativo usa apenas a playlist fixa abaixo:'))
        settings_layout.addWidget(QLabel(str(DEFAULT_PLAYLIST_FILE)))
        settings_layout.addSpacing(10)
        settings_layout.addWidget(QLabel('Dicas rápidas:'))
        settings_layout.addWidget(QLabel('• A playlist fixa é carregada automaticamente ao iniciar.'))
        settings_layout.addWidget(QLabel('• Clique em um item em Explorar para abrir a sub-playlist.'))
        settings_layout.addWidget(QLabel('• Use Recarregar playlist para voltar à lista principal.'))
        settings_layout.addWidget(QLabel('• Favorite canais para encontrá-los rápido.'))
        settings_layout.addStretch()

        config_layout.addWidget(settings_frame)
        self.main_tab_widget.addTab(config_tab, 'Configurações')

        main_layout.addWidget(self.main_tab_widget, 1)

    def on_channel_selection_changed(self):
        channel = self.get_selected_channel()
        if channel:
            self.current_channel_label.setText(
                f'Selecionado: {channel["name"]} | Grupo: {channel.get("group", "Sem grupo")} | Categoria: {channel.get("category", "Todos")}'
            )
        else:
            self.current_channel_label.setText('Nenhum canal selecionado')

    def open_file(self):
        QMessageBox.information(self, 'Atenção', 'O player usa apenas a playlist fixa em playlists/.\nNenhuma seleção adicional é necessária.')

    def populate_channel_list(self):
        self.channel_list.clear()
        self.group_list.clear()
        self.saved_playlists_list.clear()
        self.current_playlist = list(self.channels)

        self.categories = {'Todos': [], 'Canais': [], 'Filmes': [], 'Séries': []}
        self.groups_by_category = {'Todos': {}, 'Canais': {}, 'Filmes': {}, 'Séries': {}}

        for channel in self.channels:
            group = channel.get('group') or 'Sem grupo'
            category = classify_channel_category(channel)
            channel['category'] = category

            self.categories['Todos'].append(channel)
            self.categories[category].append(channel)

            self.groups_by_category['Todos'].setdefault(group, []).append(channel)
            self.groups_by_category[category].setdefault(group, []).append(channel)

        self.update_category_groups()
        self.update_channel_list()
        self.play_button.setEnabled(bool(self.channels))
        self.stop_button.setEnabled(False)
        self.save_playlist_button.setEnabled(bool(self.channels) and bool(self.profile_input.text().strip()))
        self.show_favorites_button.setEnabled(True)
        self.populate_saved_playlists()

    def populate_saved_playlists(self):
        self.saved_playlists_list.clear()
        profile = self.get_profile_data()
        for playlist_name in profile.get('playlists', {}).keys():
            self.saved_playlists_list.addItem(playlist_name)

    def update_channel_list(self, channels=None):
        self.channel_list.clear()
        selected_group = self.get_selected_group() or 'Todos'
        current_category = self.get_selected_category()
        channels = channels if channels is not None else self.categories.get(current_category, self.current_playlist)
        profile = self.get_profile_data()
        favorites = set(profile.get('favorites', []))
        show_favorites = self.show_favorites_button.isChecked()

        filtered = []
        for channel in channels:
            group = channel.get('group') or 'Sem grupo'
            if selected_group != 'Todos' and group != selected_group:
                continue
            if show_favorites and channel['name'] not in favorites:
                continue
            filtered.append(channel)

        if filtered:
            self.welcome_label.hide()
        else:
            self.welcome_label.show()

        for channel in filtered:
            name = channel['name']
            if name in favorites:
                display_name = f'★ {name}'
            else:
                display_name = name
            item = QListWidgetItem(display_name)
            if channel.get('logo'):
                icon = self.load_logo_icon(channel['logo'])
                if icon:
                    item.setIcon(icon)
            self.channel_list.addItem(item)
        self.play_button.setEnabled(bool(filtered))
        self.favorite_button.setEnabled(bool(filtered))
        self.show_favorites_button.setEnabled(bool(self.channels))

    def filter_channels(self):
        query = self.search_input.text().lower()
        selected_category = self.get_selected_category() or 'Todos'
        selected_group = self.get_selected_group() or 'Todos'
        profile = self.get_profile_data()
        favorites = set(profile.get('favorites', []))
        show_favorites = self.show_favorites_button.isChecked()

        filtered = []
        for channel in self.categories.get(selected_category, self.current_playlist):
            group = channel.get('group') or 'Sem grupo'
            if selected_group != 'Todos' and group != selected_group:
                continue
            if show_favorites and channel['name'] not in favorites:
                continue
            if query in channel['name'].lower() or query in channel['info'].lower() or query in group.lower():
                filtered.append(channel)

        self.channel_list.clear()
        for channel in filtered:
            name = channel['name']
            if name in favorites:
                display_name = f'★ {name}'
            else:
                display_name = name
            item = QListWidgetItem(display_name)
            if channel.get('logo'):
                icon = self.load_logo_icon(channel['logo'])
                if icon:
                    item.setIcon(icon)
            self.channel_list.addItem(item)
        self.play_button.setEnabled(bool(filtered))
        self.favorite_button.setEnabled(bool(filtered))

    def get_selected_channel(self):
        selected_items = self.channel_list.selectedItems()
        if not selected_items:
            return None
        selected_name = selected_items[0].text().lstrip('★ ').strip()
        for channel in self.channels:
            if channel['name'] == selected_name:
                return channel
        return None

    def get_profile_data(self):
        profile_name = self.profile_input.text().strip() or 'default'
        return self.data.setdefault(profile_name, {'favorites': [], 'playlists': {}})

    def refresh_saved_content(self):
        self.populate_saved_playlists()
        self.save_playlist_button.setEnabled(bool(self.channels) and bool(self.profile_input.text().strip()))

    def get_selected_category(self):
        index = self.category_tabs.currentIndex()
        return self.category_tabs.tabText(index) if index >= 0 else 'Todos'

    def get_selected_group(self):
        selected_items = self.group_list.selectedItems()
        if not selected_items:
            return None
        return selected_items[0].text()

    def on_category_changed(self):
        self.update_category_groups()
        self.filter_channels()

    def on_group_selection_changed(self):
        self.filter_channels()

    def update_category_groups(self):
        self.group_list.clear()
        current_category = self.get_selected_category()
        groups = self.groups_by_category.get(current_category, {})
        for group_name in sorted(groups.keys()):
            self.group_list.addItem(group_name)
        self.group_list.setCurrentRow(0)

    def play_selected_channel(self):
        channel = self.get_selected_channel()
        if not channel:
            QMessageBox.warning(self, 'Aviso', 'Selecione um canal antes de reproduzir.')
            return
        self.play_channel(channel)

    def play_channel(self, channel):
        url = channel['url']
        if not url:
            QMessageBox.warning(self, 'Aviso', 'URL de stream inválida.')
            return

        if channel.get('type') == 'playlist' or url.lower().endswith(('.m3u', '.m3u8')):
            try:
                self.channels = load_playlist_from_url(url)
                self.populate_channel_list()
                self.status_label.setText(f'Playlist carregada: {channel["name"]}')
                self.welcome_label.hide()
            except Exception as exc:
                QMessageBox.critical(self, 'Erro', f'Não foi possível carregar a sub-playlist: {exc}')
            return

        self.media_player.setSource(QUrl(url))
        self.media_player.play()
        self.status_label.setText(f'Tocando: {channel["name"]}')
        self.stop_button.setEnabled(True)
        self.welcome_label.hide()
        self.update_favorites_info()

    def stop_video(self):
        self.media_player.stop()
        self.status_label.setText('Reprodução parada.')
        self.stop_button.setEnabled(False)

    def toggle_favorite(self):
        channel = self.get_selected_channel()
        if not channel:
            return
        profile = self.get_profile_data()
        favorites = set(profile.get('favorites', []))
        if channel['name'] in favorites:
            favorites.remove(channel['name'])
        else:
            favorites.add(channel['name'])
        profile['favorites'] = list(favorites)
        save_saved_data(self.data)
        self.filter_channels()
        self.update_favorites_info()

    def update_favorites_info(self):
        profile = self.get_profile_data()
        count = len(profile.get('favorites', []))
        self.favorites_info.setText(f'Favoritos: {count}')

    def save_current_playlist(self):
        profile = self.get_profile_data()
        name, ok = QInputDialog.getText(self, 'Salvar playlist', 'Nome da playlist:')
        if not ok or not name.strip():
            return
        profile.setdefault('playlists', {})
        profile['playlists'][name.strip()] = {
            'file': str(DEFAULT_PLAYLIST_FILE),
        }
        save_saved_data(self.data)
        self.populate_saved_playlists()
        self.update_favorites_info()

    def load_saved_playlist(self):
        selected_items = self.saved_playlists_list.selectedItems()
        if not selected_items:
            return
        self.load_default_playlist()

    def load_default_playlist(self):
        if DEFAULT_PLAYLIST_FILE.exists():
            try:
                self.channels = load_playlist_from_file(str(DEFAULT_PLAYLIST_FILE))
                self.populate_channel_list()
                self.status_label.setText(f'Playlist carregada: {DEFAULT_PLAYLIST_FILE.name} ({len(self.channels)} canais)')
                self.welcome_label.hide()
            except Exception as exc:
                self.status_label.setText(f'Erro ao ler playlist fixa: {exc}')
        else:
            self.status_label.setText('Arquivo M3U fixo não encontrado em playlists/.')

    def apply_styles(self):
        self.setStyleSheet('''
            QWidget { background: #121212; color: #E0E0E0; font-family: Arial, sans-serif; }
            QLabel#titleLabel { font-size: 32px; font-weight: bold; color: #2196F3; margin: 12px 0; }
            QLabel#sectionLabel { font-size: 18px; font-weight: bold; margin-bottom: 8px; color: #FFB74D; }
            QPushButton { background: #1b1b1b; color: #E0E0E0; border: 1px solid #2196F3; border-radius: 12px; min-height: 38px; padding: 10px 14px; }
            QPushButton:hover { background: #2196F3; color: #121212; }
            QPushButton#primaryButton { background: #2196F3; color: #FFFFFF; border: 1px solid #42A5F5; }
            QLineEdit { background: #171717; border: 1px solid #333333; border-radius: 12px; padding: 10px; color: #E0E0E0; }
            QListWidget { background: #141414; border: 1px solid #333333; border-radius: 12px; color: #E0E0E0; }
            QListWidget::item:selected { background: #2196F3; color: #121212; }
            QFrame#toolbarFrame { background: #141414; border: 1px solid #222222; border-radius: 14px; }
            QFrame#sectionFrame { background: #161616; border: 1px solid #333333; border-radius: 14px; }
            QFrame#videoPanel { background: #000000; border: 1px solid #2A2A2A; border-radius: 16px; }
            QLabel#welcomeLabel { font-size: 20px; color: #E0E0E0; margin: 24px; }
            QTabWidget::pane { border: 1px solid #333333; background: #121212; border-radius: 12px; }
            QTabBar::tab { background: #141414; color: #E0E0E0; padding: 10px 16px; border: 1px solid #333333; border-bottom: none; border-top-left-radius: 10px; border-top-right-radius: 10px; }
            QTabBar::tab:selected { background: #2196F3; color: #121212; }
            QTabBar::tab:hover { background: #FF9800; color: #121212; }
        ''')

    def on_player_error(self, error, error_string):
        if error != QMediaPlayer.Error.NoError:
            QMessageBox.critical(self, 'Erro de mídia', f'Erro: {error_string}')
            self.status_label.setText(f'Erro de reprodução: {error_string}')
            self.stop_button.setEnabled(False)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        urls = event.mimeData().urls()
        if not urls:
            return
        path = urls[0].toLocalFile()
        if path.lower().endswith(('.m3u', '.m3u8')):
            try:
                self.channels = load_playlist_from_file(path)
                self.populate_channel_list()
                self.status_label.setText(f'Playlist carregada por arraste: {path} ({len(self.channels)} canais)')
                self.save_playlist_button.setEnabled(bool(self.channels) and bool(self.profile_input.text().strip()))
            except Exception as exc:
                QMessageBox.critical(self, 'Erro', f'Não foi possível carregar o arquivo: {exc}')
        else:
            QMessageBox.warning(self, 'Aviso', 'Arraste um arquivo M3U válido.')

    def load_logo_icon(self, logo_url):
        if not logo_url:
            return None
        if logo_url in self.logo_cache:
            return self.logo_cache[logo_url]
        try:
            response = requests.get(logo_url, timeout=5)
            response.raise_for_status()
            pixmap = QPixmap()
            pixmap.loadFromData(response.content)
            if not pixmap.isNull():
                icon = QIcon(pixmap.scaled(32, 32, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))
                self.logo_cache[logo_url] = icon
                return icon
        except Exception:
            pass
        return None


def main():
    app = QApplication([])
    window = IPTVPlayerWindow()
    window.show()
    app.exec()


if __name__ == '__main__':
    main()
