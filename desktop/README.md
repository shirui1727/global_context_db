# Global Context DB Desktop

Electron + Vite + React desktop shell for Global Context DB.

```bash
cd desktop
npm install
npm run dev
```

Useful commands:

```bash
npm run lint
npm run build
npm start
npm run package:win
```

## Connection

The desktop app defaults to `http://127.0.0.1:8000`. Open the Settings page to switch it to a NAS service, for example:

```text
http://192.168.10.5:8000
```

If the backend is local and not running, the Electron main process can start:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

For NAS mode, the desktop app only connects to the remote service. It will not try to start a backend on the NAS.

## First Version Workflow

1. Start the desktop app.
2. Use Settings to choose local or NAS backend.
3. Use Capture to import public URLs, RSS feeds, and batch URL lists.
4. Use Documents to import text files or paste text.
5. Use Memory to add, edit, delete, and inspect long-term memories.
6. Use Governance to review audit logs and recent search results.

Supported file types are `.txt`, `.md`, `.markdown`, `.json`, `.csv`, and `.log`. Files larger than 5 MB are skipped in the first version.

## Chromium Capture Extension

1. Open Chrome / Edge / Brave extensions page.
2. Enable developer mode.
3. Load unpacked extension from `desktop/extension`.
4. Open a normal web page and use the extension popup to save the current page, selected text, or visible screenshot.

The extension only sends content already visible in the user's browser to the configured local service. It does not store accounts, automate login, bypass paywalls, solve CAPTCHA, or work around anti-bot restrictions.
