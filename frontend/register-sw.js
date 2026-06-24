const isNativeApp = window.Capacitor?.isNativePlatform?.() === true;

// Capacitor already packages the web assets. Its localhost WebView origin does
// not expose the browser-only /static cache paths used by the PWA worker.
if (!isNativeApp && 'serviceWorker' in navigator && window.location.protocol.startsWith('http')) {
  window.addEventListener('load', async () => {
    const registration = await navigator.serviceWorker.register('/sw.js');

    registration.addEventListener('updatefound', () => {
      const newWorker = registration.installing;
      if (!newWorker) return;
      newWorker.addEventListener('statechange', () => {
        if (newWorker.state === 'installed' && navigator.serviceWorker.controller) {
          window.location.reload();
        }
      });
    });

    navigator.serviceWorker.addEventListener('controllerchange', () => {
      window.location.reload();
    });
  });
}
