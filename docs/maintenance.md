# 股票工具維護手冊

這份文件專門記錄 GitHub 上 Python 檔案的常用操作。

## 目前 Repo

GitHub:

```text
git@github.com:c224456k/dot-price-bot.git
```

本地路徑:

```text
/home/twnoc/liaob/DClab
```

專案目錄

```text
src/stock_bot/bot/           常駐 bot 的入口、Discord 事件、Service 和 Repository
src/stock_bot/report/        快報的入口、Service、Repository 和 webhook 發送
src/stock_bot/market/        共用 Yahoo 取價、夜盤查詢與樣本存取
src/stock_bot/config.py      共用 TOML 設定與驗證
src/stock_bot/charts.py      共用 Matplotlib 繪圖
tw_stock_chart_bot.py        常駐 bot 的原啟動入口
scripts/tw_market_report.py  一次性快報的原啟動入口
docs/                        維護與部署說明
config.example.toml          Bot 與市場快報的共用設定範例
pyproject.toml               Python 依賴宣告
uv.lock                      依賴版本鎖定檔
```

## 更新到 GitHub

修改完 Python 檔案後，進入 repo:

```bash
cd /home/twnoc/liaob/DClab
```

查看狀態:

```bash
git status
```

加入要上傳的檔案，例如:

```bash
git add scripts/tw_market_report.py
```

建立 commit:

```bash
git commit -m "Update TW stock script"
```

推送到 GitHub:

```bash
git push origin main
```

## 從 GitHub 更新本地

如果 GitHub 上有新版本，要拉回本地:

```bash
cd /home/twnoc/liaob/DClab
git pull
```

## 套件管理

專案使用 uv 管理套件。`pyproject.toml` 宣告依賴，`uv.lock` 鎖定安裝版本，`.python-version` 指定預設使用 Python 3.11。

安裝 uv 後，在 repo 根目錄建立或更新 `.venv`：

```bash
uv sync --locked
```

新增依賴時用 `uv add 套件名稱`。更新既有套件時用 `uv lock --upgrade-package 套件名稱`，並提交更新後的 `uv.lock`。

使用下面的 `systemd` 設定時，先執行 `uv sync --locked`，服務會直接使用 `.venv` 裡的 Python。

## 一次性台股快報

複製 `config.example.toml` 為 `config.toml`，在 `[report.discord]` 填入快報 webhook。常駐 bot 和快報共用這個檔案，各自驗證用到的區段。正式設定檔應限制讀取權限，並保存在 Git 之外。

- `[report.discord]` 設定發送目的地與可選的通知對象。
- `[report.index]` 設定 Yahoo Finance 指數代碼、快報名稱和圖表標題。
- `[[report.quotes]]` 可重複列出要查詢的台股或 ETF，`exchange` 用 `tse` 或 `otc`。
- `[report.sources]` 設定證交所、CNN 與台灣行事曆的網址。Yahoo Finance 連線由 `yfinance` 管理。

```bash
uv run --locked tw-market-report --config config.toml
```

## Discord 股票圖 Bot

新增檔案:

```text
tw_stock_chart_bot.py
```

用途:

- 在 Discord 內 `@機器人 2330`
- 或 `@機器人 0050`
- 或 `@機器人 00631L`
- 或 `@機器人 00981A`
- 或 `@機器人 AAPL`
- 或 `@機器人 TSLA`
- 或 `@機器人 VOO`
- 或 `@機器人 BRK.B`
- 機器人會直接回該股票 / ETF 的當下趨勢圖

目前支援:

- 台股代碼，例如 `2330`、`0050`、`006208`、`00631L`
- 美股代碼，例如 `AAPL`、`TSLA`、`VOO`、`BRK.B`
- Bot 在 Discord 伺服器內會嘗試把暱稱改成 `股市小幫手`

在共用的 `config.toml` 填入 `[discord]` 的 `token`。`[night]` 設定夜盤網址、查詢別名與樣本檔路徑。既有設定檔可參照範例補上 `yahoo_url`、`taifex_url` 和 `aliases`。

```bash
uv run --locked stock-chart-bot --config config.toml
```

Bot 會依序處理取價。預設允許 4 筆等待，並限制取價、繪圖與回覆中的查詢合計最多 5 筆。達到任一上限就立即回覆忙碌。排隊和取價共用 30 秒期限，取價完成後才開始繪圖。

若用 Docker 部署，將正式設定檔以唯讀方式掛載，並把 `night.sample_file` 設為掛載資料卷內的路徑，例如 `/data/night-samples.jsonl`。

注意:

