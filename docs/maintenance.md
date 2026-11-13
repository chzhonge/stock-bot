# 股票工具操作手冊

## 第一次安裝

部署使用已發布的 `ghcr.io/chzhonge/stock-bot:latest`。Bot 能在 Discord 回圖後，就完成首次部署。

以下指令中的 `/path/to/projects` 請換成 Docker 主機的實際部署路徑。`stock-bot/`、`stock-bot-private/` 和 `wud/` 放在同一層。

### 1. 啟動 Bot

1. **放置 Compose 檔。** 把 [Bot 的 Compose](../compose.yaml) 複製到 `stock-bot/compose.yaml`。
2. **準備 Bot 設定。** 把 [設定範例](../config.example.toml) 複製到 `stock-bot-private/config.toml`，填入 `[discord]` 的 bot token。市場快報才需要 `[report.discord]` 的 webhook。正式設定留在 Docker 主機，讀取權限限於管理者和容器的 UID/GID `10001`。
3. **設定 Discord 權限。** 在 Discord Developer Portal 啟用 **Message Content Intent**，並給 bot 所用頻道讀取、發送訊息、嵌入連結和附加檔案的權限。
4. **啟動並驗證。** 若映像是私有的，先參考 [GHCR 私有映像](#ghcr-私有映像)。接著在 Docker 主機執行下列指令。

   ```sh
   cd /path/to/projects/stock-bot
   sudo docker compose config --quiet &&
   sudo docker compose pull &&
   sudo docker compose up -d
   sudo docker compose logs --tail 50 stock-bot
   ```

   到 Discord 試 `@機器人 2330`，確認 bot 能回圖。如果日誌出現 DNS 或連線錯誤，先看[容器無法連外](#容器無法連外)。

### 選用｜用 WUD 自動更新

若希望新映像發布後自動更新 bot，再安裝 WUD。在 Docker 主機的部署路徑下建立 `wud/`，並依下表準備檔案。

| 從 repo 取得 | 在 WUD 目錄的檔名 | 用途 |
| --- | --- | --- |
| [WUD Compose](../deploy/wud/compose.yaml) | `compose.yaml` | 啟動背景監看和自動更新 |
| [環境變數範例](../deploy/wud/.env.example) | `.env` | 填 bot 路徑和 WUD 管理員帳密 |
| [單次更新腳本](../deploy/wud/check-and-update.sh) | `check-and-update.sh` | 選用，從終端機立即檢查 |

在 WUD 的 `.env` 填入下列欄位。路徑指向 bot 的部署目錄，末尾省略 `/`。填入實際密碼，並限制 `.env` 的讀取權限。WUD 即使關閉網頁，首次啟動仍需要初始化管理員。 [WUD 管理員設定](https://getwud.app/docs/configuration/authentications/)

```dotenv
STOCK_BOT_COMPOSE_DIR=/path/to/projects/stock-bot
WUD_AUTH_ADMIN_USER=admin
WUD_AUTH_ADMIN_PASSWORD=
```

範本透過 Docker socket 更新 bot，並掛入 `stock-bot/` 以讀寫 Compose。含 Discord 憑證的 `stock-bot-private/` 留在旁邊。若 WUD 需要指定 bridge 或 DNS，啟動前先建立 [WUD 的本機覆寫檔](#容器無法連外)。若 bot 使用私有映像，也先完成 [WUD 的 GHCR 認證](#ghcr-私有映像)。

```sh
cd /path/to/projects/wud
sudo docker compose config --quiet && sudo docker compose up -d wud
sudo docker compose logs --tail 50 wud
```

確認日誌顯示 WUD 已啟動並能檢查 `stock-bot`。網頁和 HTTP API 預設關閉。等下次正常發版，再驗證 WUD 能自動重建 bot，並確認 Discord 能回圖、尚未到期的夜盤樣本仍在。 [WUD Compose 更新文件](https://getwud.app/docs/configuration/triggers/docker-compose/)

## 平常怎麼用

| 要做什麼 | 在哪裡操作 |
| --- | --- |
| 等待自動更新 | 已部署 WUD 時，預設每小時整點檢查。想換頻率，見[自訂 WUD 排程](#自訂-wud-排程)。 |
| 立刻檢查並更新 | 已部署 WUD 時，在其目錄執行 `sudo sh ./check-and-update.sh`。有新映像就會重建 bot。 |
| 用 Compose 手動更新 | 在 Docker 主機的 bot 目錄執行 `sudo docker compose pull && sudo docker compose up -d`。 |
| 查看日誌 | 在對應的部署目錄執行 `sudo docker compose logs --tail 50 stock-bot` 或 `sudo docker compose logs --tail 50 wud`。 |
| 手動跑市場快報 | 在 Docker 主機的 bot 目錄執行 `sudo docker compose run --rm stock-bot python -m scripts.tw_market_report --config /app/config.toml`。 |

### 三大法人日報排程

`stock-bot-cron` 服務使用與 Bot 相同的映像，每週一至週五台灣時間 15:30 查詢證交所 BFI82U。有資料時，透過 `config.toml` 的 `[report.discord].webhook_url` 發送至 Discord。部署時需使用含此排程的新映像及新版 Compose。用 `sudo docker compose logs --tail 50 stock-bot-cron` 查看結果。

JSON 包含報表日期、狀態與各類法人及合計的買進、賣出、買賣差額，金額以新台幣元表示。休市或執行時當日資料尚未發布，會輸出 `no_data`。連線或解析失敗會記錄為排程錯誤。

Discord 以「股市小幫手」發送卡片，顯示外資及陸資、投信、自營商和三大法人合計的買賣超。法人成交比重以三大法人買賣金額合計除以當日 FMTQIK 大盤成交金額的兩倍，兩份報表的交易範圍可能有差異，因此標示為估算。若大盤成交金額無法取得，卡片仍會發送，該欄顯示「暫無資料」。

手動查詢並發送當日資料時，執行 `sudo docker compose exec stock-bot-cron python -m scripts.tw_institutional_flows`。可附上 `--date YYYY-MM-DD` 查詢並發送指定日期。

### 上市外資買賣超排行

`stock-bot-cron` 每週一至週五台灣時間 16:15 查詢證交所 TWT38U，透過同一個 Discord webhook 發送上市普通股與 ETF 的外資買超、賣超各前 10 名。排名採外資及陸資（不含外資自營商）的原始淨股數，卡片以張顯示。查無當日資料時跳過發送。

手動執行 `sudo docker compose exec stock-bot-cron python -m scripts.tw_foreign_rankings`，或加上 `--date YYYY-MM-DD` 查詢並發送指定日期。補發時以查詢當下的上市證券名冊篩選標的。

### 本機操作與設定

在本機安裝 uv，於 repo 根目錄放置 `config.toml`。先執行 `uv sync --locked` 安裝依賴，再依需要啟動 bot 或快報。

- 用 `uv run --locked stock-chart-bot --config config.toml` 啟動 bot。
- 用 `uv run --locked python -m scripts.tw_market_report --config config.toml` 手動跑快報。

快報會在台灣上班日透過 webhook 發送。行事曆無法查詢時會繼續執行。

- **查詢別名**在 `config.toml` 的 `[aliases]` 設定，以股票代碼或 `night` 為目標。格式見[設定範例](../config.example.toml)。
- **快報股票清單**在 [快報腳本](../scripts/tw_market_report.py) 的 `WATCHLIST`。上市用 `tse`，上櫃用 `otc`。容器要使用新清單時，請發布新映像。
- **夜盤樣本**預設是設定檔旁的 `data/night-samples.jsonl`。容器內的 `/app/data` 對應 `night-data` 資料卷。若自訂 `night.sample_file`，請將樣本留在該資料卷內。

## 有問題才看

### 容器無法連外

若 Docker 主機能解析 `discord.com`，但容器查 DNS 失敗，直接連外部 IP 的 TCP 443 也逾時，請查主機的轉送防火牆是否放行 Compose 專用網路。單獨指定 `dns` 只會改變查詢對象。

可以放行該子網的 DNS 和出站 HTTPS。若主機已放行 Docker 內建的 `bridge`，也可在對應的覆寫檔設定 `network_mode: bridge`。只有容器需要指定 DNS 時，才加上 `dns` 並填入容器可連到的 DNS 位址。 [Docker 網路文件](https://docs.docker.com/compose/how-tos/networking/) · [Compose DNS 設定](https://docs.docker.com/reference/compose-file/services/#dns)

| 服務 | 主機上的覆寫檔 | 設定位置 |
| --- | --- | --- |
| Bot | `stock-bot/compose.override.yaml` | `services.stock-bot` |
| WUD | `wud/compose.override.yaml` | `services.wud` |

覆寫檔放在各自的 `compose.yaml` 旁。從該目錄執行 `sudo docker compose config --quiet && sudo docker compose up -d`，Compose 就會合併設定並套用。實際 DNS、檔案權限做法和防火牆規則可記在該主機的維護筆記，重裝時一起還原本機覆寫檔。 [Compose 覆寫文件](https://docs.docker.com/compose/how-tos/multiple-compose-files/merge/)

### 自訂 WUD 排程

若想每 15 分鐘檢查，在 Docker 主機的 `wud/compose.override.yaml` 合併以下設定，保留現有的網路和 DNS 欄位。存檔後在 WUD 目錄執行 `sudo docker compose up -d wud`。 [WUD 排程文件](https://getwud.app/docs/configuration/watchers/)

```yaml
services:
  wud:
    environment:
      WUD_WATCHER_LOCAL_CRON: "*/15 * * * *"
```

### GHCR 私有映像

在 Docker 主機執行 `sudo docker login ghcr.io -u YOUR_GITHUB_USERNAME`，密碼使用對該套件有讀取權限、具 `read:packages` 的 classic PAT。若 WUD 也要自動更新私有映像，在 `wud/compose.override.yaml` 的 `services.wud.environment` 加入 `WUD_REGISTRY_GHCR_LOCAL_USERNAME` 和 `WUD_REGISTRY_GHCR_LOCAL_TOKEN`。 [WUD GHCR 認證](https://getwud.app/docs/configuration/registries/ghcr/)

### 從舊設定升級

- 若舊 Compose 的服務名是 `bot`，先用舊檔執行 `sudo docker compose stop bot` 和 `sudo docker compose rm -f bot`，再換新版。沿用原本的 Compose 專案目錄和專案名稱，可繼續使用 `night-data`。
- 若 bot 的 `config.toml` 原先放在部署目錄內，把它移到旁邊的 `stock-bot-private/`，再套用新版 Compose。舊的 `[report.index]`、`[[report.quotes]]` 和 `[[report.watchlist]]` 自訂內容移到快報腳本後，再從 TOML 移除。
- 若 WUD 管理員帳密原先放在 WUD 的覆寫檔，把值移到同目錄的 `.env`，再刪除覆寫檔裡的兩個帳密欄位。

要建置並發布新映像，請見[維護者發版手冊](releasing.md)。
