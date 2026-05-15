# Global Context DB Desktop

Electron + Vite + React desktop shell for the local FastAPI backend.

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

The Electron main process connects to `http://127.0.0.1:8000`. If the backend is not already running, it starts `python -m uvicorn app.main:app --host 127.0.0.1 --port 8000` from the project root.

First version workflow:

1. Start the desktop app with `npm start`.
2. Use `采集` to import public URLs, refresh RSS feeds, and run batch URL imports.
3. Use `文件夹` to choose a folder, scan supported text files, then import them in one batch.
4. Supported file types are `.txt`, `.md`, `.markdown`, `.json`, `.csv`, and `.log`.
5. Files larger than 5 MB are skipped in the first version.
6. Use `文件库`, `搜索`, and `记忆` to review imported documents, search local context, and store long-term notes.

Chromium capture extension:

1. Open Chrome / Edge / Brave extensions page.
2. Enable developer mode.
3. Load unpacked extension from `S:\项目开发\全局数据库\global_context_db\desktop\extension`.
4. Open a normal web page, click the extension icon, then choose `保存当前页`, `保存选中文本`, or `保存可见截图`.

The extension only sends content already visible in the user's browser to `http://127.0.0.1:8000`. It does not store accounts, automate login, bypass paywalls, solve CAPTCHA, or work around anti-bot restrictions.
