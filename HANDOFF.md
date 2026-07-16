# HANDOFF — QMK 鍵盤 OLED 顯示 Claude Code 模型狀態

> 給未來的 Claude：讀完後請依文末「下次接續的開頭」段落執行。

## 任務目標

讓使用者的 QMK 鍵盤（帶 OLED 小螢幕）即時顯示 Claude Code 目前使用的模型名稱
（如 Fable 5、Opus 4.8）與 agent 狀態（工作中／等確認／出錯），按鍵兼作 Claude Code 操控鍵。

靈感來源：OpenAI × Work Louder 的 Codex Micro（LED 顯示 agent 狀態），
https://www.hot3c.com/read.asp?class=11&id=27624

## 架構（已實作）

```
Claude Code statusline（model.display_name + cwd）＋ hooks（agent 狀態）
      → host/zima_push.py（Python + hidapi，best-effort 靜默失敗）
      → USB Raw HID（usage page 0xFF60 / usage 0x61，32-byte report）
      → QMK raw_hid_receive() → OLED 顯示 + RGB 底光變色 + waiting 時震動
```

細節（協定、鍵位、OLED 版面、狀態表）見 README.md。

## 目前進度（2026-07-16，Mac Mini）

- [x] P0 鍵盤確認：**splitkb Zima**（4×3 + 旋鈕 + OLED 128×32 + RGB + 震動 + 蜂鳴器，
      atmega32u4 / atmel-dfu）。原韌體＝舊版 QMK 預設 keymap（VID 0xFEED），非 VIA/Vial
      → Raw HID 通道沒被佔用，直接刷自製韌體，VIA 衝突問題不存在
- [x] P1 韌體：`~/git/vial-qmk/keyboards/splitkb/zima/keymaps/claude/`
      編譯過（26502/28672，92%，audio/haptic/rgb 全保留）
- [x] P1 host 端：不用現成框架，自寫 `host/zima_push.py`（hidapi 直推，約 60 行核心）
      — 調研過的 qmk-hid-host 等全是常駐程式，對「statusline 事件驅動推送」反而多餘
- [x] P1 statusline：settings.json 已掛 `statusLine`（同一支腳本 statusline 模式，
      印 `模型 | cwd` 並推送 CMD_MODEL + CMD_INFO）
- [x] P2 agent 狀態：hooks 已掛 UserPromptSubmit→working、Stop→idle、
      Notification→waiting、SessionEnd→idle（皆 async + 靜默失敗）
- [x] 刷韌體成功（2026-07-16，dfu-programmer 0x6800 bytes）；新韌體以 VID 0x8D1D
      重新列舉、Raw HID 介面（0xFF60/0x61）出現，host 推送 model/status 皆成功送達
- [ ] 使用者目視確認 OLED/RGB/震動 實際效果 + 用一陣子的鍵位/亮度回饋
- [ ] P2 多 session：暫定 last-write-wins（已是天然行為，觀察夠不夠用）
- [ ] P3 部署其他機器：host 腳本 + hidapi + settings 掛載（README 有步驟）；
      settings.json 是機器專屬檔不進共享池，各機自行加

## 關鍵決策摘要

| 決策點 | 結論 |
|---|---|
| host 框架 | 不用現成常駐程式，自寫 zima_push.py 事件驅動單發推送 |
| VIA 衝突 | 不存在——刷非 VIA 韌體，Raw HID 專用 |
| 裝置比對 | PID 0xF75B + VID 0x8D1D（新）/0xFEED（舊板上韌體），usage 0xFF60/0x61 |
| 鍵盤不在時 | host 全部靜默 exit 0，statusline/hooks 不受影響 |
| 多 session | last-write-wins（HANDOFF 原暫定案，天然成立） |
| waiting 提示 | OLED 反白字 + RGB 橘 + DRV2605L 震動一下 |

## 重要參考資料

- https://docs.qmk.fm/features/rawhid — QMK Raw HID 官方文件
- https://code.claude.com/docs/en/statusline — Claude Code statusline 官方文件
- 調研過的現成專案（最終未採用，接法可參考）：
  danielrosehill/Claude-Macropad-V2、jondkinney/blinkstick-claude、
  zzeneg/qmk-hid-host、Klathmon/qmk-hid-display、dob9601/qmk-oled-api

## 下次接續的開頭

工作目錄 `cd ~/git/qmk-claude-oled`。若韌體還沒刷成：`cd ~/git/vial-qmk &&
qmk flash -kb splitkb/zima -km claude`，請使用者按板底 USB 口右邊 reset。
刷完驗證：`python3 host/zima_push.py model "Test"` 應出現在 OLED 第二行；
開新 Claude Code session 應自動更新（statusline 已掛全域 settings.json）。
之後的重點是 P3 部署其他機器與實際使用回饋（鍵位、震動強度、RGB 亮度微調）。
