const isNativeApp = window.Capacitor?.isNativePlatform?.() === true;

// Capacitor already packages the web assets. Its localhost WebView origin does
// not expose the browser-only /static cache paths used by the PWA worker.
if (!isNativeApp && 'serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
  window.addEventListener('load', () => navigator.serviceWorker.register('/static/sw.js'));
}
