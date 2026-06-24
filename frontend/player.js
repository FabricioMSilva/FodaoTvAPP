// ============================================
// FODÃO PLAYER - Main Player Script
// ============================================

// DOM Elements
const supabase = window.havkSupabase;
const videoPlayer = document.getElementById('video-player');
const videoContainer = document.querySelector('.video-container');
const availableGallery = document.getElementById('available-gallery');
const searchInput = document.getElementById('search-input');
const channelList = document.getElementById('channel-list');
const sectionTitle = document.getElementById('section-title');
const displayUsername = document.getElementById('display-username');
const channelCount = document.getElementById('channel-count');
const messageContainer = document.getElementById('message-container');
const toggleSidebar = document.getElementById('toggle-sidebar');
const sidebar = document.querySelector('.sidebar');
const navItems = document.querySelectorAll('.nav-item');
const settingsBtn = document.getElementById('settings-btn');
const profileBtn = document.getElementById('profile-btn');
const settingsModal = document.getElementById('settings-modal');
const profileModal = document.getElementById('profile-modal');
const closeModals = document.querySelectorAll('.close-modal');
const contentGrid = document.getElementById('content-grid');
const categoriesSection = document.getElementById('categories-section');
const mainGrid = document.getElementById('main-grid');
const continuaGrid = document.getElementById('continua-grid');
const lancamentosGrid = document.getElementById('lancamentos-grid');
const maisVistosGrid = document.getElementById('mais-vistos-grid');
const minhaListaGrid = document.getElementById('minha-lista-grid');
const heroBanner = document.getElementById('hero-banner');
const heroCurrentChannel = document.getElementById('hero-current-channel');
const heroTotalChannels = document.getElementById('hero-total-channels');
const heroFavoriteCount = document.getElementById('hero-favorite-count');
const heroWatchBtn = document.getElementById('hero-watch-btn');
const profileUsername = document.getElementById('profile-username');
const playerNowTitle = document.getElementById('player-now-title');

// State
let currentChannels = [];
let currentChannelPool = [];
let allChannels = [];
let channelsByCategory = {};
let currentUsername = '';
let currentUser = null;
let currentProfile = null;
let currentCategory = '';
let currentGroupPath = [];
let groupTrees = {};
let currentPlayingChannel = null;
let hls = null;
let playlistLoaded = false;
let displayedChannelsCount = 0;
const channelBatchSize = 50;
let favorites = [];
let catalogGroups = {};
let categoryRecords = {};
let selectedGroupId = '';
let playbackRequest = 0;
let catalogVisibleCount = 60;
let adultAccessGranted = sessionStorage.getItem('fodao-adult-access') === 'true';
const ADULT_ACCESS_PIN = '0000';

// UI Elements
const homeScreen = document.getElementById('home-screen');
const playerSection = document.getElementById('player-section');
const loadMoreBtn = document.getElementById('load-more-btn');
const categoryButtons = document.querySelectorAll('.category-card');
const catalogModal = document.getElementById('catalog-modal');
const catalogCards = document.getElementById('catalog-cards');
const catalogModalTitle = document.getElementById('catalog-modal-title');
const catalogModalSubtitle = document.getElementById('catalog-modal-subtitle');
const catalogMoreBtn = document.getElementById('catalog-more-btn');
const adultAccessModal = document.getElementById('adult-access-modal');
const adultAccessForm = document.getElementById('adult-access-form');
const adultAccessPin = document.getElementById('adult-access-pin');
const adultAccessCopy = document.getElementById('adult-access-copy');
const adultAccessError = document.getElementById('adult-access-error');
const mobileChannelsBtn = document.getElementById('mobile-channels-btn');
const mobileChannelModal = document.getElementById('mobile-channel-modal');
const mobileChannelClose = document.getElementById('mobile-channel-close');
const mobileChannelBack = document.getElementById('mobile-channel-back');
const mobileChannelGroups = document.getElementById('mobile-channel-groups');
const mobileChannelList = document.getElementById('mobile-channel-list');
const mobileChannelTitle = document.getElementById('mobile-channel-title');
const mobileChannelSubtitle = document.getElementById('mobile-channel-subtitle');
const mobileMinimizeBtn = document.getElementById('mobile-minimize-btn');
const mobileAppShell = document.getElementById('mobile-app-shell');
const mobileHomeHero = document.getElementById('mobile-home-hero');
const mobileHomeGroups = document.getElementById('mobile-home-groups');
const mobileHomeCards = document.getElementById('mobile-home-cards');
const mobileHomeSearchInput = document.getElementById('mobile-home-search-input');
const mobileHomeCardsTitle = document.getElementById('mobile-home-cards-title');
const adminBtn = document.getElementById('admin-btn');
const profileAdminBtn = document.getElementById('profile-admin-btn');
const adminCatalogModal = document.getElementById('admin-catalog-modal');
const adminM3uFile = document.getElementById('admin-m3u-file');
const adminM3uUrl = document.getElementById('admin-m3u-url');
const adminLoadUrlBtn = document.getElementById('admin-load-url-btn');
const adminM3uSummary = document.getElementById('admin-m3u-summary');
const adminImportBtn = document.getElementById('admin-import-btn');
let pendingAdminCatalog = null;
const APP_VERSION = '1.0.0';
const UPDATE_CHECK_URL = '/version.json';
const UPDATE_CHECK_INTERVAL = 1000 * 60 * 10; // 10 minutos
const MAX_NESTED_PLAYLIST_FETCH = 12;
const MAX_CATALOG_ENTRIES = 20000;

// ============================================
// INITIALIZATION
// ============================================

document.addEventListener('DOMContentLoaded', () => {
  initializePlayer();
});

async function initializePlayer() {
  if (!supabase) {
    window.location.href = 'index.html';
    return;
  }
  const { data: { session } } = await supabase.auth.getSession();
  if (!session?.user) {
    window.location.href = 'index.html';
    return;
  }

  currentUser = session.user;
  currentUsername = session.user.email || 'Usuário';
  const { data: profile, error: profileError } = await supabase
    .from('profiles')
    .select('role, is_active, expires_at, display_name')
    .eq('id', session.user.id)
    .single();
  if (profileError || !profile?.is_active || (profile.expires_at && new Date(profile.expires_at) < new Date())) {
    await supabase.auth.signOut();
    window.location.href = 'index.html';
    return;
  }
  currentProfile = profile;
  displayUsername.textContent = currentUsername.toUpperCase();
  if (profileUsername) profileUsername.textContent = currentUsername.toUpperCase();

  favorites = JSON.parse(localStorage.getItem('fodao-favorites') || '[]');
  setupEventListeners();
  enableAdminInterface();
  activateMobileShell();
  showHomeScreen();
  await checkForAppUpdate();
  startPeriodicUpdateCheck();
  loadPlaylist();
}

function showHomeScreen() {
  if (homeScreen) homeScreen.style.display = 'flex';
  if (playerSection) playerSection.style.display = 'none';
  if (contentGrid) contentGrid.style.display = 'none';
  if (categoriesSection) categoriesSection.style.display = 'none';
  if (heroBanner) heroBanner.style.display = 'none';
}

function showHeroScreen() {
  if (homeScreen) homeScreen.style.display = 'flex';
  if (heroBanner) heroBanner.style.display = 'flex';
  if (playerSection) playerSection.style.display = 'none';
  if (contentGrid) contentGrid.style.display = 'none';
  if (categoriesSection) categoriesSection.style.display = 'none';
}

function showPlayerScreen() {
  if (homeScreen) homeScreen.style.display = 'none';
  if (playerSection) playerSection.style.display = 'grid';
  if (contentGrid) contentGrid.style.display = 'none';
  if (categoriesSection) categoriesSection.style.display = 'block';
  if (heroBanner) heroBanner.style.display = 'none';
}

// ============================================
// PLAYLIST LOADING
// ============================================

