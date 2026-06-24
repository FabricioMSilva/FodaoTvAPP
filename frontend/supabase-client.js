(() => {
  const config = window.HAVK_SUPABASE_CONFIG;
  if (!config?.url || !config?.anonKey || !window.supabase?.createClient) {
    console.error('A configuração pública do Supabase não foi encontrada. Execute npm run supabase:config.');
    return;
  }
  window.havkSupabase = window.supabase.createClient(config.url, config.anonKey, {
    auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true },
  });
})();