- 需要在 Discord Developer Portal 開啟 `Message Content Intent`
- bot 要有讀取頻道訊息與發訊息權限
- 這是 Discord bot，不適合用 GitHub Actions 當常駐服務

## 夜盤功能

目前 `tw_stock_chart_bot.py` 已支援:

```text
@機器人 夜盤
@機器人 台指夜盤
@機器人 台指
@機器人 TX
@機器人 TXF
@機器人 TXF1
@機器人 WTXP
```

目前邏輯:

- 夜盤即時摘要優先抓 Yahoo `WTX&`
- 如果 Yahoo 該次抓取失敗，fallback 回期交所官方 TX 夜盤資料
- 若樣本不足，先回單根夜盤摘要 K 棒
- bot 在線時，會每分鐘抓一次夜盤最新價
- 樣本存到 `night.sample_file`。範例路徑相對於設定檔所在的目錄。

```text
data/night-samples.jsonl
```

- 再將累積樣本聚成 5 分 K 棒圖

補充:

- Yahoo `WTX&` 目前可穩定抓到當下摘要欄位，例如成交、漲跌、開高低、昨收
- 但沒有直接抓到可用的完整夜盤分時序列 API
- 所以夜盤走勢圖仍然主要依賴 bot 本地每分鐘累積樣本
- 夜盤樣本只使用最近 16 小時的資料。首次取樣與之後每小時會清除過期資料。更換路徑時，可先把舊樣本檔搬到新位置。

限制:

- 不是直接抓到整晚完整歷史分 K API
- 樣本不足時，夜盤圖可能只有 1 根或少數幾根
- 跑越久，夜盤 5 分 K 圖會越完整

如果未來要更完整的夜盤多根 K:

- 要改接有歷史分時資料的資料源
- 或維持 bot / 收集器長時間在線累積樣本

## Discord Bot 常駐方式

目前 `tw_stock_chart_bot.py` 已改成用 `systemd` 常駐執行。

service 名稱:

```text
tw-stock-chart-bot.service
```

用途:

- 關掉 MobaXterm 後 bot 仍會繼續在線
- 開機後可自動啟動
- 當 bot 異常退出時會自動重啟

常用指令:

```bash
systemctl status --no-pager tw-stock-chart-bot.service
systemctl enable --now tw-stock-chart-bot.service
systemctl restart tw-stock-chart-bot.service
systemctl stop tw-stock-chart-bot.service
systemctl disable tw-stock-chart-bot.service
```

目前建議的 service 內容:

```ini
[Unit]
Description=Discord Taiwan Stock Chart Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/twnoc/liaob/DClab
ExecStart=/home/twnoc/liaob/DClab/.venv/bin/python /home/twnoc/liaob/DClab/tw_stock_chart_bot.py --config /home/twnoc/liaob/DClab/config.toml
Restart=always
RestartSec=5
StandardOutput=append:/home/twnoc/liaob/DClab/tw_stock_chart_bot.log
StandardError=append:/home/twnoc/liaob/DClab/tw_stock_chart_bot.log

[Install]
WantedBy=multi-user.target
```

建立 service 檔可直接用:

```bash
sudo tee /etc/systemd/system/tw-stock-chart-bot.service > /dev/null <<'EOF'
[Unit]
Description=Discord Taiwan Stock Chart Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/home/twnoc/liaob/DClab
ExecStart=/home/twnoc/liaob/DClab/.venv/bin/python /home/twnoc/liaob/DClab/tw_stock_chart_bot.py --config /home/twnoc/liaob/DClab/config.toml
Restart=always
RestartSec=5
StandardOutput=append:/home/twnoc/liaob/DClab/tw_stock_chart_bot.log
StandardError=append:/home/twnoc/liaob/DClab/tw_stock_chart_bot.log

[Install]
WantedBy=multi-user.target
EOF
```

提醒:

- `EOF` 那一行要最左邊頂格，前面不能有空白
- 建議同一時間只保留一台機器跑這個 bot，避免 Discord 重複回覆

log 檔:

```text
/home/twnoc/liaob/DClab/tw_stock_chart_bot.log
```

查看 log:

```bash
sed -n '1,120p' /home/twnoc/liaob/DClab/tw_stock_chart_bot.log
```

提醒:

- Discord bot token 不建議直接寫死或公開
- 如果 token 有外洩，請去 Discord Developer Portal 重新產生新 token
- 換新 token 後，更新 `config.toml` 再重啟服務

## 注意事項

不要上傳 Python 暫存檔:

```text
__pycache__/
*.pyc
```

不要把密碼、token、Discord webhook、API key 直接寫進公開 repo。

如果有新增機密資料，建議改用環境變數或 GitHub Secrets。