async function loadPlaylist() {
  try {
    showMessage('Carregando catálogo...', 'info');
    const { data, error } = await supabase
      .from('categories')
      .select('id, slug, name, sort_order')
      .order('sort_order');
    if (error) throw error;
    if (!data?.length) throw new Error('Nenhuma categoria retornada pelo Supabase');
    categoryRecords = Object.fromEntries(data.map(category => [category.slug, category]));

    playlistLoaded = true;
    updateHeroInfo();
    openCategory('ao-vivo');
    showMessage('TV ao vivo pronta. Escolha um grupo para começar.', 'success');
  } catch (error) {
    showMessage(`Erro ao carregar catálogo: ${error.message}`, 'error');
  }
}

function enableAdminInterface() {
  if (currentProfile?.role !== 'admin') return;
  if (adminBtn) adminBtn.style.display = '';
  if (profileAdminBtn) profileAdminBtn.style.display = '';
}

async function loadGroups(category) {
  if (category === 'favoritos') {
    renderFavoriteGroups();
    return;
  }
  try {
    if (!catalogGroups[category]) {
      const categoryRecord = categoryRecords[category];
      if (!categoryRecord) throw new Error('Categoria não encontrada');
      const { data, error } = await supabase
        .from('content_groups')
        .select('id, name, sort_order, streams(count)')
        .eq('category_id', categoryRecord.id)
        .order('sort_order')
        .order('name');
      if (error) throw error;
      catalogGroups[category] = (data || []).map(group => ({
        id: group.id,
        name: group.name,
        count: group.streams?.[0]?.count || 0,
        content_type: category,
      }));
    }
    renderCatalogGroups(catalogGroups[category]);
  } catch (error) {
    showMessage(`Não foi possível carregar os grupos: ${error.message}`, 'error');
  }
}

function renderCatalogGroups(groups) {
  const container = document.getElementById('group-tree');
  if (!container) return;
  if (!groups.length) {
    container.innerHTML = '<p style="padding:16px;color:var(--text-muted)">Nenhum grupo disponível.</p>';
    return;
  }
  container.innerHTML = `<div class="breadcrumb"><span class="breadcrumb-item">Grupos</span></div>
    <div class="group-items">${groups.map(group => `
      <button class="group-item ${group.id === selectedGroupId ? 'active' : ''}" data-group-id="${group.id}" data-content-type="${group.content_type || currentCategory}">
        <span class="group-item-label"><span class="group-item-name">${group.name}</span><span class="group-item-count">${group.count} itens</span></span>
        <span class="group-item-chevron">▶</span>
      </button>`).join('')}</div>`;
  container.querySelectorAll('[data-group-id]').forEach(button => {
    button.addEventListener('click', () => loadGroup(button.dataset.groupId, button.dataset.contentType));
  });
  if (mobileChannelModal?.classList.contains('show')) renderMobileGroups(groups);
  renderMobileShellGroups(groups);
}

function renderFavoriteGroups() {
  const container = document.getElementById('group-tree');
  const favoriteChannels = getFavoriteChannels();
  if (container) container.innerHTML = '<div class="breadcrumb"><span class="breadcrumb-item">Favoritos carregados</span></div>';
  setChannelPool(favoriteChannels);
}

async function loadGroup(groupId, requestedContentType = currentCategory) {
  if (!currentCategory || currentCategory === 'favoritos') return;
  try {
    showMessage('Carregando grupo selecionado...', 'info');
    const contentType = requestedContentType || currentCategory;
    const { data, error } = await supabase
      .from('streams')
      .select('id, name, stream_url, logo_url, stream_type, content_groups(name)')
      .eq('group_id', groupId)
      .eq('is_active', true)
      .order('name');
    if (error) throw error;
    selectedGroupId = groupId;
    allChannels = (data || []).map(channel => {
      const group = channel.content_groups?.name || 'Outros';
      const groupPath = parseGroupPath(group);
      return {
        id: channel.id,
        name: channel.name,
        url: channel.stream_url,
        logo: channel.logo_url || '',
        type: channel.stream_type || contentType,
        group,
        groupPath,
        groupPathString: groupPath.join(' / ') || 'Outros',
      };
    });
    classifyChannels();
    setChannelPool(allChannels);
    renderCatalogGroups(catalogGroups[currentCategory] || []);
    populateContentRows();
    updateHeroInfo();
    if (mobileChannelModal?.classList.contains('show')) renderMobileChannels(allChannels);
    renderMobileShellCards(allChannels);
    if (contentType === 'filmes' || contentType === 'series') {
      openVisualCatalog(groupId);
    }
    showMessage(`${allChannels.length} itens carregados.`, 'success');
  } catch (error) {
    showMessage(`Não foi possível carregar este grupo: ${error.message}`, 'error');
  }
}

function setChannelPool(channels) {
  currentChannelPool = channels;
  displayedChannelsCount = Math.min(channelBatchSize, channels.length);
  currentChannels = channels.slice(0, displayedChannelsCount);
  channelCount.textContent = channels.length;
  renderChannels(currentChannels);
  renderAvailableGallery(channels);
  updateLoadMoreButton(channels.length);
}

function renderAvailableGallery(channels) {
  if (!availableGallery || !videoContainer) return;
  videoContainer.classList.add('browse-mode');
  availableGallery.replaceChildren();

  if (!channels.length) {
    availableGallery.innerHTML = '<p class="gallery-empty">Selecione um grupo para ver os canais disponíveis.</p>';
    return;
  }

  const heading = document.createElement('div');
  heading.className = 'gallery-heading';
  heading.innerHTML = `<span>${channels.length.toLocaleString('pt-BR')} DISPONÍVEIS</span><strong>Escolha um canal</strong>`;
  availableGallery.appendChild(heading);

  const grid = document.createElement('div');
  grid.className = 'gallery-grid';
  channels.forEach(channel => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'gallery-card';
    card.title = channel.name;
    const image = document.createElement('span');
    image.className = 'gallery-card-image';
    if (channel.logo) image.style.backgroundImage = `url("${channel.logo.replace(/"/g, '%22')}")`;
    else image.textContent = channel.name.slice(0, 1).toUpperCase();
    const label = document.createElement('span');
    label.className = 'gallery-card-label';
    label.textContent = channel.name;
    card.append(image, label);
    card.addEventListener('click', () => selectChannel(channel));
    grid.appendChild(card);
  });
  availableGallery.appendChild(grid);
}

function selectChannel(channel) {
  currentPlayingChannel = channel;
  if (videoContainer) videoContainer.classList.remove('mobile-mini-player');
  updateNowPlaying();
  updateHeroInfo();
  updateFavoriteButton();
  if (videoContainer) videoContainer.classList.remove('browse-mode');
  closeMobileChannelModal();
  renderMobileShellCards(currentChannelPool.length ? currentChannelPool : allChannels);
  document.querySelectorAll('.channel-item').forEach(item => {
    item.classList.toggle('active', decodeURIComponent(item.dataset.url) === channel.url);
  });
  playStream(channel.url);
}

function mobileCategoryLabel() {
  return ({
    'ao-vivo': 'TV ao vivo', filmes: 'Filmes', series: 'Séries',
    esportes: 'Esportes', favoritos: 'Favoritos', adultos: 'Adultos +18',
  })[currentCategory] || 'Canais';
}

async function openMobileChannelModal() {
  if (!mobileChannelModal) return;
  mobileChannelModal.classList.add('show');
  mobileChannelModal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('mobile-channel-modal-open');
  if (!catalogGroups[currentCategory] && currentCategory !== 'favoritos') await loadGroups(currentCategory);
  renderMobileGroups(catalogGroups[currentCategory] || []);
}

function closeMobileChannelModal() {
  if (!mobileChannelModal) return;
  mobileChannelModal.classList.remove('show');
  mobileChannelModal.setAttribute('aria-hidden', 'true');
  document.body.classList.remove('mobile-channel-modal-open');
}

function renderMobileSearch(query) {
  if (!mobileChannelModal || window.innerWidth > 600 || !query.trim()) return;
  const normalizedQuery = query.trim().toLowerCase();
  const matches = (currentChannelPool.length ? currentChannelPool : allChannels)
    .filter(channel => `${channel.name} ${channel.group}`.toLowerCase().includes(normalizedQuery))
    .slice(0, 40);
  mobileChannelModal.classList.add('show');
  mobileChannelModal.setAttribute('aria-hidden', 'false');
  document.body.classList.add('mobile-channel-modal-open');
  renderMobileChannels(matches);
  mobileChannelTitle.textContent = 'Resultados da busca';
  mobileChannelSubtitle.textContent = `${matches.length} encontrados`;
}

