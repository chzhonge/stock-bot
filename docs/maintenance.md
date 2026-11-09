# 股票工具維護手冊

這個專案有兩個執行入口。常駐 Discord bot 接收股票與夜盤查詢，一次性快報則在台灣上班日產生市場摘要並透過 Discord webhook 發送。兩支程式共用行情模組、繪圖程式和一份 TOML 設定。

## 安裝與設定

安裝 uv 後，在專案根目錄同步環境。專案預設使用 Python 3.11，依賴版本由 `uv.lock` 鎖定。

```bash
uv sync --locked
```

複製 [config.example.toml](../config.example.toml) 為 `config.toml`，再填寫要執行的功能所需的區段。

| 區段 | 用途 |
| --- | --- |
| `[discord]` | 常駐 bot 的 token 和顯示暱稱 |
| `[quotes]` | 等待佇列容量、行情請求逾時和查詢期限 |
| `[night]` | Yahoo 與期交所夜盤網址、查詢別名和樣本檔路徑 |
| `[report.discord]` | 快報 webhook 和可選的通知對象 ID |
| `[report.index]` | 快報的指數代碼、顯示名稱和圖表標題 |
| `[report.sources]` | 快報使用的證交所、CNN 和台灣行事曆網址 |

兩支程式各自驗證需要的欄位。只跑 bot 時可以將快報 webhook 留空，只跑快報時可以將 bot token 留空。正式的 `config.toml` 含有憑證，已列入 Git 忽略清單。若使用其他檔名，請將正式設定放在專案目錄外。

## 啟動 Discord bot

在 Discord Developer Portal 啟用 **Message Content Intent**，並給 bot 所用頻道的訊息讀取、發送、嵌入連結與附件權限。在專案根目錄執行：

```bash
uv run --locked python main.py --config config.toml
```

也可以用 `uv run --locked stock-chart-bot --config config.toml` 啟動同一支 bot。上線後，在 Discord 傳送 `@機器人 2330`、`@機器人 0050`、`@機器人 AAPL` 或 `@機器人 夜盤`。

Bot 一次只處理一筆取價。預設最多 4 筆等待，取價、繪圖和回覆中的查詢合計最多 5 筆。達到任一上限就回覆忙碌。排隊和取價共用 30 秒期限。圖表直接產生 PNG 附件。

### 夜盤樣本

夜盤報價優先使用 Yahoo `WTX&`，失敗時改查期交所 TX。Bot 在台灣時間 15:00 至隔天 05:00 每分鐘取樣，並將樣本聚合成 5 分鐘 K 線。樣本不足時會回傳單根摘要 K 線。

預設樣本檔為 `data/night-samples.jsonl`。相對路徑以 `config.toml` 所在目錄為準。首次取樣與之後每小時會清除超過 16 小時的舊資料。使用 Docker 時，可唯讀掛載設定檔，並把 `night.sample_file` 指向持久資料卷，例如 `/data/night-samples.jsonl`。

## 執行市場快報

在 `[report.discord]` 填寫 webhook。快報的個股與 ETF 清單定義在 [scripts/tw_market_report.py](../scripts/tw_market_report.py) 的 `WATCHLIST`。新增標的時加一筆 `WatchlistEntry`，上市使用 `tse`，上櫃使用 `otc`。清單按順序查詢及顯示。

```bash
uv run --locked python -m scripts.tw_market_report --config config.toml
```

此指令會在台灣上班日發送一則快報。若行事曆無法查詢，快報會依預設繼續執行。若從舊版設定升級，請將 `[[report.quotes]]` 或 `[[report.watchlist]]` 裡的自訂標的搬到腳本的 `WATCHLIST`，再移除舊設定區段。

## 專案位置與維護

| 路徑 | 用途 |
| --- | --- |
| `main.py` | 常駐 bot 的根目錄入口 |
| `scripts/tw_market_report.py` | 一次性快報的入口與股票清單 |
| `src/stock_bot/bot/` | Discord 事件、查詢佇列和夜盤取樣流程 |
| `src/stock_bot/report/` | 快報流程、資料來源和 webhook 發送 |
| `src/stock_bot/market/` | 共用盤中取價、夜盤查詢與樣本存取 |
| `src/stock_bot/config.py`、`src/stock_bot/charts.py` | TOML 驗證與 PNG 繪圖 |
| `pyproject.toml`、`uv.lock` | 專案依賴與鎖定版本 |

新增依賴用 `uv add 套件名稱`。更新既有套件用 `uv lock --upgrade-package 套件名稱`。更新後執行 `uv sync --locked`，並把依賴宣告和鎖定檔的變更一併提交。
