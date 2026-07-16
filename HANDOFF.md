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
- [x] P1 韌體 v2＝**Vial 版**：`~/git/vial-qmk/keyboards/splitkb/zima/keymaps/vial/`
      （v1 純 QMK keymaps/claude/ 已刪，因 Vial App 打不開、使用者要能改鍵）。
      Claude 推送掛 raw_hid_receive_kb()、command id 0x63，與 VIA/Vial 協定共存。
      28616/28672（99%！），代價：audio 停用＋砍 grave_esc/space_cadet/magic/
      tap_dance/combo/key_override/qmk_settings。日後要加功能得先砍 haptic（約省 1.5KB）
- [x] P1 host 端：不用現成框架，自寫 `host/zima_push.py`（hidapi 直推，約 60 行核心）
      — 調研過的 qmk-hid-host 等全是常駐程式，對「statusline 事件驅動推送」反而多餘
- [x] P1 statusline：settings.json 已掛 `statusLine`（同一支腳本 statusline 模式，
      印 `模型 | cwd` 並推送 CMD_MODEL + CMD_INFO）
- [x] P2 agent 狀態：hooks 已掛 UserPromptSubmit→working、Stop→idle、
      Notification→waiting、SessionEnd→idle（皆 async + 靜默失敗）
- [x] 刷韌體成功（2026-07-16，dfu-programmer 0x6800 bytes）；新韌體以 VID 0x8D1D
      重新列舉、Raw HID 介面（0xFF60/0x61）出現，host 推送 model/status 皆成功送達
- [x] Vial 版刷入成功（2026-07-16 稍晚）、0x63 協定推送驗證通過
- [x] OLED 改 12×16 加粗大字（使用者反映小字在桌上不顯眼）：上行模型名、
      下行狀態（working 轉圈、waiting「NEED INPUT」閃爍 0.6s/0.3s）；
      小字 cwd 資訊列取消（協定仍收 CMD_INFO 只是不顯示）；
      字型＝glcdfont 0x20-0x5F 子集抽進 bigfont.h，render 時像素×2＋橫向 smear 加粗；
      RGB 動畫只留 breathing（省 flash），25286/28672（88%）
- [x] Vial App 開啟確認 OK；OLED 已迭代成直式（鍵盤橫放）四場景版，
      細節見 README；靜置輪替模型名↔5H全寬用量條（rate_limits 來自 statusline JSON，
      Pro/Max 第一次 API 回應後才有）；星芒幾何是使用者對照官方 logo 口頭校過的
      （11/1 點最長粗、1 點略短於 11、7 點最短、9 點最細、4/5 點靠攏）
- [ ] 用一陣子的鍵位/視覺回饋；鍵位建議清單已給過（見對話 2026-07-16），使用者未定案
- [ ] P2 多 session：暫定 last-write-wins（已是天然行為，觀察夠不夠用）
- [ ] P3 部署其他機器：host 腳本 + hidapi + settings 掛載（README 有步驟）；
      settings.json 是機器專屬檔不進共享池，各機自行加

## 關鍵決策摘要

| 決策點 | 結論 |
|---|---|
| host 框架 | 不用現成常駐程式，自寫 zima_push.py 事件驅動單發推送 |
| VIA/Vial 共存 | 協定加 0x63 magic byte，VIA 把未知 command id 轉 raw_hid_receive_kb() |
| Vial 解鎖 | Esc(1,0)+右下(3,2)；UID 0xDB5A56202D2BEFD1 |
| 裝置比對 | PID 0xF75B + VID 0x8D1D（新）/0xFEED（舊板上韌體），usage 0xFF60/0x61 |
| 鍵盤不在時 | host 全部靜默 exit 0，statusline/hooks 不受影響 |
| 多 session | last-write-wins（HANDOFF 原暫定案，天然成立） |
| waiting 提示 | OLED「INPUT」滿屏閃爍 + RGB 黃燈同相位閃爍(0.6s/0.3s) + 蜂鳴器上升雙音 |
| 震動馬達 | 本片 Zima 沒焊馬達(選配)，HAPTIC 移除；提醒改走板載蜂鳴器(AUDIO) |
| flash 已砍清單 | extrakey、RGB動畫引擎(working呼吸手寫)、開機音、one-shot、grave_esc/space_cadet/magic/tap_dance/combo/key_override/qmk_settings |

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
