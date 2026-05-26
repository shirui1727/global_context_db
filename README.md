# Global Context DB

Global Context DB 鏄竴涓儴缃插湪 NAS 涓婄殑鍏叡璁板繂搴擄紝鐢ㄦ潵缁?Codex銆丱penClaw銆丆laude Code銆佹闈㈢鍜屾祻瑙堝櫒鎻掍欢鍏变韩闀挎湡璁板繂涓庝笂涓嬫枃銆?
瀹冧笉鏄櫘閫氱瑪璁拌蒋浠躲€傚畠鐨勬牳蹇冪洰鏍囨槸锛氳澶氫釜 AI 宸ュ叿閫氳繃鍚屼竴涓?MCP / REST 鍚庣璁块棶闀挎湡璁板繂銆佹枃妗ｅ拰閲囬泦鍐呭锛岃€屼笉鏄悇鑷繚瀛樹竴浠藉绔嬩笂涓嬫枃銆?
## 褰撳墠鑳藉姏

- 闀挎湡璁板繂锛氬啓鍏ャ€佹煡璇€佹洿鏂般€佸垹闄ゃ€佸幓閲嶃€?- 鏂囨。鍏ュ簱锛氭枃鏈€佹枃浠躲€佸叕寮€ URL銆?- 鏂囦欢寮曠敤绱㈠紩锛氬浘搴撱€佽棰戝簱銆佸ぇ鏂囦欢淇濈暀鍦ㄥ師浣嶇疆锛屽彧鐧昏璺緞銆佹憳瑕佸拰鏍囩銆?- 璧勬枡閲囬泦锛氱綉椤靛壀钘忋€丷SS銆佹壒閲?URL銆?- 娌荤悊鑳藉姏锛氬璁℃棩蹇椼€佺増鏈巻鍙层€佽瘖鏂粺璁°€佽鍒犱繚鎶ゃ€?- 蹇収鑳藉姏锛氭墜鍔ㄥ鍑哄拰鎭㈠ SQLite銆丩anceDB銆乤rtifacts銆?- NAS 鎺ュ叆锛欴ocker 閮ㄧ讲锛岃繙绋?MCP 鍦板潃銆?
## 蹇€熷湴鍧€

鎶?`NAS_IP` 鏇挎崲鎴愪綘鐨?NAS IP锛屼緥濡?`192.168.10.5`銆?
```text
REST:        http://NAS_IP:8000
Health:      http://NAS_IP:8000/health
Diagnostics: http://NAS_IP:8000/diagnostics
MCP:         http://NAS_IP:8001/mcp
```

閮ㄧ讲鎴愬姛鍚庯紝`/health` 閲屽簲鐪嬪埌锛?
```json
{
  "ok": true,
  "service": "global-context-db",
  "version": "0.1.4-context-domains"
}
```

## NAS Docker 瀹夎

### 1. 閰嶇疆 Docker 闀滃儚鍔犻€?
鍥藉唴缃戠粶鐩存帴涓嬭浇 `python:3.12-slim` 杩欑被鍩虹闀滃儚鍙兘浼氬緢鎱㈡垨澶辫触銆傜涓€娆″垱寤洪」鐩墠锛屽缓璁厛鍦?NAS 鐨?Docker / Container Manager 閲岄厤缃暅鍍忓姞閫熴€?
甯歌鍏ュ彛锛?
1. 鎵撳紑 Docker / Container Manager銆?2. 杩涘叆鈥滄敞鍐岃〃 / Registry鈥濇垨鈥滆缃?/ 闀滃儚鍔犻€熷櫒鈥濄€?3. 娣诲姞鍙敤鐨?Docker Hub 闀滃儚鍔犻€熷湴鍧€銆?4. 淇濆瓨鍚庨噸鏂板垱寤烘垨閲嶆柊閮ㄧ讲椤圭洰銆?
濡傛灉 NAS 鏀寔濉啓 `registry-mirrors`锛屾牸寮忛€氬父绫讳技锛?
```json
{
  "registry-mirrors": [
    "https://浣犵殑闀滃儚鍔犻€熷湴鍧€"
  ]
}
```

闀滃儚鍔犻€熼厤缃ソ浠ュ悗锛孨AS 鎵嶈兘鏇寸ǔ瀹氬湴涓嬭浇锛?
```text
python:3.12-slim
```

### 2. 鍑嗗鐩綍

鍦?NAS 鍏变韩鏂囦欢澶归噷鏀惧埌绫讳技鐩綍锛?
```text
docker/SR_AI/global_context_db
```

椤圭洰鐩綍閲屽簲鍖呭惈锛?
```text
app/
docs/
desktop/
Dockerfile
docker-compose.yaml
pyproject.toml
README.md
```

涓嶈鎶?`data`銆乣.git`銆乣node_modules` 鏀捐繘鏇存柊鍖呫€?
### 3. 鍒涘缓 Docker 椤圭洰

