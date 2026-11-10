# 股票工具操作手冊

Discord bot 提供股票與夜盤查詢。市場快報是可手動執行的一次性指令，兩者共用 `config.toml`。

## 首次部署

1. 依照下方「發版與更新」發布第一個 Release，確認 GitHub Actions 成功產生 `ghcr.io/chzhonge/stock-bot:latest`。
2. 把 `compose.yaml` 放到 NAS 的部署目錄，例如 `/volume1/docker/stock-bot/`。在同一層建立 `stock-bot-private/`，把 [config.example.toml](../config.example.toml) 複製成 `/volume1/docker/stock-bot-private/config.toml`。填寫 `[discord]` 的 token，若要執行快報，再填 `[report.discord]` 的 webhook。若先前已部署，將原本的 `config.toml` 搬到新位置，再用下方的 Compose 指令套用掛載變更。
3. 在 Discord Developer Portal 啟用 **Message Content Intent**，並讓 bot 能在使用的頻道讀取和傳送訊息、嵌入連結及附加檔案。
4. 在 NAS 上將 `config.toml` 的讀取權限限制給管理者和容器的 UID/GID `10001`。Compose 會將它唯讀掛載到 `/app/config.toml`。若 GHCR 套件為私有，先用 `docker login ghcr.io -u YOUR_GITHUB_USERNAME` 登入。密碼提示請貼上可讀取該套件且具 `read:packages` 權限的 classic PAT。

在 NAS 部署目錄執行以下指令。上線後，可以在 Discord 試 `@機器人 2330`、`@機器人 0050 2330 6mo` 或 `@機器人 夜盤`。

```sh
docker compose config --quiet
docker compose pull stock-bot
docker compose up -d stock-bot
docker compose logs --tail 50 stock-bot
```

若 NAS 已用舊版 Compose 啟動 `bot` 服務，先用舊的 `compose.yaml` 執行 `docker compose stop bot` 和 `docker compose rm -f bot`。再換上新版 Compose，從原本的專案目錄以同一個 Compose 專案名稱啟動 `stock-bot`，即可沿用 `night-data` 資料卷和原有映像。

### NAS 容器無法連外

若 NAS 本身能解析 `discord.com`，但容器查 DNS 失敗、直接連外部 IP 的 TCP 443 也逾時，先查 NAS 的轉送防火牆是否放行 Compose 專用網路的子網。單獨指定 `dns` 只會改變查詢對象，容器仍會使用原來的網路。

