# 維護者發版手冊

本流程用來發布 `chzhonge/stock-bot` 的新映像。要安裝 bot 或更新已部署的容器，請看[操作手冊](maintenance.md)。

## 1. 準備版本與發行說明

- 確認 `codex/architecture-refactor` 上要發版的 commit 已推送到 GitHub，並決定版本號。
- 準備 UTF-8 Markdown 發行說明。比較本次 commit 和上一個正式 tag。若是第一版，從本分支與原作者 `main` 的共同起點開始比較。
- 發行說明使用繁體中文。有相關變更才列「新功能」「修正」「部署與升級」。再用一句話整理本版最重要的變更，放在標題。

## 2. 建立 Release 草稿

準備 Python 3.11 和 GitHub CLI，用 `gh auth login --hostname github.com --web` 登入。從 repo 根目錄執行下列指令，將版本號、摘要和發行說明路徑換成這一版的值。

```sh
python tools/release_draft.py 1.0.1 --summary "本版重點" --notes-file release-notes.md
```

[發版腳本](../tools/release_draft.py) 會核對遠端 commit 和 tag，建立標題為 `stock-bot v<版本號> - <本版重點>` 的草稿，並印出草稿網址。

## 3. 發布並確認映像

1. 在 GitHub 開啟草稿，確認標題、說明和目標 commit，再按 **Publish release**。
2. 到 **Actions** 確認映像建置、兩個指令入口的檢查和 GHCR 發布都成功。Release tag 和 `latest` 應指向同一份 `linux/amd64` 映像。
3. 若已部署 WUD，可等下一次排程，或依[操作手冊](maintenance.md#平常怎麼用)手動觸發更新。確認 bot 重新上線並能在 Discord 回圖。
