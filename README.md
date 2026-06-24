# Fodão Player

Player IPTV com interface web/PWA, aplicativo Android via Capacitor, API FastAPI e player desktop em Python.

## Estrutura

| Diretório | Finalidade |
| --- | --- |
| `backend/` | API FastAPI, autenticação atual e entrega de catálogo/playlists. |
| `frontend/` | Interface web, PWA e player responsivo. |
| `android/` | Projeto Android nativo gerado pelo Capacitor. |
| `player/` | Player desktop em Python. |
| `tools/` | Utilitários de importação, análise e organização de M3U. |
| `extract_m3u_links.py` | Extrai uma playlist para o catálogo leve consumido pela API. |

Dados privados e gerados — playlists M3U, usuários, catálogo extraído, APKs e ambientes locais — não são versionados.

## Requisitos

- Python 3.10+
- Node.js 20+
- JDK 21 e Android SDK para compilar o aplicativo Android

## Executar a API e o player web

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn backend.app:app --host 0.0.0.0 --port 8000
```

Abra `http://localhost:8000/player` no navegador.

Para acessar pelo celular na mesma rede, use o IP do computador, por exemplo `http://192.168.15.4:8000`; `localhost` no celular aponta para o próprio aparelho.

## Catálogo local

Coloque uma playlist autorizada em `player/playlists/`. O projeto procura, nesta ordem:

1. `2596364918xtvs-1782216748325.m3u8`
2. `canaisfilmeseseries.m3u`
3. `capas.m3u8`

Para gerar o catálogo leve, execute:

```powershell
python extract_m3u_links.py
```

Os arquivos resultantes ficam em `output_extracao/` e são ignorados pelo Git por poderem conter links privados.

## Android

Instale dependências e sincronize os arquivos web antes de abrir ou compilar o Android:

```powershell
npm install
npm run android:sync
```

Para gerar um APK de teste:

```powershell
cd android
.\gradlew.bat assembleDebug
```

O APK será criado em `android/app/build/outputs/apk/debug/app-debug.apk`.

## Player desktop

```powershell
python player/run_player.py
```

## Próxima etapa: Supabase

O arquivo `.env.example` lista as variáveis previstas para a futura autenticação e catálogo centralizados no Supabase. Copie-o para `.env`, preencha localmente e nunca publique a chave `SUPABASE_SERVICE_ROLE_KEY`.

## Aviso

Use apenas links e conteúdos para os quais você tenha autorização de distribuição.