function toggleMobileMiniPlayer(forceMini = null) {
  if (!videoContainer || window.innerWidth > 600 || !currentPlayingChannel) return;
  const shouldMinimize = forceMini === null ? !videoContainer.classList.contains('mobile-mini-player') : forceMini;
  videoContainer.classList.toggle('mobile-mini-player', shouldMinimize);
  if (mobileMinimizeBtn) mobileMinimizeBtn.innerHTML = shouldMinimize ? '<i class="fas fa-expand-alt"></i>' : '<i class="fas fa-compress-alt"></i>';
}

function selectRelativeChannel(direction) {
  if (!currentPlayingChannel || !currentChannelPool.length) return;
  const index = currentChannelPool.findIndex(channel => channel.url === currentPlayingChannel.url);
  if (index < 0) return;
  selectChannel(currentChannelPool[(index + direction + currentChannelPool.length) % currentChannelPool.length]);
}

function activateMobileShell() {
  if (window.innerWidth > 600 || !mobileAppShell || !mobileHomeHero || !videoContainer) return;
  mobileAppShell.hidden = false;
  if (videoContainer.parentElement !== mobileHomeHero) mobileHomeHero.appendChild(videoContainer);
}

function renderMobileShellGroups(groups) {
  if (!mobileHomeGroups || window.innerWidth > 600) return;
  if (!groups.length) {
    mobileHomeGroups.innerHTML = '<p class="mobile-shell-empty">Carregando grupos…</p>';
    return;
  }
  mobileHomeGroups.innerHTML = groups.slice(0, 8).map(group => `
    <button type="button" class="mobile-home-group" data-home-group-id="${group.id}" data-home-content-type="${group.content_type || currentCategory}">
      <strong>${group.name}</strong><small>${group.count} itens</small>
    </button>`).join('');
  mobileHomeGroups.querySelectorAll('[data-home-group-id]').forEach(button => {
    button.addEventListener('click', () => loadGroup(button.dataset.homeGroupId, button.dataset.homeContentType));
  });
}

function renderMobileShellCards(channels) {
  if (!mobileHomeCards || window.innerWidth > 600) return;
  const source = channels.length ? channels.slice(0, 12) : getFavoriteChannels().slice(0, 12);
  if (mobileHomeCardsTitle) mobileHomeCardsTitle.textContent = getFavoriteChannels().length ? 'Seus favoritos' : 'Canais para você';
  if (!source.length) {
    mobileHomeCards.innerHTML = '<p class="mobile-shell-empty">Escolha um grupo para ver os canais.</p>';
    return;
  }
  mobileHomeCards.replaceChildren();
  const fragment = document.createDocumentFragment();
  source.forEach(channel => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'mobile-home-card';
    const cover = document.createElement('span');
    cover.className = 'mobile-home-card-cover';
    if (channel.logo) cover.style.backgroundImage = `url("${channel.logo.replace(/"/g, '%22')}")`;
    else cover.innerHTML = '<i class="fas fa-tv"></i>';
    const title = document.createElement('strong');
    title.textContent = channel.name;
    card.append(cover, title);
    card.addEventListener('click', () => selectChannel(channel));
    fragment.appendChild(card);
  });
  mobileHomeCards.appendChild(fragment);
}

function renderMobileGroups(groups) {
  if (!mobileChannelGroups || !mobileChannelList) return;
  mobileChannelTitle.textContent = 'Escolha um grupo';
  mobileChannelSubtitle.textContent = mobileCategoryLabel();
  mobileChannelGroups.hidden = false;
  mobileChannelList.hidden = true;
  if (mobileChannelBack) mobileChannelBack.hidden = true;
  if (!groups.length) {
    mobileChannelGroups.innerHTML = '<p class="mobile-channel-empty">Nenhum grupo disponível.</p>';
    return;
  }
  mobileChannelGroups.innerHTML = groups.map(group => `
    <button type="button" class="mobile-group-card" data-mobile-group-id="${group.id}" data-mobile-content-type="${group.content_type || currentCategory}">
      <span>${group.name}</span><small>${group.count} itens</small><i class="fas fa-chevron-right"></i>
    </button>`).join('');
  mobileChannelGroups.querySelectorAll('[data-mobile-group-id]').forEach(button => {
    button.addEventListener('click', () => loadGroup(button.dataset.mobileGroupId, button.dataset.mobileContentType));
  });
}

function renderMobileChannels(channels) {
  if (!mobileChannelGroups || !mobileChannelList) return;
  const activeGroup = (catalogGroups[currentCategory] || []).find(group => group.id === selectedGroupId);
  mobileChannelTitle.textContent = activeGroup?.name || 'Escolha um canal';
  mobileChannelSubtitle.textContent = `${channels.length.toLocaleString('pt-BR')} disponíveis`;
  mobileChannelGroups.hidden = true;
  mobileChannelList.hidden = false;
  if (mobileChannelBack) mobileChannelBack.hidden = false;
  mobileChannelList.replaceChildren();
  if (!channels.length) {
    mobileChannelList.innerHTML = '<p class="mobile-channel-empty">Nenhum canal neste grupo.</p>';
    return;
  }
  const fragment = document.createDocumentFragment();
  channels.forEach(channel => {
    const button = document.createElement('button');
    button.type = 'button';
    button.className = 'mobile-channel-card';
    const artwork = document.createElement('span');
    artwork.className = 'mobile-channel-artwork';
    if (channel.logo) artwork.style.backgroundImage = `url("${channel.logo.replace(/"/g, '%22')}")`;
    else artwork.textContent = channel.name.slice(0, 1).toUpperCase();
    const name = document.createElement('strong');
    name.textContent = channel.name;
    button.append(artwork, name);
    button.addEventListener('click', () => selectChannel(channel));
    fragment.appendChild(button);
  });
  mobileChannelList.appendChild(fragment);
}

function openVisualCatalog(groupId) {
  if (!catalogModal || !catalogCards) return;
  const group = (catalogGroups[currentCategory] || []).find(item => item.id === groupId);
  catalogVisibleCount = Math.min(60, allChannels.length);
  catalogModalTitle.textContent = group?.name || 'Disponíveis';
  catalogModalSubtitle.textContent = `${allChannels.length.toLocaleString('pt-BR')} títulos neste grupo`;
  renderVisualCatalogCards();
  catalogModal.classList.add('show');
  catalogModal.setAttribute('aria-hidden', 'false');
}

function renderVisualCatalogCards() {
  if (!catalogCards) return;
  catalogCards.replaceChildren();
  const fragment = document.createDocumentFragment();
  allChannels.slice(0, catalogVisibleCount).forEach(channel => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'catalog-card';
    card.title = channel.name;

    const poster = document.createElement('span');
    poster.className = 'catalog-poster';
    if (channel.logo) {
      poster.style.backgroundImage = `url("${channel.logo.replace(/"/g, '%22')}")`;
    } else {
      poster.classList.add('no-poster');
      poster.textContent = channel.name.slice(0, 1).toUpperCase();
    }

    const details = document.createElement('span');
    details.className = 'catalog-card-details';
    const title = document.createElement('strong');
    title.textContent = channel.name;
    const meta = document.createElement('small');
    meta.textContent = channel.group;
    details.append(title, meta);
    card.append(poster, details);
    card.addEventListener('click', () => {
      currentPlayingChannel = channel;
      updateNowPlaying();
      updateHeroInfo();
      updateFavoriteButton();
      closeModal('catalog-modal');
      showPlayerScreen();
      playStream(channel.url);
    });
    fragment.appendChild(card);
  });
  catalogCards.appendChild(fragment);
  if (catalogMoreBtn) {
    catalogMoreBtn.style.display = catalogVisibleCount < allChannels.length ? 'block' : 'none';
  }
}

async function loadPlaylistFromM3U() {
  showMessage('O catálogo agora é carregado diretamente do Supabase.', 'info');
}

// ============================================
// M3U PLAYLIST PARSER
// ============================================

