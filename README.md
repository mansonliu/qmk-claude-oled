# qmk-claude-oled

讓 QMK 鍵盤（splitkb Zima）的 OLED 即時顯示 Claude Code 的模型與 agent 狀態，
按鍵兼作 Claude Code 操控鍵。

```
Claude Code statusline / hooks
      → host/zima_push.py（Python + hidapi）
      → USB Raw HID（usage page 0xFF60）
      → QMK raw_hid_receive() → OLED / RGB / 震動
```

## 硬體

- **splitkb Zima** — 4×3 巨集鍵盤，OLED 128×32（文字 21×4）、旋鈕、RGB 底光×5、
  DRV2605L 震動馬達、蜂鳴器。MCU atmega32u4（atmel-dfu bootloader）。
- Raw HID 只在 USB 有效。

## 韌體

Keymap 在 vial-qmk fork：`keyboards/splitkb/zima/keymaps/claude/`
（repo: mansonliu/vial-qmk，分支 vial）。**非 VIA/Vial** — Raw HID 通道專用於本專案。

```sh
cd ~/git/vial-qmk
qmk flash -kb splitkb/zima -km claude   # 按板底 USB 口右邊的 reset 進 bootloader
```

### OLED 版面（21×4）

```
Claude Code   L0      ← 標題 + 目前鍵層
Fable 5               ← 模型名（host 推送）
working /             ← 狀態 + 轉圈動畫
~/git/qmk-claude-oled ← 資訊列（cwd）
```

### 狀態回饋

| 狀態 | OLED | RGB 底光 | 震動 |
|---|---|---|---|
| idle | `idle` | 關 | — |
| working | `working /`（轉圈） | 青色呼吸 | — |
| waiting | `>> NEEDS INPUT <<` | 橘色恆亮 | 買茲一下 |
| error | `!! ERROR !!` | 紅色恆亮 | — |

一小時沒收到 host 推送 → 顯示 `waiting for host...`。

### 鍵位（Layer 0，Claude 操控）

```
[旋鈕按=Enter]  TG(1)     TG(2)
Esc             ↑         Shift+Tab   ← 中斷 / 上 / 切權限模式
Tab             ↓         Enter
1               2         3           ← 快速選選項
```

旋鈕轉動 = ↑/↓（順時針=↓）。Layer 1 = 音效/QK_BOOT、Layer 2 = RGB/震動（同原廠）。

## Host 端

`host/zima_push.py`（需 `brew install hidapi` + `pip install hid`）：

```sh
zima_push.py model "Fable 5"     # 設模型名
zima_push.py status working      # idle|working|waiting|error
zima_push.py info "~/git/foo"    # 設資訊列
zima_push.py statusline          # statusline 模式：stdin JSON → 推送 + 印文字
```

鍵盤沒插時全部靜默略過（exit 0），statusline/hooks 不會被拖垮。

### Raw HID 協定（32-byte report）

| byte 0 | 意義 | payload |
|---|---|---|
| 0x01 | 模型名 | bytes 1..：NUL 結尾 ASCII，≤21 字 |
| 0x02 | 狀態 | byte 1：0 idle / 1 working / 2 waiting / 3 error |
| 0x03 | 資訊列 | bytes 1..：NUL 結尾 ASCII，≤21 字 |

裝置比對：PID `0xF75B`，VID `0x8D1D`（新韌體）或 `0xFEED`（舊），
usage page `0xFF60` / usage `0x61`。

## Claude Code 掛載（settings.json）

```jsonc
"statusLine": { "type": "command",
  "command": "python3 $HOME/git/qmk-claude-oled/host/zima_push.py statusline" },
"hooks": {
  "UserPromptSubmit": [ /* status working (async) */ ],
  "Stop":             [ /* status idle    (async) */ ],
  "Notification":     [ /* status waiting (async) */ ],
  "SessionEnd":       [ /* status idle */ ]
}
```

多 session：最後推送者蓋掉顯示（last-write-wins）。

## 部署到其他機器

每台插 Zima 的機器要：clone 本 repo、裝 hidapi + pip hid、
settings.json 掛 statusline 與 hooks（跨機器同步走 claude-sync 池）。
