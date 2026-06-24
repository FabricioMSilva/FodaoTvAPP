const loginForm = document.getElementById('login-form');
const messageContainer = document.getElementById('login-message');
const usernameInput = document.getElementById('username');
const passwordInput = document.getElementById('password');
const rememberCheckbox = document.getElementById('remember');

document.addEventListener('DOMContentLoaded', async () => {
  if (!window.havkSupabase) {
    showMessage('O aplicativo ainda não foi configurado. Execute a geração da configuração Supabase.', 'error');
    return;
  }

  const { data: { session } } = await window.havkSupabase.auth.getSession();
  if (session) {
    window.location.replace('player.html');
    return;
  }

  const savedEmail = localStorage.getItem('fodao-player-email');
  if (savedEmail) {
    usernameInput.value = savedEmail;
    rememberCheckbox.checked = true;
  }
});

loginForm.addEventListener('submit', async event => {
  event.preventDefault();
  const email = usernameInput.value.trim().toLowerCase();
  const password = passwordInput.value;

  if (!email || !password) {
    showMessage('Informe seu e-mail e senha.', 'error');
    return;
  }
  if (!window.havkSupabase) {
    showMessage('A configuração do aplicativo não está disponível.', 'error');
    return;
  }

  showMessage('Entrando...', 'info');
  const { error } = await window.havkSupabase.auth.signInWithPassword({ email, password });
  if (error) {
    showMessage('E-mail ou senha incorretos.', 'error');
    return;
  }

  if (rememberCheckbox.checked) localStorage.setItem('fodao-player-email', email);
  else localStorage.removeItem('fodao-player-email');
  showMessage('Login bem-sucedido! Redirecionando...', 'success');
  setTimeout(() => window.location.replace('player.html'), 300);
});

function showMessage(text, type = 'info') {
  messageContainer.innerHTML = `<div class="message ${type}">${text}</div>`;
  messageContainer.style.display = 'block';
}
