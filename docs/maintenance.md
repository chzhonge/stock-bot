# 股票工具操作手冊

## 第一次安裝

先讓 Discord bot 跑起來，再安裝 WUD 自動更新。Bot 需要已發布的 `ghcr.io/chzhonge/stock-bot:latest`。如果 GHCR 上還沒有映像，先依[發版步驟](#發布新版本)發布第一版。

以下以 `/volume1/docker/projects/` 為例。若 NAS 路徑不同，請讓 bot、私有設定和 WUD 目錄維持並列。

### 1. 啟動 Bot

1. **放置 Compose 檔。** 把 [Bot 的 Compose](../compose.yaml) 複製到 `stock-bot/compose.yaml`。
2. **準備 Bot 設定。** 把 [設定範例](../config.example.toml) 複製到 `stock-bot-private/config.toml`。填入 `[discord]` 的 bot token。要用市場快報時，再填 `[report.discord]` 的 webhook。正式設定留在 NAS，只授權管理者和容器的 UID/GID `10001` 讀取。
3. **設定 Discord 權限。** 在 Discord Developer Portal 啟用 **Message Content Intent**，並給 bot 所用頻道讀取、發送訊息、嵌入連結和附加檔案的權限。
4. **啟動並驗證。** 若映像是私有的，先參考 [GHCR 私有映像](#ghcr-私有映像)。接著在 NAS 執行下列指令。

   ```sh
   cd /volume1/docker/projects/stock-bot
   sudo docker compose config --quiet &&
   sudo docker compose pull stock-bot &&
   sudo docker compose up -d stock-bot
   sudo docker compose logs --tail 50 stock-bot
   ```

   到 Discord 試 `@機器人 2330`，確認 bot 能回圖。如果日誌出現 DNS 或連線錯誤，先看 [NAS 容器無法連外](#nas-容器無法連外)。

### 2. 啟動 WUD

在 NAS 建立 `/volume1/docker/projects/wud/`，並依下表準備檔案。

| 從 repo 取得 | 在 WUD 目錄的檔名 | 用途 |
| --- | --- | --- |
| [WUD Compose](../deploy/wud/compose.yaml) | `compose.yaml` | 啟動背景監看和自動更新 |
| [環境變數範例](../deploy/wud/.env.example) | `.env` | 填 bot 路徑和 WUD 管理員帳密 |
| [單次更新腳本](../deploy/wud/check-and-update.sh) | `check-and-update.sh` | 選用，從終端機立即檢查 |

在 WUD 的 `.env` 填入下列欄位。路徑指向 bot 的部署目錄，末尾省略 `/`。填入實際密碼，並限制 `.env` 的讀取權限。WUD 即使關閉網頁，首次啟動仍需要初始化管理員。 [WUD 管理員設定](https://getwud.app/docs/configuration/authentications/)

```dotenv
STOCK_BOT_COMPOSE_DIR=/volume1/docker/projects/stock-bot
WUD_AUTH_ADMIN_USER=admin
WUD_AUTH_ADMIN_PASSWORD=
```

範本透過 Docker socket 更新 bot，並掛入 `stock-bot/` 以讀寫 Compose。含 Discord 憑證的 `stock-bot-private/` 留在旁邊。若這台 NAS 也需要替 WUD 指定 bridge 或 DNS，啟動前先建立 [WUD 的本機覆寫檔](#nas-容器無法連外)。若 bot 使用私有映像，也先完成 [WUD 的 GHCR 認證](#ghcr-私有映像)。

```sh
cd /volume1/docker/projects/wud
sudo docker compose config --quiet && sudo docker compose up -d wud
sudo docker compose logs --tail 50 wud
```

確認日誌顯示 WUD 已啟動並能檢查 `stock-bot`。網頁和 HTTP API 預設關閉。等下次正常發版，再驗證 WUD 能自動重建 bot，並確認 Discord 能回圖、尚未到期的夜盤樣本仍在。 [WUD Compose 更新文件](https://getwud.app/docs/configuration/triggers/docker-compose/)

## 平常怎麼用

| 要做什麼 | 在哪裡操作 |
| --- | --- |
| 發布新映像 | 在電腦上[建立 Release 草稿](#發布新版本)，到 GitHub 確認並發布。 |
| 等待自動更新 | WUD 每小時整點檢查。想換頻率，見[自訂 WUD 排程](#自訂-wud-排程)。 |
| 立刻檢查並更新 | 在 NAS 執行 `sudo sh /volume1/docker/projects/wud/check-and-update.sh`。沿用 WUD 的自動更新設定，有新映像就會重建 bot。 |
| 查看日誌 | 在各自的 NAS 部署目錄執行 `sudo docker compose logs --tail 50 stock-bot` 或 `sudo docker compose logs --tail 50 wud`。 |
| 手動跑市場快報 | 在 NAS 的 bot 目錄執行 `sudo docker compose run --rm stock-bot python -m scripts.tw_market_report --config /app/config.toml`。 |

### 發布新版本

1. 確認 `codex/architecture-refactor` 上要發版的 commit 已推送到 `chzhonge/stock-bot`。準備 UTF-8 Markdown 發行說明，有內容才列「新功能」「修正」「部署與升級」。第一版以本分支和原作者 `main` 的共同起點為基準，之後比較上一個正式 tag。
2. 用 `gh auth login --hostname github.com --web` 登入 GitHub CLI，再從 repo 根目錄執行下方指令。將版本號、摘要和發行說明路徑換成這一版的值。[腳本](../tools/release_draft.py) 會用 `stock-bot v<版本號> - <本版重點>` 建立草稿並印出網址。

   ```sh
   python tools/release_draft.py 1.0.1 --summary "本版重點" --notes-file release-notes.md
   ```

3. 到 GitHub 確認草稿的標題、說明和目標 commit，再按 **Publish release**。到 **Actions** 確認建置和兩個指令入口的檢查已通過。成功後，GHCR 會有 Release tag 和 `latest`，兩者指向同一份 `linux/amd64` 映像。

### 本機操作與設定

在本機安裝 uv，於 repo 根目錄放置 `config.toml`。先執行 `uv sync --locked` 安裝依賴，再依需要啟動 bot 或快報。

- 用 `uv run --locked stock-chart-bot --config config.toml` 啟動 bot。
- 用 `uv run --locked python -m scripts.tw_market_report --config config.toml` 手動跑快報。

快報會在台灣上班日透過 webhook 發送。行事曆無法查詢時會繼續執行。

- **查詢別名**在 `config.toml` 的 `[aliases]` 設定，以股票代碼或 `night` 為目標。格式見[設定範例](../config.example.toml)。
- **快報股票清單**在 [快報腳本](../scripts/tw_market_report.py) 的 `WATCHLIST`。上市用 `tse`，上櫃用 `otc`。NAS 要用新清單時，請發布新映像。
- **夜盤樣本**預設是設定檔旁的 `data/night-samples.jsonl`。NAS 的 `/app/data` 對應 `night-data` 資料卷。若自訂 `night.sample_file`，請讓 NAS 上的樣本繼續存在該資料卷內。

## 有問題才看

### NAS 容器無法連外

若 NAS 能解析 `discord.com`，但容器查 DNS 失敗，直接連外部 IP 的 TCP 443 也逾時，請查 NAS 的轉送防火牆是否放行 Compose 專用網路。單獨指定 `dns` 只會改變查詢對象。

可以放行該子網所需的 DNS 和出站 HTTPS。若防火牆已放行 Docker 內建的 `bridge`，也可以讓受影響的服務改走該網路。把覆寫檔放在對應服務的 `compose.yaml` 旁，Compose 會自動合併。以下的 `192.0.2.53` 是範例，請換成容器能連到的 DNS 位址。預設 DNS 可用時可省略 `dns`。 [Docker 網路文件](https://docs.docker.com/compose/how-tos/networking/) · [Compose 覆寫文件](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)

**Bot 的 `stock-bot/compose.override.yaml`**

```yaml
services:
  stock-bot:
    network_mode: bridge
    dns:
      - 192.0.2.53
```

**WUD 的 `wud/compose.override.yaml`**

```yaml
services:
  wud:
    network_mode: bridge
    dns:
      - 192.0.2.53
```

在各自的部署目錄執行 `sudo docker compose config --quiet && sudo docker compose up -d`。重裝或搬機時，記得備份有使用的覆寫檔。

### 自訂 WUD 排程

若想每 15 分鐘檢查，在 NAS 的 `wud/compose.override.yaml` 合併以下設定，保留現有的網路和 DNS 欄位。存檔後在 WUD 目錄執行 `sudo docker compose up -d wud`。 [WUD 排程文件](https://getwud.app/docs/configuration/watchers/)

```yaml
services:
  wud:
    environment:
      WUD_WATCHER_LOCAL_CRON: "*/15 * * * *"
```

### GHCR 私有映像

在 NAS 執行 `sudo docker login ghcr.io -u YOUR_GITHUB_USERNAME`，密碼使用對該套件有讀取權限、具 `read:packages` 的 classic PAT。若 WUD 也要自動更新私有映像，在 NAS 的 `wud/compose.override.yaml` 的 `services.wud.environment` 加入 `WUD_REGISTRY_GHCR_LOCAL_USERNAME` 和 `WUD_REGISTRY_GHCR_LOCAL_TOKEN`。 [WUD GHCR 認證](https://getwud.app/docs/configuration/registries/ghcr/)

### 從舊設定升級

- 若舊 Compose 的服務名是 `bot`，先用舊檔執行 `sudo docker compose stop bot` 和 `sudo docker compose rm -f bot`，再換新版。沿用原本的 Compose 專案目錄和專案名稱，可繼續使用 `night-data`。
- 若 bot 的 `config.toml` 原先放在部署目錄內，把它移到旁邊的 `stock-bot-private/`，再套用新版 Compose。舊的 `[report.index]`、`[[report.quotes]]` 和 `[[report.watchlist]]` 自訂內容移到快報腳本後，再從 TOML 移除。
- 若 WUD 管理員帳密原先放在 WUD 的覆寫檔，把值移到同目錄的 `.env`，再刪除覆寫檔裡的兩個帳密欄位。