function parseM3UPlaylist(text) {
  const lines = text.split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const channels = [];

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    
    if (!line.startsWith('#EXTINF')) continue;

    const extinf = line.substring(8).trim();
    let name = extinf;
    let logo = '';
    let group = '';

    if (extinf.includes(',')) {
      const meta = extinf.split(',')[0];
      name = extinf.split(',')[1]?.trim() || name;
      const logoMatch = meta.match(/tvg-logo="([^"]*)"/);
      if (logoMatch) logo = logoMatch[1];
      const groupMatch = meta.match(/group-title="([^"]*)"/);
      if (groupMatch) group = groupMatch[1];
    }

    const url = (lines[i + 1] || '').trim();
    if (!url || url.startsWith('#')) continue;

    const channelGroup = group || 'Outros';
    const channelGroupPath = parseGroupPath(channelGroup);
    channels.push({
      name: name.trim(),
      url,
      logo,
      group: channelGroup,
      groupPath: channelGroupPath,
      groupPathString: channelGroupPath.join(' / ') || 'Outros',
      type: classifyChannelType(name, group, url),
      raw: extinf,
    });
  }

  return channels;
}

function classifyChannelType(name, group, url) {
  const text = `${group} ${name} ${url}`.toLowerCase();
  if (text.includes('filme') || text.includes('movie') || text.includes('cinema') || text.includes('film') || text.includes('flix')) {
    return 'filmes';
  }
  if (text.includes('serie') || text.includes('series') || text.includes('série') || text.includes('tv show') || text.includes('episódio') || text.includes('episode')) {
    return 'series';
  }
  if (text.includes('esporte') || text.includes('sports') || text.includes('live sports') || text.includes('futebol') || text.includes('sport')) {
    return 'esportes';
  }
  return 'ao-vivo';
}

function classifyChannels() {
  channelsByCategory = {
    'ao-vivo': [],
    filmes: [],
    series: [],
    esportes: [],
    favoritos: [],
  };

  allChannels.forEach(channel => {
    channelsByCategory[channel.type].push(channel);
  });
}

function parseGroupPath(group) {
  return (group || 'Outros')
    .split(/[\\/|]/)
    .map(segment => segment.trim())
    .filter(Boolean);
}

function addChannelToGroupTree(tree, path) {
  let node = tree;
  node.count += 1;

  path.forEach(segment => {
    const key = segment || 'Outros';
    if (!node.children[key]) {
      node.children[key] = {
        name: key,
        path: [...node.path, key],
        children: {},
        count: 0,
      };
    }
    node = node.children[key];
    node.count += 1;
  });
}

function buildCategoryGroupTrees() {
  const categories = ['ao-vivo', 'filmes', 'series', 'esportes', 'favoritos'];
  const trees = {};

  categories.forEach(category => {
    trees[category] = {
      name: 'root',
      path: [],
      children: {},
      count: 0,
    };
  });

  allChannels.forEach(channel => {
    const tree = trees[channel.type] || trees['ao-vivo'];
    addChannelToGroupTree(tree, channel.groupPath || parseGroupPath(channel.group));
    if (favorites.includes(channel.url)) {
      addChannelToGroupTree(trees.favoritos, channel.groupPath || parseGroupPath(channel.group));
    }
  });

  return trees;
}

function getGroupNode(tree, path) {
  let node = tree;
  for (const segment of path) {
    node = node.children[segment];
    if (!node) return null;
  }
  return node;
}

function channelMatchesCurrentGroup(channel) {
  if (!currentGroupPath.length) return true;
  const path = channel.groupPath || parseGroupPath(channel.group);
  if (path.length < currentGroupPath.length) return false;
  return currentGroupPath.every((segment, index) => path[index]?.toLowerCase() === segment.toLowerCase());
}

function applyCurrentCategory() {
  if (!playlistLoaded || !currentCategory) return;

  let baseChannels = currentCategory === 'favoritos'
    ? getFavoriteChannels()
    : channelsByCategory[currentCategory] || [];

  const filteredByGroup = baseChannels.filter(channelMatchesCurrentGroup);
  currentChannelPool = filteredByGroup;
  displayedChannelsCount = Math.min(channelBatchSize, currentChannelPool.length);
  currentChannels = currentChannelPool.slice(0, displayedChannelsCount);
  channelCount.textContent = currentChannelPool.length;
  renderChannels(currentChannels);
  updateLoadMoreButton(currentChannelPool.length);
  renderGroupTree(currentCategory);

  if (currentChannels.length > 0 && window.innerWidth > 600) {
    playStream(currentChannels[0].url);
  }
}

function updateLoadMoreButton(totalCount) {
  if (!loadMoreBtn) return;
  if (displayedChannelsCount < totalCount) {
    loadMoreBtn.style.display = 'block';
  } else {
    loadMoreBtn.style.display = 'none';
  }
}

function renderGroupTree(category) {
  const container = document.getElementById('group-tree');
  if (!container || !playlistLoaded) return;

  const tree = groupTrees[category] || groupTrees['ao-vivo'];
  if (!tree) {
    container.innerHTML = '<p style="padding: 16px; color: var(--text-muted);">Sem grupos disponíveis.</p>';
    return;
  }

  const breadcrumbHtml = buildGroupBreadcrumbHtml();
  const treeHtml = renderTreeNodeRecursive(tree, currentGroupPath, 0);

  container.innerHTML = `
    ${breadcrumbHtml}
    <div class="group-items">${treeHtml}</div>
  `;
  
  attachGroupTreeEventListeners();
}

function renderTreeNodeRecursive(node, currentPath, depth) {
  const children = Object.values(node.children)
    .sort((a, b) => a.name.localeCompare(b.name, 'pt-BR', { sensitivity: 'base' }));

  if (children.length === 0) return '';

  return children.map(child => {
    const childHasChildren = Object.keys(child.children).length > 0;
    const isActive = currentPath.length === depth + 1 && currentPath[depth] === child.name;
    const pathKey = child.path.join('||');
    const hasGrandchildren = childHasChildren && depth < 2;

    return `
      <div class="group-item-wrapper" data-path="${pathKey}">
        <button class="group-item ${childHasChildren ? 'has-children' : 'leaf'} ${isActive ? 'active' : ''}" 
                data-path="${pathKey}" 
                data-depth="${depth}">
          <div class="group-item-label">
            <span class="group-item-name">${child.name}</span>
            <span class="group-item-count">${child.count} item${child.count !== 1 ? 'ns' : ''}</span>
          </div>
          ${childHasChildren ? '<span class="group-item-chevron">▶</span>' : ''}
        </button>
        ${hasGrandchildren && isActive ? `
          <div class="group-submenu" style="margin-top: 4px; margin-left: 8px;">
            ${renderTreeNodeRecursive(child, currentPath.slice(depth + 1), depth + 1)}
          </div>
        ` : ''}
      </div>
    `;
  }).join('');
}

function buildGroupBreadcrumbHtml() {
  if (!currentGroupPath.length) {
    return `
      <div class="breadcrumb">
        <button class="breadcrumb-item" data-path="">📂 Todos os grupos</button>
      </div>
    `;
  }

  const segments = [
    { label: '📂 Todos', path: [] },
    ...currentGroupPath.map((segment, index) => ({
      label: segment,
      path: currentGroupPath.slice(0, index + 1),
    })),
  ];

  return `
    <div class="breadcrumb">
      ${segments.map((segment, idx) => `
        <button class="breadcrumb-item" data-path="${segment.path.join('||')}">
          ${segment.label}
        </button>
        ${idx < segments.length - 1 ? '<span class="breadcrumb-separator">›</span>' : ''}
      `).join('')}
    </div>
  `;
}

function attachGroupTreeEventListeners() {
  // Breadcrumb navigation
  document.querySelectorAll('.breadcrumb-item').forEach(button => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      const path = button.dataset.path ? button.dataset.path.split('||').filter(Boolean) : [];
      currentGroupPath = path;
      applyCurrentCategory();
      populateContentRows();
    });
  });

  // Group item selection and expand
  document.querySelectorAll('.group-item').forEach(button => {
    button.addEventListener('click', (event) => {
      event.preventDefault();
      const path = button.dataset.path ? button.dataset.path.split('||') : [];
      const hasChildren = button.classList.contains('has-children');

      if (hasChildren && event.target.closest('.group-item-chevron')) {
        // Toggle expand
        button.classList.toggle('expanded');
      } else {
        // Navigate to group
        currentGroupPath = path;
        applyCurrentCategory();
        populateContentRows();
      }
    });
  });
}

