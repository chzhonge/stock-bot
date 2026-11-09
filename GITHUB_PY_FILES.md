# GitHub Python Files Notes

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

主要 Python 檔案:

```text
TW_stock.py
tw_stock_chart_bot.py
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
git add TW_stock.py
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

Python 套件寫在:

```text
requirements.txt
```

目前常用套件:

```text
requests
yfinance
discord.py
matplotlib
beautifulsoup4
```

如果換新機器或環境，要先安裝:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pip install beautifulsoup4
```

補充:

- Debian / Ubuntu 新機器如果直接用 `python3 -m pip install ...` 可能會遇到 `externally-managed-environment`
- 這種情況改用 `.venv` 最穩定

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

啟動方式:

```bash
source .venv/bin/activate
export DISCORD_TOKEN='你的 Discord Bot Token'
python tw_stock_chart_bot.py
```

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
- 本地暫存檔:

```text
/tmp/taifex_tx_night_samples.jsonl
```

- 再將累積樣本聚成 5 分 K 棒圖

補充:

- Yahoo `WTX&` 目前可穩定抓到當下摘要欄位，例如成交、漲跌、開高低、昨收
- 但沒有直接抓到可用的完整夜盤分時序列 API
- 所以夜盤走勢圖仍然主要依賴 bot 本地每分鐘累積樣本
- bot 剛重啟後，夜盤圖會先比較短，跑久一點後才會變完整

限制:

- 不是直接抓到整晚完整歷史分 K API
- 所以 bot 剛啟動時，夜盤圖可能只有 1 根或少數幾根
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
Environment=DISCORD_TOKEN=你的新DiscordBotToken
ExecStart=/home/twnoc/liaob/DClab/.venv/bin/python /home/twnoc/liaob/DClab/tw_stock_chart_bot.py
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
Environment=DISCORD_TOKEN=你的新DiscordBotToken
ExecStart=/home/twnoc/liaob/DClab/.venv/bin/python /home/twnoc/liaob/DClab/tw_stock_chart_bot.py
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
- 換新 token 後，要同步更新 service 設定再重啟

## 注意事項

不要上傳 Python 暫存檔:

```text
__pycache__/
*.pyc
```

不要把密碼、token、Discord webhook、API key 直接寫進公開 repo。

如果有新增機密資料，建議改用環境變數或 GitHub Secrets。

## 檔名提醒

固定使用:

```text
TW_stock.py
```

不要再使用之前拼錯的:

```text
TW-sotck.py
```