可在 NAS 防火牆放行該子網所需的 DNS 和出站 HTTPS。若防火牆已放行 Docker 內建的 `bridge`，也可在 NAS 本機的 `stock-bot` 服務設定 `network_mode: bridge`，並視需要用 `dns` 指定容器可連到的 DNS 伺服器。將這些環境專用的設定留在 WUD 讀取的 NAS Compose 檔。 [Docker 網路文件](https://docs.docker.com/compose/how-tos/networking/) · [Compose DNS 設定](https://docs.docker.com/reference/compose-file/services/#dns)

## 發版與更新

### 發布映像

1. 在 `codex/architecture-refactor` 分支確認要發版的 commit 已推送到 `chzhonge/stock-bot`。
2. 準備 UTF-8 Markdown 發行說明。有內容才保留「新功能」「修正」「部署與升級」等章節。第一次發版以本分支和原作者 `main` 的共同起點為基準，之後以上一個正式 tag 為基準。
3. 安裝 GitHub CLI 並用 `gh auth login --hostname github.com --web` 登入。在專案根目錄執行下方指令，提供本版的一句話重點和發行說明的路徑。[腳本](../tools/release_draft.py) 會確認目前 commit 已推送到 GitHub，並用 `stock-bot v<版本號> - <本版重點>` 作為草稿標題。

   ```sh
   python tools/release_draft.py 1.0.0 --summary "Discord 查詢改版與 NAS 自動部署" --notes-file release-notes.md
   ```

4. 開啟腳本印出的草稿網址，確認標題、說明和目標 commit，再按 **Publish release**。到 **Actions** 查看結果。兩個指令入口通過檢查後，同一份 `linux/amd64` 映像會以 Release tag 和 `latest` 發布到 GHCR。

### 設定 WUD

將 [WUD 的 Compose 範本](../deploy/wud/compose.yaml) 複製到 NAS 上獨立的 WUD 目錄，檔名保留 `compose.yaml`。例如 bot 放在 `/volume1/docker/projects/stock-bot/`，WUD 放在同一層的 `wud/`。Bot 的 Compose 和建置用的 Dockerfile 都留在 repo 根目錄。

在 WUD 目錄內建立 `.env`，填入 NAS 上存放 bot 的 `compose.yaml` 的絕對目錄。路徑末尾省略 `/`。

```dotenv
STOCK_BOT_COMPOSE_DIR=/volume1/docker/projects/stock-bot
```

WUD 透過 Docker socket 管理容器。範本會掛載 bot 的部署目錄供 WUD 更新 Compose，含憑證的 `stock-bot-private/` 應留在這個目錄之外。範本關閉網頁和 HTTP API，並只監看標有 `wud.watch: "true"` 的容器。

若 NAS 的防火牆只放行 Docker 內建的 `bridge`，在 WUD 目錄新增本機 `compose.override.yaml`。需要指定 DNS 時，把範例位址換成容器可連到的 DNS。Compose 啟動時會合併這份檔案。

```yaml
services:
  wud:
    network_mode: bridge
    dns:
      - 192.0.2.53
```

若映像為私有，在本機 `compose.override.yaml` 的 `wud.environment` 加入 `WUD_REGISTRY_GHCR_LOCAL_USERNAME` 和 `WUD_REGISTRY_GHCR_LOCAL_TOKEN`。在 NAS 的 WUD 目錄啟動並查看日誌。

```sh
sudo docker compose config --quiet && sudo docker compose up -d wud
sudo docker compose logs --tail 50 -f wud
```

先確認 WUD 能正常檢查 `stock-bot`。下次正式版發布後，確認 WUD 偵測到 `latest` 的 digest 改變、容器已重建、bot 重新上線，且尚未到期的夜盤樣本仍在。

參考 [WUD Compose trigger](https://getwud.app/docs/configuration/triggers/docker-compose/) 和 [WUD GHCR 認證](https://getwud.app/docs/configuration/registries/ghcr/)。

## 日常操作

在本機安裝 uv 後，從專案根目錄啟動 bot 或手動執行一次市場快報。

```sh
uv sync --locked
uv run --locked stock-chart-bot --config config.toml
uv run --locked python -m scripts.tw_market_report --config config.toml
```

NAS 上可用現有映像手動執行快報。快報在台灣上班日發送。若行事曆來源無法查詢，會繼續執行。

```sh
docker compose run --rm stock-bot python -m scripts.tw_market_report --config /app/config.toml
```

- **查詢別名**在 `config.toml` 的 `[aliases]` 調整，以股票代碼或 `night` 作為對應目標。格式可參考 [設定範例](../config.example.toml)。
- **快報股票清單**在 [快報腳本](../scripts/tw_market_report.py) 的 `WATCHLIST` 調整。上市用 `tse`，上櫃用 `otc`。NAS 要用到新清單時，依前面的發版步驟更新映像。
- **夜盤樣本**預設位於設定檔旁的 `data/night-samples.jsonl`。NAS 將 `/app/data` 存在 `night-data` 資料卷中。自訂 `night.sample_file` 時，請把路徑留在這個資料卷內。

若從舊版升級，將 `[report.index]`、`[[report.quotes]]` 或 `[[report.watchlist]]` 的自訂內容移到快報腳本，再從 TOML 移除這些舊區段。