鍦?NAS Docker / Container Manager 閲岋細

1. 杩涘叆鈥滈」鐩€濄€?2. 鐐瑰嚮鈥滃垱寤衡€濄€?3. 閫夋嫨 `global_context_db/docker-compose.yaml`銆?4. 鍒涘缓骞跺惎鍔ㄩ」鐩€?
鏈」鐩娇鐢ㄧ殑 Compose 鏂囦欢鍚嶇粺涓€涓猴細

```text
docker-compose.yaml
```

### 4. Docker Compose 閰嶇疆

褰撳墠 `docker-compose.yaml` 浼氬惎鍔ㄤ袱涓湇鍔★細

- `app`锛歊EST 鍚庣锛岀鍙?`8000`
- `mcp`锛氳繙绋?MCP 鏈嶅姟锛岀鍙?`8001`

鍏抽敭鐜鍙橀噺锛?
```yaml
GCD_DATA_DIR: /data
GCD_SQLITE_PATH: /data/gcd_v2.sqlite3
GCD_LANCEDB_DIR: /data/lancedb_v2
GCD_SERVICE_VERSION: 0.1.4-context-domains
```

MCP 鏈嶅姟棰濆浣跨敤锛?
```yaml
GCD_MCP_HOST: 0.0.0.0
GCD_MCP_PORT: 8001
GCD_MCP_PATH: /mcp
```

### 5. 楠岃瘉

鎵撳紑锛?
```text
http://NAS_IP:8000/health
```

缁х画纭锛?
```text
http://NAS_IP:8000/diagnostics
http://NAS_IP:8000/snapshots
```

`/diagnostics` 鑳借繑鍥炵粺璁′俊鎭紝璇存槑娌荤悊鐗堝凡缁忕湡姝ｈ窇璧锋潵銆?
## AI 宸ュ叿閰嶇疆

### OpenClaw / 鏀寔杩滅▼ MCP 鐨勫鎴风

鏂板 MCP 鏈嶅姟锛?
```text
鏈嶅姟鍚嶇О锛歡lobal_context_db
浼犺緭绫诲瀷锛欻TTP 娴佸紡浼犺緭
URL锛歨ttp://NAS_IP:8001/mcp
```

濡傛灉瀹㈡埛绔厑璁稿～鍐?HTTP 璇锋眰澶达紝鍙姞锛?
```text
Accept: application/json, text/event-stream
```

閫氬父 MCP 瀹㈡埛绔細鑷姩甯﹁繖涓ご锛屼笉濉篃鍙互鍏堟祴璇曘€?
### MCP 宸ュ叿鍚?
涓诲伐鍏峰悕浣跨敤 `gcd_*`锛?
- `gcd_health`
- `gcd_add_memory`
- `gcd_search_memories`
- `gcd_list_memories`
- `gcd_update_memory`
- `gcd_delete_memory`
- `gcd_ingest_text`
- `gcd_add_file_reference`
- `gcd_list_file_references`
- `gcd_search_context`
- `gcd_diagnostics`
- `gcd_export_snapshot`
- `gcd_list_snapshots`
- `gcd_restore_snapshot`

鍏煎鏃у鎴风锛?
- `memory_search`
- `memory_export_snapshot`
- `memory_restore_snapshot`

## 鎵嬪姩鏇存柊 NAS

鍦?Windows 鏈満鐢熸垚鏇存柊鍖咃細

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1
```

鐢熸垚缁撴灉锛?
```text
S:\椤圭洰寮€鍙慭鍏ㄥ眬鏁版嵁搴揬release\global_context_db.zip
```

鏇存柊姝ラ锛?
1. 瑙ｅ帇 `global_context_db.zip`銆?2. 瑕嗙洊 NAS 鐨?`docker/SR_AI/global_context_db` 鐩綍銆?3. 纭椤圭洰閰嶇疆閲屾槸鏂扮殑 `docker-compose.yaml` 鍐呭銆?4. 鍋滄椤圭洰銆?5. 鍒犻櫎鏃ч暅鍍?`global_context_db-app` 鍜?`global_context_db-mcp`銆?6. 涓嶈鍒犻櫎鏁版嵁鍗凤紝涓嶈鍒犻櫎 `/data`銆?7. 鍥炲埌椤圭洰锛岄噸鏂伴儴缃层€?
鍙垹闄ゅ鍣ㄤ笉澶燂紱濡傛灉闀滃儚娌″垹锛孨AS 鍙兘缁х画鐢ㄦ棫浠ｇ爜鍒涘缓鏂板鍣ㄣ€?
## 蹇収澶囦唤

瀵煎嚭蹇収锛?
```bash
curl -X POST http://NAS_IP:8000/snapshots
```

鍒楀嚭蹇収锛?
```bash
curl http://NAS_IP:8000/snapshots
```

鎭㈠蹇収锛?
```bash
curl -X POST http://NAS_IP:8000/snapshots/restore \
  -H "Content-Type: application/json" \
  -d "{\"snapshot_path\":\"/data/snapshots/your_snapshot.zip\"}"
