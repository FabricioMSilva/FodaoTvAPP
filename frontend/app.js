// ============================================
// FODÃO PLAYER - Login Script
// ============================================

const loginForm = document.getElementById('login-form');
const messageContainer = document.getElementById('login-message');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const rememberCheckbox = document.getElementById('remember');
const serverUrlInput = document.getElementById('server-url');
const isNativeApp = window.Capacitor?.isNativePlatform?.() === true;
const defaultApiBase = window.location.protocol === 'file:'
  ? 'http://127.0.0.1:8000'
  : (isNativeApp ? 'http://192.168.15.4:8000' : window.location.origin);

// Initialize with saved username if available
document.addEventListener('DOMContentLoaded', () => {
  // A file:// page has a "null" origin and cannot call the FastAPI endpoints.
  // Move it to the running local app before any login request is attempted.
  if (window.location.protocol === 'file:') {
    window.location.replace(`${defaultApiBase}/static/index.html`);
    return;
  }

  const savedUsername = localStorage.getItem('fodao-player-username');
  const savedApiBase = localStorage.getItem('havk-api-base');
  serverUrlInput.value = savedApiBase || defaultApiBase;
  if (isNativeApp) {
    serverUrlInput.placeholder = 'http://192.168.15.4:8000';
  }
  if (savedUsername) {
    usernameInput.value = savedUsername;
    rememberCheckbox.checked = true;
  }
});

// Handle Login Form Submission
loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  
  const username = usernameInput.value.trim();
  const password = passwordInput.value;
  let apiBase = '';
  
  if (!username || !password) {
    showMessage('Por favor, preencha todos os campos', 'error');
    return;
  }

  try {
    apiBase = new URL(serverUrlInput.value.trim()).origin;
  } catch {
    showMessage('Informe a URL do servidor, por exemplo http://192.168.0.10:8000', 'error');
    return;
  }
  localStorage.setItem('havk-api-base', apiBase);

  // Save username if "Remember me" is checked
  if (rememberCheckbox.checked) {
    localStorage.setItem('fodao-player-username', username);
  } else {
    localStorage.removeItem('fodao-player-username');
  }

  // Store credentials in session storage for the player page
  sessionStorage.setItem('fodao-auth-username', username);
  sessionStorage.setItem('fodao-auth-password', btoa(password)); // Simple encoding

  // Verify credentials by trying to fetch the playlist
  try {
    showMessage('Verificando credenciais...', 'info');
    const playlistUrl = `${apiBase}/playlist/${encodeURIComponent(username)}.m3u`;
    
    const response = await fetch(playlistUrl, {
      method: 'GET',
      headers: {
        'Authorization': 'Basic ' + btoa(`${username}:${password}`),
      },
    });

    if (!response.ok) {
      if (response.status === 401) {
        showMessage('Usuário ou senha incorretos', 'error');
      } else if (response.status === 404) {
        showMessage('Usuário não encontrado', 'error');
      } else {
        showMessage(`Erro: ${response.statusText}`, 'error');
      }
      return;
    }

    // Credentials are valid, redirect to player
    showMessage('Login bem-sucedido! Redirecionando...', 'success');
    setTimeout(() => {
      window.location.href = apiBase === window.location.origin ? `${apiBase}/player` : 'player.html';
    }, 500);

  } catch (error) {
    showMessage(`Erro de conexão: ${error.message}`, 'error');
  }
});

function showMessage(text, type = 'info') {
  messageContainer.innerHTML = `<div class="message ${type}">${text}</div>`;
  messageContainer.style.display = 'block';
  
  // Auto-clear success messages after 3 seconds
  if (type === 'success') {
    setTimeout(() => {
      messageContainer.style.display = 'none';
    }, 3000);
  }
}

// Allow keyboard shortcuts
document.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && (document.activeElement === usernameInput || document.activeElement === passwordInput)) {
    loginForm.dispatchEvent(new Event('submit'));
  }
});
