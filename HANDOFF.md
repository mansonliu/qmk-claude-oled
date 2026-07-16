# HANDOFF — QMK 鍵盤 OLED 顯示 Claude Code 模型狀態

> 給未來的 Claude：讀完後請依文末「下次接續的開頭」段落執行。

## 任務目標

讓使用者的 QMK 鍵盤（帶 OLED 小螢幕，原本顯示鍵層與圖片）即時顯示 Claude Code 目前使用的模型名稱（如 Fable 5、Opus 4.8），未來可擴充顯示 agent 狀態（工作中／等確認／出錯）。

靈感來源：OpenAI × Work Louder 的 Codex Micro 巨集鍵盤（LED 顯示 agent 狀態），報導見 https://www.hot3c.com/read.asp?class=11&id=27624

## 架構（已定案）

```
Claude Code statusline（stdin JSON 含 model.display_name）
      → host 端腳本（寫狀態檔或直接呼叫）
      → Raw HID（僅 USB 有效，藍牙不行）
      → QMK 韌體 raw_hid_receive() → oled_task_user() 畫到 OLED
```

## 目前進度

- [x] 可行性確認：QMK Raw HID 是社群顯示 host 資訊的標準做法
- [x] 調研現成專案（2026-07-16，見下方參考資料）——結論：兩個半段各有成熟專案，但「Claude Code 模型名 → QMK OLED」完整組合沒人做過，需自己寫膠水
- [ ] P0：等鍵盤到手，確認：型號、韌體是否 VIA、OLED 解析度、keymap 原始碼位置
- [ ] P1：選定 host 端框架（候選見下）並打通 Raw HID 顯示任意字串
- [ ] P1：寫 Claude Code statusline 腳本把 model.display_name 餵給 host 端
- [ ] P2：多 session 行為（暫定：最後有動作的 session 蓋掉顯示）
- [ ] P2：agent 狀態顯示（等確認／工作中），可參考 blinkstick-claude 的 hooks 接法
- [ ] P3：部署到其他機器（host 腳本每台插鍵盤的機器都要裝）

## 關鍵決策摘要

| 決策點 | 結論 |
|---|---|
| 鍵盤怎麼知道模型 | 韌體自己不可能知道，必須 host 端經 Raw HID 推送 |
| 連線方式 | Raw HID 只支援 USB；藍牙模式下此功能無效 |
| Claude Code 端掛載點 | statusline（每次回覆更新、JSON 自帶 model.display_name），不用常駐程式；agent 狀態才用 hooks |
| VIA 衝突 | 若韌體開 VIA_ENABLE，Raw HID 通道被 VIA 佔用，要用 VIA custom command 包資料或關 VIA |
| host 框架傾向 | 主力機是 macOS：先試 qmk-oled-api（Rust、可畫圖）或 Klathmon/qmk-hid-display（Node、明確支援 macOS）；zzeneg/qmk-hid-host 最好擴充但 macOS 僅部分支援 |
| 資料落點 | GitHub repo（純程式碼、跨機器、可公開），不放 OneDrive |

## 重要參考資料

現成專案（2026-07-16 調研）：

- https://github.com/danielrosehill/Claude-Macropad-V2 — 專為 Claude Code 做的巨集鍵盤（ESP32/RP2040 非 QMK），host 驅動狀態 LED，hooks 接法可參考
- https://github.com/jondkinney/blinkstick-claude — Claude Code hooks（UserPromptSubmit/Stop/PermissionRequest/PostToolUse）→ HID LED 裝置，含多 session 識別
- https://github.com/zzeneg/qmk-hid-host — Rust host 常駐程式，enum data ID 設計最好擴充；macOS 部分支援
- https://github.com/Klathmon/qmk-hid-display — Node.js host，支援 macOS/Windows
- https://github.com/dob9601/qmk-oled-api — Rust crate，host 直接把 OLED 當畫布畫圖，韌體端只貼一小段
- https://docs.qmk.fm/features/rawhid — QMK Raw HID 官方文件
- https://code.claude.com/docs/en/statusline — Claude Code statusline 官方文件

## 下次接續的開頭

使用者說「請讀 HANDOFF.md，繼續 QMK OLED 顯示 Claude 模型」即接手。第一步是問到鍵盤型號與韌體狀況（P0 那行的四項），再決定 host 框架。工作目錄：`cd ~/git/qmk-claude-oled`。