function loadMoreChannels() {
  const nextCount = Math.min(currentChannelPool.length, displayedChannelsCount + channelBatchSize);
  currentChannels = currentChannelPool.slice(0, nextCount);
  displayedChannelsCount = nextCount;
  renderChannels(currentChannels);
  updateLoadMoreButton(currentChannelPool.length);
}

// ============================================
// CHANNEL RENDERING
// ============================================

function renderChannels(channels) {
  if (channels.length === 0) {
    channelList.innerHTML = '<p style="padding: 16px; text-align: center; color: #6b7280;">Nenhum canal encontrado</p>';
    return;
  }

  channelList.innerHTML = channels.map(channel => `
    <button class="channel-item" data-url="${encodeURIComponent(channel.url)}" title="${channel.name}">
      <strong>${channel.name}</strong>
      <span>${channel.groupPathString}</span>
    </button>
  `).join('');

  // Add event listeners to channel items
  document.querySelectorAll('.channel-item').forEach(button => {
    button.addEventListener('click', () => {
      const streamUrl = decodeURIComponent(button.dataset.url);
      const channel = channels.find(item => item.url === streamUrl) || null;
      if (!channel) return;
      selectChannel(channel);

      // Mark as active
      document.querySelectorAll('.channel-item').forEach(item => item.classList.remove('active'));
      button.classList.add('active');
      updateFavoriteButton();
    });
  });
}

function renderContentCards(channels, container, max = 8) {
  if (!container) return;
  if (!channels.length) {
    container.innerHTML = '<p style="color: var(--text-muted); padding: 16px;">Nenhum item disponível.</p>';
    return;
  }

  container.innerHTML = channels.slice(0, max).map(channel => `
    <div class="content-card" data-url="${encodeURIComponent(channel.url)}">
      <div class="card-image" ${channel.logo ? `style="background-image: url('${channel.logo}');"` : ''}>
        ${channel.logo ? '' : '<i class="fas fa-tv"></i>'}
      </div>
      <div class="card-content">
        <h3 class="card-title">${channel.name}</h3>
        <p class="card-meta">${channel.group}</p>
      </div>
    </div>
  `).join('');

  container.querySelectorAll('.content-card').forEach(card => {
    card.addEventListener('click', () => {
      const streamUrl = decodeURIComponent(card.dataset.url);
      const channel = allChannels.find(item => item.url === streamUrl) || null;
      if (!channel) return;
      selectChannel(channel);
      updateFavoriteButton();
    });
  });
}

function populateContentRows() {
  if (!playlistLoaded) return;

  const activeCategory = currentCategory || 'ao-vivo';
  const categoryChannels = activeCategory === 'favoritos'
    ? getFavoriteChannels()
    : channelsByCategory[activeCategory] || allChannels;

  const filteredByGroup = categoryChannels.filter(channelMatchesCurrentGroup);

  renderContentCards(filteredByGroup, continuaGrid);
  renderContentCards(filteredByGroup, lancamentosGrid);
  renderContentCards(filteredByGroup, maisVistosGrid);
  renderContentCards(getFavoriteChannels().filter(channelMatchesCurrentGroup), minhaListaGrid);
  renderContentCards(filteredByGroup.slice(0, 6), mainGrid, 6);
}

function getFavoriteChannels() {
  return allChannels.filter(channel => favorites.includes(channel.url));
}

function isFavorite(channel) {
  if (!channel) return false;
  return favorites.includes(channel.url);
}

function toggleFavorite() {
  if (!currentPlayingChannel) {
    showMessage('Nenhum canal sendo reproduzido.', 'error');
    return;
  }

  const index = favorites.indexOf(currentPlayingChannel.url);
  if (index >= 0) {
    favorites.splice(index, 1);
    showMessage('Removido dos favoritos', 'info');
  } else {
    favorites.push(currentPlayingChannel.url);
    showMessage('Adicionado aos favoritos', 'success');
  }

  localStorage.setItem('fodao-favorites', JSON.stringify(favorites));
  groupTrees = buildCategoryGroupTrees();
  populateContentRows();
  updateFavoriteButton();
  updateHeroInfo();
}

function updateHeroInfo() {
  if (heroCurrentChannel) {
    heroCurrentChannel.textContent = currentPlayingChannel ? currentPlayingChannel.name : 'Nenhum canal selecionado';
  }
  if (heroTotalChannels) {
    heroTotalChannels.textContent = allChannels.length.toString();
  }
  if (heroFavoriteCount) {
    heroFavoriteCount.textContent = getFavoriteChannels().length.toString();
  }
}

function updateNowPlaying(channel = currentPlayingChannel) {
  if (playerNowTitle) {
    playerNowTitle.textContent = channel ? channel.name : 'Escolha um canal para começar';
  }
}

function updateFavoriteButton() {
  const favoritesBtn = document.getElementById('favorites-btn');
  if (!favoritesBtn) return;
  if (isFavorite(currentPlayingChannel)) {
    favoritesBtn.classList.add('active');
    favoritesBtn.innerHTML = '<i class="fas fa-heart"></i>';
  } else {
    favoritesBtn.classList.remove('active');
    favoritesBtn.innerHTML = '<i class="fas fa-heart"></i>';
  }
}

// ============================================
// STREAM PLAYBACK
// ============================================

function getProxyUrl(url) {
  return url;
}

