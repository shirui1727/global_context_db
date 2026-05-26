# NAS 閮ㄧ讲鍜?MCP 鎺ュ叆

杩欎唤鏂囨。缁?NAS 鍥惧舰鐣岄潰鐢ㄦ埛浣跨敤銆傜洰鏍囨槸鎶?`global_context_db` 閮ㄧ讲鎴愪竴涓暱鏈熻繍琛岀殑鍏叡璁板繂鏈嶅姟銆?
## 鏋舵瀯

Docker 椤圭洰浼氬惎鍔ㄤ袱涓鍣細

- `global_context_db-app-1`锛歊EST 鍚庣锛岀鍙?`8000`
- `global_context_db-mcp-1`锛歁CP 鏈嶅姟锛岀鍙?`8001`

鏁版嵁鏀惧湪 Docker 鍗烽噷锛?
- `/data/gcd_v2.sqlite3`
- `/data/lancedb_v2`
- `/data/artifacts`
- `/data/snapshots`

涓嶈鐩存帴鎿嶄綔杩欎簺鏂囦欢锛屽閮ㄥ伐鍏峰彧閫氳繃 REST 鎴?MCP 璁块棶銆?
澶ф枃浠朵笉寤鸿鏀捐繘杩欎釜 Docker 鏁版嵁鍗枫€傚浘搴撱€佽棰戝簱銆佽璁＄礌鏉愩€佸伐绋嬭祫鏂欏簲缁х画鏀惧湪 NAS 鍘熸潵鐨勮祫鏂欑洰褰曪紝`global_context_db` 鍙繚瀛樿矾寰勩€佹憳瑕併€佹爣绛惧拰鎼滅储绱㈠紩銆?
## Docker 闀滃儚鍔犻€?
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

## 绗竴娆″畨瑁?
1. 鎶婇」鐩斁鍒?NAS 鐩綍锛屼緥濡傦細

```text
鍏变韩鏂囦欢澶?docker/SR_AI/global_context_db
```

2. 纭鐩綍閲屽瓨鍦細

```text
docker-compose.yaml
Dockerfile
app/
docs/
pyproject.toml
README.md
```

3. 鍦?Docker / Container Manager 涓繘鍏モ€滈」鐩€濄€?4. 鐐瑰嚮鈥滃垱寤衡€濄€?5. 閫夋嫨锛?
```text
global_context_db/docker-compose.yaml
```

6. 鍒涘缓骞跺惎鍔ㄩ」鐩€?
## Compose 鏂囦欢瑙勫垯

鏈?NAS 椤圭洰缁熶竴浣跨敤锛?
```text
docker-compose.yaml
```

## 绔彛

```text
REST: http://NAS_IP:8000
MCP:  http://NAS_IP:8001/mcp
```

渚嬪锛?
```text
REST: http://192.168.10.5:8000
MCP:  http://192.168.10.5:8001/mcp
```

## 楠岃瘉

鎵撳紑锛?
```text
http://NAS_IP:8000/health
```

娌荤悊鐗堝簲鐪嬪埌锛?
```text
version: 0.1.4-context-domains
```

缁х画鎵撳紑锛?
```text
http://NAS_IP:8000/diagnostics
http://NAS_IP:8000/snapshots
```

濡傛灉 `/diagnostics` 鏄?404锛岃鏄庡鍣ㄩ噷鐨勪唬鐮佽繕鏄棫鐨勶紝闇€瑕佸垹闄ゆ棫闀滃儚鍚庨噸鏂伴儴缃层€?
## OpenClaw / MCP 瀹㈡埛绔厤缃?
鏈嶅姟鍚嶇О锛?
```text
global_context_db
```

浼犺緭绫诲瀷锛?
```text
HTTP 娴佸紡浼犺緭
```

URL锛?
```text
http://NAS_IP:8001/mcp
```

濡傛灉鏈?HTTP 璇锋眰澶磋缃紝鍙互鍔狅細

```text
Accept: application/json, text/event-stream
```

