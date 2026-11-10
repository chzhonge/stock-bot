# dot-price-bot

在 Discord 查詢股票走勢、比較多檔股票的報酬率，或查看台指期夜盤。專案也提供一個可手動執行的台股市場快報，透過 Discord webhook 發送。

## Discord 查詢範例

在頻道提及 bot，後面加上股票代碼、別名或查詢區間。

| 訊息 | 回覆 |
| --- | --- |
| `@機器人 2330` | 台積電最新交易日的盤中圖 |
| `@機器人 AAPL 2y` | Apple 最近兩年的調整後收盤價走勢 |
| `@機器人 0050 2330 6mo` | 兩檔標的最近六個月的報酬率比較 |
| `@機器人 夜盤` | 台指期夜盤報價與可取得的走勢圖 |

## 本機快速開始

1. 準備 Python 3.11 和 uv。
2. 將 [config.example.toml](config.example.toml) 複製為 `config.toml`，在 `[discord]` 填入 bot token。若要執行快報，再填寫 `[report.discord]` 的 webhook URL。請妥善保管正式設定檔。
3. 在 Discord Developer Portal 啟用 **Message Content Intent**，並讓 bot 能在使用的頻道讀取和傳送訊息、嵌入連結及附加檔案。
4. 在專案根目錄安裝依賴並啟動 bot。

   ```sh
   uv sync --locked
   uv run --locked stock-chart-bot --config config.toml
   ```

若要手動執行一次市場快報，使用以下指令。快報在台灣上班日發送。

```sh
uv run --locked python -m scripts.tw_market_report --config config.toml
```

## NAS 部署

正式發布 GitHub Release 後，GitHub Actions 會從 Release tag 建置 `linux/amd64` Docker 映像，通過檢查後發布到 GHCR。[Compose 設定](compose.yaml) 使用 `ghcr.io/chzhonge/dot-price-bot:latest`。設定 WUD 的 Docker Compose trigger 後，WUD 會在偵測到映像更新時拉取新版本並重建 bot 容器。

首次部署、發版、WUD 設定，以及別名和快報股票清單的調整方式，請見[操作手冊](docs/maintenance.md)。