async function playStream(url) {
  const requestId = ++playbackRequest;
  const targetUrl = getProxyUrl(url);

  // Destroy existing HLS instance
  if (hls) {
    hls.destroy();
    hls = null;
  }

  videoPlayer.pause();
  videoPlayer.removeAttribute('src');
  videoPlayer.load();

  // Do not pre-download the playlist here. Besides doubling network traffic, an
  // older asynchronous probe could replace a newer channel selection.
  const isHls = /\.m3u8(?:$|[?#])/i.test(url);

  if (!isHls) {
    videoPlayer.src = targetUrl;
    videoPlayer.play().catch(() => showMessage('Clique no player para iniciar a reprodução', 'info'));
    return;
  }

  if (Hls.isSupported()) {
    hls = new Hls({
      debug: false,
      enableWorker: true,
    });

    hls.loadSource(targetUrl);
    hls.attachMedia(videoPlayer);

    hls.on(Hls.Events.MANIFEST_PARSED, () => {
      if (requestId !== playbackRequest) return;
      videoPlayer.play().catch(err => {
        console.log('Autoplay failed:', err);
        showMessage('Clique no player para iniciar a reprodução', 'info');
      });
    });

    hls.on(Hls.Events.ERROR, (event, data) => {
      if (requestId !== playbackRequest) return;
      console.error('HLS Error:', data);
      if (data.fatal) {
        switch (data.type) {
          case Hls.ErrorTypes.NETWORK_ERROR:
            showMessage('Erro de conexão ao carregar o canal. Tente outro stream ou verifique o provedor.', 'error');
            break;
          case Hls.ErrorTypes.MEDIA_ERROR:
            hls.recoverMediaError();
            break;
          default:
            showMessage('Não foi possível reproduzir este canal.', 'error');
        }
      }
    });
  } else if (videoPlayer.canPlayType('application/vnd.apple.mpegurl')) {
    // Native HLS support (Safari)
    videoPlayer.src = targetUrl;
    videoPlayer.addEventListener('loadedmetadata', () => {
      videoPlayer.play().catch(err => {
        console.log('Autoplay failed:', err);
      });
    });
  } else {
    showMessage('Seu navegador não suporta HLS. Use Chrome, Firefox ou Safari.', 'error');
  }
}

// ============================================
// SEARCH & FILTERING
// ============================================

function filterChannels() {
  if (!playlistLoaded || !currentCategory) return;

  const query = searchInput.value.toLowerCase().trim();
  const baseChannels = channelsByCategory[currentCategory] || allChannels;
  const filteredBase = baseChannels.filter(channelMatchesCurrentGroup);

  if (query === '') {
    currentChannelPool = filteredBase;
  } else {
    currentChannelPool = filteredBase.filter(channel => 
      channel.name.toLowerCase().includes(query) ||
      channel.groupPathString.toLowerCase().includes(query)
    );
  }

  displayedChannelsCount = Math.min(channelBatchSize, currentChannelPool.length);
  currentChannels = currentChannelPool.slice(0, displayedChannelsCount);
  channelCount.textContent = currentChannelPool.length;
  renderChannels(currentChannels);
  updateLoadMoreButton(currentChannelPool.length);

  if (currentChannels.length > 0) {
    playStream(currentChannels[0].url);
  }
}

// ============================================
// NAVIGATION & CATEGORIES
// ============================================

function openCategory(category, bypassAdultCheck = false) {
  if (category === 'adultos' && !adultAccessGranted && !bypassAdultCheck) {
    requestAdultAccess();
    return;
  }
  currentCategory = category;
  currentGroupPath = [];
  selectedGroupId = '';
  if (category !== 'favoritos') allChannels = [];
  currentPlayingChannel = null;
  updateNowPlaying();

  // Update active nav item
  navItems.forEach(item => {
    if (item.dataset.category === category) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // Update top navigation active state
  document.querySelectorAll('.top-nav-item').forEach(item => {
    if (item.dataset.category === category) {
      item.classList.add('active');
    } else {
      item.classList.remove('active');
    }
  });

  // Update section title
  const titles = {
    'ao-vivo': 'TV AO VIVO',
    'filmes': 'FILMES',
    'series': 'SÉRIES',
    'esportes': 'ESPORTES',
    'favoritos': 'FAVORITOS',
    'adultos': 'ADULTOS +18',
  };

  sectionTitle.textContent = titles[category] || 'Conteúdo';

  // Change row headings on category selection
  const rowTitles = {
    'ao-vivo': ['TV AO VIVO', 'MAIS VISTOS', 'RECOMENDADOS'],
    'filmes': ['FILMES', 'LANÇAMENTOS', 'RECOMENDADOS'],
    'series': ['SÉRIES', 'LANÇAMENTOS', 'RECOMENDADOS'],
    'esportes': ['ESPORTES', 'LANÇAMENTOS', 'RECOMENDADOS'],
    'favoritos': ['FAVORITOS', 'RECOMENDADOS', 'RECOMENDADOS'],
    'adultos': ['ADULTOS +18', 'LANÇAMENTOS', 'RECOMENDADOS'],
  };

  const titlesToUse = rowTitles[category] || ['Conteúdo', 'Conteúdo', 'Conteúdo'];
  const continuaSection = document.getElementById('continua-assistindo');
  const lancamentosSection = document.getElementById('lancamentos');
  const maisVistosSection = document.getElementById('mais-vistos');

  const continuaTitle = continuaSection?.querySelector('h2');
  const lancamentosTitle = lancamentosSection?.querySelector('h2');
  const maisVistosTitle = maisVistosSection?.querySelector('h2');

  if (continuaTitle) continuaTitle.textContent = titlesToUse[0];
  if (lancamentosTitle) lancamentosTitle.textContent = titlesToUse[1];
  if (maisVistosTitle) maisVistosTitle.textContent = titlesToUse[2];

  // Show player section
  showPlayerScreen();

  channelList.innerHTML = '<p style="padding:16px;text-align:center;color:#6b7280;">Escolha um grupo para carregar seus canais.</p>';
  channelCount.textContent = '0';
  if (!playlistLoaded) {
    loadPlaylist().then(() => loadGroups(category));
  } else {
    loadGroups(category);
  }

  // Close sidebar on mobile
  if (window.innerWidth <= 768) {
    sidebar.classList.remove('show');
  }
}

function classifyImportedCategory(groupName, channelName) {
  const text = `${groupName} ${channelName}`.toLocaleLowerCase('pt-BR');
  if (/(adult|adulto|\+18|hentai)/.test(text)) return 'adultos';
  if (/(esporte|sport|futebol|nba|ufc|premier league|copa)/.test(text)) return 'esportes';
  if (/(s[eé]rie|series|temporada|episode|epis[oó]dio)/.test(text)) return 'series';
  if (/(filme|movie|cinema|netflix|amazon|disney)/.test(text)) return 'filmes';
  return 'ao-vivo';
}

function resolveUrl(url, baseUrl) {
  try {
    return baseUrl ? new URL(url, baseUrl).href : url;
  } catch {
    return url;
  }
}

function extractM3uEntries(text) {
  const lines = text.replace(/^\uFEFF/, '').split(/\r?\n/).map(line => line.trim()).filter(Boolean);
  const entries = [];
  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.startsWith('#EXTINF')) continue;

    const commaIndex = line.lastIndexOf(',');
    const metadata = commaIndex >= 0 ? line.slice(0, commaIndex) : line;
    const name = commaIndex >= 0 ? line.slice(commaIndex + 1).trim() : 'Sem nome';
    const attribute = key => metadata.match(new RegExp(`${key}="([^"]*)"`, 'i'))?.[1] || '';
    let url = '';

    for (let j = i + 1; j < lines.length; j += 1) {
      if (!lines[j] || lines[j].startsWith('#')) continue;
      url = lines[j];
      break;
    }

    if (!url) continue;

    entries.push({
      name: name || 'Sem nome',
      group: attribute('group-title') || 'Outros',
      logo: attribute('tvg-logo'),
      tvgId: attribute('tvg-id'),
      url,
    });
  }
  return entries;
}

function isNestedPlaylistUrl(url) {
  return /\.(m3u|m3u8)(?:\?.*)?$/i.test(url);
}

async function fetchM3uText(url) {
  const fetchRemote = async (requestUrl) => {
    const response = await fetch(requestUrl, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`Falha ao baixar M3U: ${response.status} ${response.statusText}`);
    }
    return response.text();
  };

  try {
    return await fetchRemote(url);
  } catch (firstError) {
    console.warn('Falha ao buscar diretamente. Tentando proxy backend:', firstError);
    const proxyUrl = `/api/proxy-m3u?url=${encodeURIComponent(url)}`;
    const response = await fetch(proxyUrl, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error(`Falha ao baixar via proxy: ${response.status} ${response.statusText}`);
    }
    return response.text();
  }
}

async function parseM3uTextRecursive(text, baseUrl = '') {
  const entries = [];
  const queue = [{ text, baseUrl }];
  const visited = new Set();

  while (queue.length && entries.length < MAX_CATALOG_ENTRIES) {
    const { text: currentText, baseUrl: currentBase } = queue.shift();
    const parsed = extractM3uEntries(currentText);

    for (const entry of parsed) {
      const resolvedUrl = resolveUrl(entry.url, currentBase || window.location.href);
      if (isNestedPlaylistUrl(resolvedUrl) && !visited.has(resolvedUrl) && visited.size < MAX_NESTED_PLAYLIST_FETCH) {
        visited.add(resolvedUrl);
        try {
          const nestedText = await fetchM3uText(resolvedUrl);
          queue.push({ text: nestedText, baseUrl: resolvedUrl });
        } catch (error) {
          console.warn('Não foi possível carregar lista aninhada:', resolvedUrl, error);
        }
        continue;
      }
      entries.push({ ...entry, url: resolvedUrl });
    }
  }

  return entries;
}

async function parseM3uForImport(text, baseUrl = '') {
  const parsedEntries = await parseM3uTextRecursive(text, baseUrl);
  const groups = new Map();
  const streams = new Map();

  for (const entry of parsedEntries) {
    if (!entry.url) continue;
    const categorySlug = classifyImportedCategory(entry.group, entry.name);
    const groupName = entry.group.trim() || 'Outros';
    const groupKey = `${categorySlug}\u0000${groupName}`;
    if (!groups.has(groupKey)) {
      groups.set(groupKey, { category_slug: categorySlug, name: groupName, sort_order: groups.size });
    }
    const streamKey = `${groupKey}\u0000${entry.name}`;
    if (!streams.has(streamKey)) {
      streams.set(streamKey, {
        category_slug: categorySlug,
        group_name: groupName,
        name: entry.name,
        stream_url: entry.url,
        logo_url: entry.logo,
        stream_type: categorySlug,
        metadata: { tvg_id: entry.tvgId || null, source_group: groupName },
      });
    }
  }

  return { groups: [...groups.values()], streams: [...streams.values()] };
}

async function checkForAppUpdate() {
  try {
    const response = await fetch(`${UPDATE_CHECK_URL}?_=${Date.now()}`, { cache: 'no-store' });
    if (!response.ok) return;
    const remote = await response.json();
    if (remote?.version && remote.version !== APP_VERSION) {
      showMessage('Nova versão do app disponível. Atualizando...', 'info');
      if ('serviceWorker' in navigator) {
        const reg = await navigator.serviceWorker.getRegistration();
        if (reg) await reg.update();
      }
      setTimeout(() => window.location.reload(), 1200);
    }
  } catch (error) {
    console.warn('Falha ao verificar atualização do app:', error);
  }
}

function startPeriodicUpdateCheck() {
  setInterval(checkForAppUpdate, UPDATE_CHECK_INTERVAL);
  window.addEventListener('focus', () => {
    if (document.visibilityState === 'visible') {
      checkForAppUpdate();
    }
  });
}

function openAdminCatalogModal() {
  if (currentProfile?.role !== 'admin' || !adminCatalogModal) return;
  adminCatalogModal.classList.add('show');
  adminCatalogModal.setAttribute('aria-hidden', 'false');
}

async function importAdminCatalog() {
  if (currentProfile?.role !== 'admin' || !pendingAdminCatalog) return;
  adminImportBtn.disabled = true;
  adminImportBtn.textContent = 'ATUALIZANDO...';
  try {
    const { data, error } = await supabase.rpc('replace_catalog', { catalog: pendingAdminCatalog });
    if (error) throw error;
    catalogGroups = {};
    categoryRecords = {};
    allChannels = [];
    selectedGroupId = '';
    await loadPlaylist();
    adminM3uSummary.textContent = `Catálogo atualizado: ${data.streams} links em ${data.groups} grupos.`;
    showMessage('Catálogo atualizado para todos os usuários.', 'success');
    closeModal('admin-catalog-modal');
  } catch (error) {
    showMessage(`Não foi possível atualizar o catálogo: ${error.message}`, 'error');
  } finally {
    adminImportBtn.disabled = false;
    adminImportBtn.textContent = 'ATUALIZAR CATÁLOGO';
  }
}

// ============================================
// MODALS
// ============================================

function openModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.add('show');
  }
}