娉ㄦ剰锛歚/mcp` 涓嶆槸鏅€氱綉椤点€傜洿鎺ョ敤娴忚鍣ㄦ墦寮€鍑虹幇 `Missing session ID` 鏄甯哥殑锛孧CP 瀹㈡埛绔細鍏堝彂 initialize 寤虹珛浼氳瘽銆?
## 鏂囦欢搴撳拰澶ф枃浠舵€庝箞鏀?
榛樿瑙勫垯锛?
```text
鍘熸枃浠舵斁鍘熸潵鐨?NAS 璧勬枡搴?璁板繂搴撳彧淇濆瓨绱㈠紩鍜岃矾鏍?```

鎺ㄨ崘缁撴瀯锛?
```text
NAS
鈹溾攢 documents/          鍘熷鏂囨。搴?鈹溾攢 photos/             鍥惧簱
鈹溾攢 videos/             瑙嗛搴?鈹溾攢 projects/           椤圭洰璧勬枡
鈹斺攢 docker/
   鈹斺攢 global_context_db/
      鈹斺攢 data/         鏁版嵁搴撱€佺储寮曘€佺綉椤?HTML銆佹埅鍥俱€佸揩鐓?```

涓夌妯″紡锛?
- 寮曠敤妯″紡锛氶粯璁ゆ帹鑽愩€傚彧璁板綍璺緞銆佹爣棰樸€佹憳瑕併€佹爣绛撅紝涓嶅鍒跺師鏂囦欢銆?- 鎵樼妯″紡锛氬彧閫傚悎灏忔枃鏈€佺綉椤?HTML銆佹埅鍥剧瓑灏忔枃浠躲€?- 鎻愬彇妯″紡锛氶€傚悎鍥剧墖銆佽棰戙€丳DF銆傚彧淇濆瓨 OCR銆佸瓧骞曘€佹憳瑕併€佺缉鐣ュ浘鍜岀储寮曘€?
鍙敤鎺ュ彛锛?
```text
POST /file-references
GET  /file-references
```

MCP 宸ュ叿锛?
```text
gcd_add_file_reference
gcd_list_file_references
```

## 鏇存柊娴佺▼

1. 鍦?Windows 鏈満鐢熸垚鏇存柊鍖咃細

```powershell
powershell -ExecutionPolicy Bypass -File scripts\package-nas-update.ps1
```

2. 鎶婄敓鎴愮殑 zip 瑕嗙洊鍒?NAS锛?
```text
S:\椤圭洰寮€鍙慭鍏ㄥ眬鏁版嵁搴揬release\global_context_db.zip
```

3. 鍦?NAS 鐨?`docker/SR_AI` 杩欎竴灞傝В鍘嬶紝瑕嗙洊鍚屽悕 `global_context_db` 鐩綍銆?4. 鍦?Docker 椤圭洰閲岀‘璁?Compose 閰嶇疆鍐呭鏄柊鐨勩€?5. 鍋滄椤圭洰銆?6. 鍒犻櫎鏃ч暅鍍忥細

```text
global_context_db-app
global_context_db-mcp
```

7. 涓嶈鍒犻櫎鍗凤紝涓嶈鍒犻櫎 `/data`銆?8. 鍥為」鐩紝鐐瑰嚮閲嶆柊閮ㄧ讲銆?
鍙垹闄ゅ鍣ㄤ笉澶燂紱鏃ч暅鍍忚繕鍦ㄦ椂锛岄噸鏂伴儴缃插彲鑳界户缁繍琛屾棫浠ｇ爜銆?
## 蹇収鍜屽閮ㄥぇ鏂囦欢

蹇収澶囦唤鐨勬槸 `global_context_db` 鑷繁鐨勬暟鎹細

```text
SQLite
LanceDB
/data/artifacts
/data/snapshots
```

濡傛灉浣跨敤鏂囦欢寮曠敤妯″紡锛屽閮ㄥ浘搴撱€佽棰戝簱銆侀」鐩祫鏂欏師浠朵粛鍦ㄥ師鏉ョ殑 NAS 璧勬枡鐩綍锛屽揩鐓у彧淇濆瓨瀹冧滑鐨勮矾寰勩€佹憳瑕併€佹爣绛惧拰绱㈠紩锛屼笉浼氬鍒跺師鏂囦欢銆?
## 甯歌闂

### Docker Hub 鎵撳紑闀滃儚鏄?404

姝ｅ父銆俙global_context_db-app` 鍜?`global_context_db-mcp` 鏄?NAS 鏈湴鏋勫缓鐨勯暅鍍忥紝涓嶆槸 Docker Hub 涓婄殑鍏紑闀滃儚銆?
### `/health` 鏂颁簡锛屼絾 `/diagnostics` 鏄?404

璇存槑 Compose 閰嶇疆鏇存柊浜嗭紝浣嗛暅鍍忎唬鐮佹病閲嶅缓銆傚垹闄ゆ棫闀滃儚鍚庨噸鏂伴儴缃层€?
### OpenClaw 鎶?fetch failed

鍏堢‘璁?NAS 绔細

```text
http://NAS_IP:8000/health
http://NAS_IP:8000/diagnostics
```

濡傛灉 REST 姝ｅ父锛屽啀閲嶆柊娣诲姞 OpenClaw 鐨?MCP 鏈嶅姟閰嶇疆锛?
```text
http://NAS_IP:8001/mcp
```

## 鏈満鍛戒护閮ㄧ讲

濡傛灉涓嶆槸 NAS 鍥惧舰鐣岄潰锛屼篃鍙互鍦ㄩ」鐩洰褰曡繍琛岋細

```bash
docker compose -f docker-compose.yaml up -d --build
```

