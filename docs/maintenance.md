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
docker compose pull bot
docker compose up -d bot
docker compose logs --tail 50 bot
```

## 發版與更新

### 發布映像

1. 將包含 Dockerfile 和 workflow 的 `codex/architecture-refactor` 分支推送到 GitHub。
2. 建立 Release 時新增 tag（例如 `v0.1.0`），在 **Target** 選 `codex/architecture-refactor`。若選用既有 tag，確認它指向包含部署設定的 commit。
3. 按 **Publish release** 發布正式版，再到 **Actions** 查看結果。Workflow 會從 tag 指向的 commit 建置 `linux/amd64` 映像。兩個指令入口的檢查通過後，同一份映像會以 Release tag 和 `latest` 發布到 GHCR。

### 設定 WUD

把下面的設定合併到 NAS 現有的 WUD 服務，保留原有 Docker socket 掛載。將範例路徑換成實際部署目錄，只掛載 `stock-bot/`，讓 WUD 以同樣的絕對路徑讀寫 Compose 檔。含憑證的 `stock-bot-private/` 留在掛載範圍外。WUD 能透過 Docker socket 管理容器，管理介面請只開放給管理者透過內網或 VPN 使用。

```yaml
volumes:
  - /volume1/docker/stock-bot:/volume1/docker/stock-bot
environment:
  WUD_TRIGGER_DOCKERCOMPOSE_DOTPRICEBOT_FILE: /volume1/docker/stock-bot/compose.yaml
  WUD_TRIGGER_DOCKERCOMPOSE_DOTPRICEBOT_INCLUDEBYDEFAULT: "false"
  WUD_TRIGGER_DOCKERCOMPOSE_DOTPRICEBOT_ONDIGEST: "true"
  WUD_TRIGGER_DOCKERCOMPOSE_DOTPRICEBOT_AUTO: "true"
```

若套件為私有，在 WUD 設定 `WUD_REGISTRY_GHCR_LOCAL_USERNAME` 和 `WUD_REGISTRY_GHCR_LOCAL_TOKEN`。套用後確認 WUD 看得到 `bot`。下次正式版發布後，確認 WUD 偵測到 `latest` 的 digest 改變、容器已重建、bot 重新上線，且尚未到期的夜盤樣本仍在。想先從 WUD 介面手動觸發，可把 `AUTO` 設成 `"false"`。

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
docker compose run --rm bot python -m scripts.tw_market_report --config /app/config.toml
```

- **查詢別名**在 `config.toml` 的 `[aliases]` 調整，以股票代碼或 `night` 作為對應目標。格式可參考 [設定範例](../config.example.toml)。
- **快報股票清單**在 [快報腳本](../scripts/tw_market_report.py) 的 `WATCHLIST` 調整。上市用 `tse`，上櫃用 `otc`。NAS 要用到新清單時，依前面的發版步驟更新映像。
- **夜盤樣本**預設位於設定檔旁的 `data/night-samples.jsonl`。NAS 將 `/app/data` 存在 `night-data` 資料卷中。自訂 `night.sample_file` 時，請把路徑留在這個資料卷內。

若從舊版升級，將 `[report.index]`、`[[report.quotes]]` 或 `[[report.watchlist]]` 的自訂內容移到快報腳本，再從 TOML 移除這些舊區段。