function closeModal(modalId) {
  const modal = document.getElementById(modalId);
  if (modal) {
    modal.classList.remove('show');
    modal.setAttribute('aria-hidden', 'true');
  }
}

function requestAdultAccess() {
  if (!adultAccessModal || !adultAccessPin) return;
  adultAccessCopy.textContent = 'Digite o PIN de acesso para abrir conteúdo adulto.';
  adultAccessError.textContent = '';
  adultAccessPin.value = '';
  adultAccessModal.classList.add('show');
  adultAccessModal.setAttribute('aria-hidden', 'false');
  setTimeout(() => adultAccessPin.focus(), 0);
}

function submitAdultAccess(event) {
  event.preventDefault();
  const pin = adultAccessPin.value.trim();
  if (!/^\d{4,8}$/.test(pin)) {
    adultAccessError.textContent = 'Use um PIN numérico de 4 a 8 dígitos.';
    return;
  }
  if (pin !== ADULT_ACCESS_PIN) {
    adultAccessError.textContent = 'PIN incorreto.';
    adultAccessPin.select();
    return;
  }
  adultAccessGranted = true;
  sessionStorage.setItem('fodao-adult-access', 'true');
  closeModal('adult-access-modal');
  openCategory('adultos', true);
}

closeModals.forEach(btn => {
  btn.addEventListener('click', () => {
    const modalId = btn.dataset.modal;
    closeModal(modalId);
  });
});

if (adultAccessForm) adultAccessForm.addEventListener('submit', submitAdultAccess);

// Close modal when clicking outside
document.querySelectorAll('.modal').forEach(modal => {
  modal.addEventListener('click', (e) => {
    if (e.target === modal) {
      modal.classList.remove('show');
    }
  });
});

// ============================================
// MESSAGE NOTIFICATIONS
// ============================================

function showMessage(text, type = 'info') {
  const message = document.createElement('div');
  message.className = `toast-message ${type}`;
  message.textContent = text;
  messageContainer.appendChild(message);

  // Auto-remove after 3 seconds
  setTimeout(() => {
    message.style.animation = 'slideOutRight 0.3s ease';
    setTimeout(() => message.remove(), 300);
  }, 3000);
}

// ============================================
// EVENT LISTENERS
// ============================================