```

鎭㈠鍓嶈纭蹇収鏉ヨ嚜鏈」鐩鍑恒€?
蹇収浼氬浠?`global_context_db` 鑷繁鐨勬暟鎹細SQLite銆丩anceDB銆乣/data/artifacts`銆傚鏋滀綘鐢ㄧ殑鏄枃浠跺紩鐢ㄦā寮忥紝澶栭儴鍥惧簱銆佽棰戝簱銆侀」鐩枃浠跺師浠朵粛鍦ㄥ師 NAS 璧勬枡鐩綍锛屼笉浼氳蹇収澶嶅埗杩涙潵銆?
## 鏂囦欢搴撳拰澶ф枃浠?
榛樿涓嶈鎶婂浘搴撱€佽棰戝簱銆佽璁＄礌鏉愩€佸伐绋嬭祫鏂欒繖绫诲ぇ鏂囦欢澶嶅埗杩?`global_context_db`銆傛帹鑽愭柟寮忔槸锛?
```text
鍘熸枃浠剁户缁斁鍦?NAS 鍘熸潵鐨勮祫鏂欑洰褰?global_context_db 鍙繚瀛樿矾寰勩€佹爣棰樸€佹憳瑕併€佹爣绛俱€佺被鍨嬨€佸ぇ灏忓拰鍚戦噺绱㈠紩
```

甯歌鐩綍鍙互杩欐牱鍒嗭細

```text
NAS
鈹溾攢 documents/          鍘熷鏂囨。搴?鈹溾攢 photos/             鍥惧簱
鈹溾攢 videos/             瑙嗛搴?鈹溾攢 projects/           椤圭洰璧勬枡
鈹斺攢 docker/
   鈹斺攢 global_context_db/
      鈹斺攢 data/         鏁版嵁搴撱€佺储寮曘€佺缉鐣ュ浘銆佺綉椤?HTML銆佸揩鐓?```

涓夌璧勬枡妯″紡锛?
- 寮曠敤妯″紡锛氶粯璁ゆ帹鑽愩€備笉澶嶅埗鍘熸枃浠讹紝鍙褰?`smb://...`銆乣/volume1/...` 鎴栧叾浠栧彲鎵撳紑璺緞銆?- 鎵樼妯″紡锛氬彧閫傚悎灏忔枃鏈€佸皬 Markdown銆佺綉椤?HTML銆佹埅鍥剧瓑闇€瑕侀殢搴撳浠界殑灏忔枃浠躲€?- 鎻愬彇妯″紡锛氶€傚悎鍥剧墖銆佽棰戙€丳DF銆傚師鏂囦欢涓嶅姩锛屽彧淇濆瓨 OCR銆佸瓧骞曘€佹憳瑕併€佺缉鐣ュ浘銆佹爣绛俱€?
鐧昏涓€涓閮ㄦ枃浠跺紩鐢細

```bash
curl -X POST http://NAS_IP:8000/file-references \
  -H "Content-Type: application/json" \
  -d "{\"uri\":\"smb://NAS/documents/project.pdf\",\"title\":\"椤圭洰璧勬枡\",\"media_type\":\"application/pdf\",\"summary\":\"椤圭洰鑳屾櫙鍜屽叧閿喅绛朶",\"tags\":[\"椤圭洰\",\"璧勬枡\"]}"
```

## 鏈湴寮€鍙?
```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

妗岄潰绔細

```bash
cd desktop
npm install
npm run dev
```

## 璁捐鍘熷垯

- NAS 鏄叕鍏辨暟鎹眰銆?- MCP 鏄?AI 宸ュ叿浼樺厛鍏ュ彛銆?- REST 鏄鐞嗐€佽皟璇曞拰妗岄潰绔叆鍙ｃ€?- 澶栭儴宸ュ叿涓嶈鐩存帴鎿嶄綔 SQLite 鎴?LanceDB 鏂囦欢銆?- 闀挎湡璁板繂鍜屽畬鏁翠細璇濇祦姘村垎灞傚鐞嗐€?

## Design notes

- `docs/current-architecture-v0.3.md`: current authoritative architecture for memory, document, asset, session, improvement, REST, MCP, and retrieval boundaries.
- `docs/asset-hardening-v0.2.md`: asset governance, identity, versions, locations, artifacts, and scan runs.
- `docs/cognee-absorption-v0.3.md`: Cognee absorption notes and the actionable v0.3 checklist for session, trace, resume context, and improve tasks.
- `docs/frontier-memory-absorption-v0.3.md`: frontier memory-system notes from LangGraph, Mem0, Generative Agents, and MCP security practice.
