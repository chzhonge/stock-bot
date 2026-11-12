# stock-bot

在 Discord 查詢股票走勢、比較多檔股票的報酬率，或查看台指期夜盤。專案也提供一個可手動執行的台股市場快報，透過 Discord webhook 發送。

## Discord 查詢範例

在 Discord 輸入 `/stock-bot` 選擇指令，或在頻道提及 bot 並加上查詢內容。

| 斜線指令 | 提及機器人 | 回覆 |
| --- | --- | --- |
| `/stock-bot help` | `@機器人 help` | 查詢說明。斜線指令僅自己可見，提及機器人則在頻道公開回覆 |
| `/stock-bot chart-help` | `@機器人 chart-help` | 圖表手冊。選擇圖表類型，查看示範圖、讀法與查詢範例 |
| `/stock-bot quote 代碼:2330` | `@機器人 2330` | 台積電最新交易日的盤中圖 |
| `/stock-bot quote 代碼:AAPL 區間:2y` | `@機器人 AAPL 2y` | Apple 最近兩年的調整後收盤價走勢 |
| `/stock-bot index 指數:大盤 區間:6mo` | `@機器人 大盤 6mo` | 台灣加權指數近六個月的走勢 |
| `/stock-bot compare 代碼:0050 2330 區間:6mo` | `@機器人 0050 2330 6mo` | 兩檔標的最近六個月的報酬率比較 |
| `/stock-bot night` | `@機器人 夜盤` | 台指期夜盤報價與可取得的走勢圖 |

比較時，在「代碼」欄位用空格分隔 2 至 5 個標的。省略區間時預設比較最近一年。

比較圖以第一個共同交易日為 0%。`compare` 和 `quote` 的歷史查詢可選「報酬」。預設「含息報酬」使用 Yahoo 原幣調整後收盤價，配息按除息參考價估算再投入。「價格報酬」使用收盤價，配息不計入。兩種模式都使用分割調整後的價格，未納入稅費或匯率。價格型指數仍以指數點位變動呈現。

例如 `/stock-bot compare 代碼:0050 0056 區間:1y 報酬:價格報酬`。單一標的可用 `/stock-bot quote 代碼:0056 區間:1y 報酬:價格報酬`。選擇報酬模式時，`quote` 需要填寫歷史區間。`@機器人` 的歷史查詢沿用含息報酬。

`index` 的「指數」欄位可搜尋名稱、別名或代碼，例如 `大盤`、`sp500`、`費半` 或 `^IXIC`。建議清單使用目前的指數別名設定。省略區間時顯示最新交易日的盤中圖。

圖表手冊涵蓋單一標的盤中與歷史走勢、多標的比較及台指期夜盤。斜線指令開啟的手冊僅自己可見，提及機器人則在頻道公開顯示。選單由開啟手冊的人操作。

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

正式發布 GitHub Release 後，GitHub Actions 會從 Release tag 建置 `linux/amd64` Docker 映像，通過檢查後發布到 GHCR。[Compose 設定](compose.yaml) 使用 `ghcr.io/chzhonge/stock-bot:latest`。設定 WUD 的 Docker Compose trigger 後，WUD 會在偵測到映像更新時拉取新版本並重建 bot 容器。

首次部署、發版、WUD 設定，以及別名和快報股票清單的調整方式，請見[操作手冊](docs/maintenance.md)。