function setupEventListeners() {
  if (mobileChannelsBtn) mobileChannelsBtn.addEventListener('click', openMobileChannelModal);
  if (mobileChannelClose) mobileChannelClose.addEventListener('click', closeMobileChannelModal);
  if (mobileChannelBack) mobileChannelBack.addEventListener('click', () => renderMobileGroups(catalogGroups[currentCategory] || []));
  if (mobileChannelModal) mobileChannelModal.addEventListener('click', event => {
    if (event.target === mobileChannelModal) closeMobileChannelModal();
  });
  if (adminBtn) adminBtn.addEventListener('click', event => {
    event.preventDefault();
    openAdminCatalogModal();
  });
  if (profileAdminBtn) profileAdminBtn.addEventListener('click', () => {
    closeModal('profile-modal');
    openAdminCatalogModal();
  });
  if (adminM3uFile) adminM3uFile.addEventListener('change', async () => {
    const file = adminM3uFile.files?.[0];
    pendingAdminCatalog = null;
    adminImportBtn.disabled = true;
    adminM3uSummary.textContent = 'Lendo arquivo...';
    if (!file) {
      adminM3uSummary.textContent = 'Nenhum arquivo selecionado.';
      return;
    }
    try {
      const catalog = await parseM3uForImport(await file.text());
      if (!catalog.streams.length) throw new Error('Nenhum link M3U válido foi encontrado.');
      pendingAdminCatalog = catalog;
      adminM3uSummary.textContent = `${file.name}: ${catalog.streams.length} links em ${catalog.groups.length} grupos. O catálogo atual será substituído.`;
      adminImportBtn.disabled = false;
    } catch (error) {
      adminM3uSummary.textContent = `Arquivo inválido: ${error.message}`;
    }
  });

  function parseMultipleUrls(rawValue) {
    return rawValue
      .split(/\r?\n|[;,]/)
      .map(url => url.trim())
      .filter(url => url.length > 0);
  }

  function mergeImportedCatalogs(catalogs) {
    const groups = new Map();
    const streams = new Map();

    catalogs.forEach(catalog => {
      catalog.groups.forEach(group => {
        const key = `${group.category_slug}\u0000${group.name}`;
        if (!groups.has(key)) groups.set(key, group);
      });
      catalog.streams.forEach(stream => {
        const key = `${stream.category_slug}\u0000${stream.group_name}\u0000${stream.name}\u0000${stream.stream_url}`;
        if (!streams.has(key)) streams.set(key, stream);
      });
    });

    return {
      groups: [...groups.values()],
      streams: [...streams.values()],
    };
  }

  if (adminLoadUrlBtn) adminLoadUrlBtn.addEventListener('click', async () => {
    const urls = parseMultipleUrls(adminM3uUrl?.value || '');
    if (!urls.length) {
      adminM3uSummary.textContent = 'Informe ao menos uma URL de M3U/M3U8.';
      return;
    }

    pendingAdminCatalog = null;
    adminImportBtn.disabled = true;
    adminM3uSummary.textContent = 'Carregando URLs...';

    const results = await Promise.allSettled(urls.map(async url => {
      const text = await fetchM3uText(url);
      return parseM3uForImport(text, url);
    }));

    const successes = results.filter(r => r.status === 'fulfilled').map(r => r.value);
    const failures = results
      .filter(r => r.status === 'rejected')
      .map(r => r.reason?.message || 'Erro desconhecido');

    if (!successes.length) {
      adminM3uSummary.textContent = `Falha ao carregar todas as URLs: ${failures.join('; ')}`;
      adminImportBtn.disabled = true;
      return;
    }

    const catalog = mergeImportedCatalogs(successes);
    pendingAdminCatalog = catalog;
    adminImportBtn.disabled = false;
    adminM3uSummary.textContent = `${successes.length} de ${urls.length} URLs carregadas. ${catalog.streams.length} links em ${catalog.groups.length} grupos. O catálogo atual será substituído.`;
    if (failures.length) {
      showMessage(`Algumas URLs falharam: ${failures.join('; ')}`, 'warning');
    }
  });

  if (adminImportBtn) adminImportBtn.addEventListener('click', importAdminCatalog);
  document.querySelectorAll('.logout').forEach(button => {
    button.addEventListener('click', async event => {
      event.preventDefault();
      await supabase?.auth.signOut();
      window.location.replace('index.html');
    });
  });

  document.querySelectorAll('.mobile-bottom-nav [data-category]').forEach(item => {
    item.classList.toggle('active', item.dataset.category === category);
  });
  document.querySelectorAll('.mobile-home-tabs [data-category]').forEach(item => {
    item.classList.toggle('active', item.dataset.category === category);
  });

  // Search
  if (searchInput) {
    searchInput.addEventListener('input', filterChannels);
    searchInput.addEventListener('input', () => renderMobileSearch(searchInput.value));
  }

  // Delegate category clicks for home buttons and sidebar nav
  document.body.addEventListener('click', (event) => {
    const button = event.target.closest('.category-card');
    if (button) {
      event.preventDefault();
      const category = button.dataset.category;
      if (category) {
        openCategory(category);
      }
      return;
    }

    const navItem = event.target.closest('.nav-item');
    if (navItem && navItem.dataset.category) {
      event.preventDefault();
      openCategory(navItem.dataset.category);
      return;
    }
  });

  // Existing direct listeners for fallback
  navItems.forEach(item => {
    item.addEventListener('click', (e) => {
      e.preventDefault();
      const category = item.dataset.category;
      if (category) {
        openCategory(category);
      }
    });
  });

  categoryButtons.forEach(button => {
    button.addEventListener('click', () => {
      const category = button.dataset.category;
      if (category) {
        openCategory(category);
      }
    });
  });

  const topNav = document.getElementById('top-nav');
  const toggleMenu = document.getElementById('toggle-menu');

  if (toggleMenu && topNav) {
    toggleMenu.addEventListener('click', () => {
      if (window.innerWidth <= 600) {
        openMobileChannelModal();
        return;
      }
      topNav.classList.toggle('open');
    });
  }

  // Load more button
  if (loadMoreBtn) {
    loadMoreBtn.addEventListener('click', () => {
      loadMoreChannels();
    });
  }
  if (mobileHomeSearchInput) mobileHomeSearchInput.addEventListener('input', () => renderMobileSearch(mobileHomeSearchInput.value));
  document.getElementById('mobile-home-all-groups')?.addEventListener('click', openMobileChannelModal);
  document.getElementById('mobile-home-all-channels')?.addEventListener('click', openMobileChannelModal);
  document.getElementById('mobile-home-more')?.addEventListener('click', openMobileChannelModal);
  document.getElementById('mobile-home-profile')?.addEventListener('click', () => openModal('profile-modal'));

  if (catalogMoreBtn) {
    catalogMoreBtn.addEventListener('click', () => {
      catalogVisibleCount = Math.min(allChannels.length, catalogVisibleCount + 60);
      renderVisualCatalogCards();
    });
  }

  // Settings and Profile
  if (settingsBtn) {
    settingsBtn.addEventListener('click', (e) => {
      e.preventDefault();
      openModal('settings-modal');
    });
  }

  profileBtn.addEventListener('click', (e) => {
    e.preventDefault();
    openModal('profile-modal');
  });

  // Sidebar toggle on mobile
  if (toggleSidebar) {
    toggleSidebar.addEventListener('click', () => {
      sidebar.classList.toggle('show');
    });
  }

  // Close sidebar when clicking outside
  document.addEventListener('click', (e) => {
    if (window.innerWidth <= 768) {
      if (!sidebar.contains(e.target) && e.target !== toggleSidebar) {
        sidebar.classList.remove('show');
      }
    }
  });

  // Player controls
  const fullscreenBtn = document.getElementById('fullscreen-btn');
  const favoritesBtn = document.getElementById('favorites-btn');

  if (fullscreenBtn) {
    fullscreenBtn.addEventListener('click', () => {
      if (videoPlayer.requestFullscreen) {
        videoPlayer.requestFullscreen();
      } else if (videoPlayer.webkitRequestFullscreen) {
        videoPlayer.webkitRequestFullscreen();
      }
    });
  }

  if (favoritesBtn) {
    favoritesBtn.addEventListener('click', () => {
      toggleFavorite();
    });
  }

  if (mobileMinimizeBtn) mobileMinimizeBtn.addEventListener('click', () => toggleMobileMiniPlayer());

  if (videoContainer) {
    let touchStart = null;
    videoContainer.addEventListener('touchstart', event => {
      const touch = event.changedTouches[0];
      touchStart = { x: touch.clientX, y: touch.clientY };
    }, { passive: true });
    videoContainer.addEventListener('touchend', event => {
      if (!touchStart || window.innerWidth > 600) return;
      const touch = event.changedTouches[0];
      const dx = touch.clientX - touchStart.x;
      const dy = touch.clientY - touchStart.y;
      touchStart = null;
      if (Math.abs(dy) > Math.abs(dx) && dy < -60) openMobileChannelModal();
      else if (Math.abs(dy) > Math.abs(dx) && dy > 60) toggleMobileMiniPlayer(true);
      else if (Math.abs(dx) > 60) selectRelativeChannel(dx < 0 ? 1 : -1);
      else if (videoContainer.classList.contains('mobile-mini-player')) toggleMobileMiniPlayer(false);
    }, { passive: true });
  }

  document.body.addEventListener('click', (event) => {
    const groupItem = event.target.closest('.group-item');
    if (!groupItem || groupItem.dataset.groupId) return;

    const groupPath = groupItem.dataset.path ? groupItem.dataset.path.split('||') : [];
    if (!groupPath.length) return;

    currentGroupPath = groupPath;
    applyCurrentCategory();
    populateContentRows();
    updateBreadcrumb();
  });

  if (heroWatchBtn) {
    heroWatchBtn.addEventListener('click', () => {
      if (!currentCategory) {
        openCategory('ao-vivo');
      } else {
        showPlayerScreen();
      }
    });
  }

  // Settings
  const languageSelect = document.getElementById('language-select');
  const themeSelect = document.getElementById('theme-select');

  if (languageSelect) {
    languageSelect.addEventListener('change', (e) => {
      localStorage.setItem('fodao-language', e.target.value);
      showMessage('Idioma atualizado', 'success');
    });
  }

  if (themeSelect) {
    themeSelect.addEventListener('change', (e) => {
      localStorage.setItem('fodao-theme', e.target.value);
      showMessage('Tema atualizado', 'success');
    });
  }

  // Populate devices list
  const devicesList = document.getElementById('devices-list');
  if (devicesList) {
    const devices = [
      { name: 'Este Dispositivo', status: 'Ativo' },
      { name: 'Smart TV Sala', status: 'Inativo' },
      { name: 'Tablet', status: 'Inativo' },
    ];
    devicesList.innerHTML = devices.map(device => `
      <div class="device-item">
        <strong>${device.name}</strong> - ${device.status}
      </div>
    `).join('');
  }

  // Profile info
  document.getElementById('profile-expiry').textContent = new Date(Date.now() + 180 * 24 * 60 * 60 * 1000).toLocaleDateString('pt-BR');
  document.getElementById('profile-created').textContent = new Date().toLocaleDateString('pt-BR');
}

// ============================================
// CLEANUP
// ============================================

window.addEventListener('beforeunload', () => {
  if (hls) {
    hls.destroy();
  }
});
