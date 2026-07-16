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

Keymap 在 vial-qmk fork：`keyboards/splitkb/zima/keymaps/vial/`
（repo: mansonliu/vial-qmk，分支 vial）。**Vial 韌體** — 可用 Vial App 改鍵；
Claude 推送用自訂 command id 0x63 掛在 raw_hid_receive_kb()，與 VIA/Vial 協定共存。
flash 全滿（28616/28672），為此 audio 已停用（蜂鳴器沒聲音）。
Vial 解鎖組合鍵：Esc + 右下鍵。

```sh
cd ~/git/vial-qmk
qmk flash -kb splitkb/zima -km vial   # 按板底 USB 口右邊的 reset 進 bootloader
```

### OLED 版面（直式 32×128，鍵盤橫放）

旋轉 270°（keymap oled_init_user；zima.c 已改為尊重 user 覆寫）。四個場景：

- **靜置**：模型名直排大字（字母 12×16、版號同大小、小數點縮成小方點），
  每 5 秒與「5H 用量條」輪替——全寬直條由下往上填滿百分比（無數字）
- **working**：32×48 Claude 星芒置中脈動（光芒長短粗細照官方時鐘方位，
  4 幀 62–100% 縮放、0-1-2-3-2-1 呼吸循環）
- **waiting**：INPUT 五個 18×24 大字滿屏、0.6s/0.3s 閃爍（黃色底光同相位）
- **error**：ERROR 滿屏
- **待機（無訊號）**：靜態滿版星芒——開機後尚未收到推送、或超過 1 小時沒推送時顯示

字型：glcdfont 0x20–0x5F 子集（bigfont.h）任意倍率放大＋橫向 smear 加粗；
星芒 4 幀點陣在 spark.h（keymap 目錄有生成腳本邏輯，見 git log）。
CMD_INFO 協定仍接受但目前不顯示。

### 狀態回饋

| 狀態 | OLED | RGB 底光 |
|---|---|---|
| idle | 模型名↔用量條輪替 | 關（刻意：亮燈＝有事） |
| working | 星芒脈動 | 青色呼吸（手寫模擬） |
| waiting | INPUT 滿屏閃爍 | 黃色同相位閃爍 |
| error | ERROR 滿屏 | 紅色恆亮 |

註：本片 Zima 未焊震動馬達（HAPTIC 移除）；蜂鳴器提醒試過太大聲已取消，
audio 停用。RGB 動畫引擎裁掉（working 呼吸為手寫模擬）。

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
zima_push.py usage 62 41         # 手動設用量 %（5h、7d）
zima_push.py statusline          # statusline 模式：stdin JSON → 推送 + 印文字
zima_push.py notification        # Notification hook 模式：過濾閒置提醒（見下）
```

鍵盤沒插時全部靜默略過（exit 0），statusline/hooks 不會被拖垮。

### Raw HID 協定（32-byte report）

byte 0 固定 0x63（VIA 未用的 command id，路由到 raw_hid_receive_kb）。

| byte 1 | 意義 | payload |
|---|---|---|
| 0x01 | 模型名 | bytes 2..：NUL 結尾 ASCII，≤21 字 |
| 0x02 | 狀態 | byte 2：0 idle / 1 working / 2 waiting / 3 error |
| 0x03 | 資訊列 | bytes 2..：NUL 結尾 ASCII，≤21 字 |
| 0x04 | 用量 | byte 2：5小時窗 %、byte 3：7天窗 %（0–100，255=未知） |

裝置比對：PID `0xF75B`，VID `0x8D1D`（新韌體）或 `0xFEED`（舊），
usage page `0xFF60` / usage `0x61`。

## Claude Code 掛載（settings.json）

```jsonc
"statusLine": { "type": "command",
  "command": "python3 $HOME/git/qmk-claude-oled/host/zima_push.py statusline" },
"hooks": {
  "UserPromptSubmit": [{ "hooks": [{ "type": "command", "async": true, "timeout": 10,
    "command": "python3 $HOME/git/qmk-claude-oled/host/zima_push.py status working 2>/dev/null || true" }] }],
  "Stop":             [{ "hooks": [{ "type": "command", "async": true, "timeout": 10,
    "command": "python3 $HOME/git/qmk-claude-oled/host/zima_push.py status idle 2>/dev/null || true" }] }],
  "Notification":     [{ "hooks": [{ "type": "command", "async": true, "timeout": 10,
    "command": "python3 $HOME/git/qmk-claude-oled/host/zima_push.py notification 2>/dev/null || true" }] }],
  "SessionEnd":       [{ "hooks": [{ "type": "command", "timeout": 10,
    "command": "python3 $HOME/git/qmk-claude-oled/host/zima_push.py status idle 2>/dev/null || true" }] }]
}
```

**Notification 必須走 `notification` 模式，不要直接 `status waiting`**：
Claude Code 的 Notification 事件除了權限請求／提問，還包含「閒置 60 秒」
的提醒（message 為 "Claude is waiting for your input"）。直接接 waiting
會造成每次對話結束一分鐘後黃燈誤閃；`notification` 模式會過濾掉閒置提醒，
只有真的需要回答時才觸發 WAITING。

多 session：最後推送者蓋掉顯示（last-write-wins）。

## Codex 端

`host/codex_hook.py` 讀取 Codex hook 的 stdin JSON，並呼叫既有的
`host/zima_push.py`，不自行實作 HID：

- `SessionStart`：設定模型名、刷新用量、設為 `idle`
- `UserPromptSubmit`：設定模型名、刷新用量、設為 `working`
- `PermissionRequest`：設定模型名、刷新用量、設為 `waiting`
- `PostToolUse`：刷新用量、回到 `working`（授權工具執行完畢後的近似值）
- `Stop`：設定模型名、刷新用量、設為 `idle`

用量取 `transcript_path` JSONL 最後一筆 `token_count`：300 分鐘視窗映射成
5h，10080 分鐘視窗映射成 7d；缺值或解析失敗送 `255`（未知）。為避免 hook
因大型 transcript 變慢，只搜尋檔案尾端 1 MiB。

在 `~/.codex/config.toml` 加入以下設定（若 repo 不在
`$HOME/git/qmk-claude-oled`，請替換每個 command 的絕對位置）：

```toml
[features]
hooks = true

[[hooks.SessionStart]]
matcher = "startup|resume|clear"

[[hooks.SessionStart.hooks]]
type = "command"
command = 'python3 "$HOME/git/qmk-claude-oled/host/codex_hook.py" session'
timeout = 3

[[hooks.UserPromptSubmit]]

[[hooks.UserPromptSubmit.hooks]]
type = "command"
command = 'python3 "$HOME/git/qmk-claude-oled/host/codex_hook.py" working'
timeout = 3

[[hooks.PermissionRequest]]

[[hooks.PermissionRequest.hooks]]
type = "command"
command = 'python3 "$HOME/git/qmk-claude-oled/host/codex_hook.py" waiting'
timeout = 3

[[hooks.PostToolUse]]

[[hooks.PostToolUse.hooks]]
type = "command"
command = 'python3 "$HOME/git/qmk-claude-oled/host/codex_hook.py" working'
timeout = 3

[[hooks.Stop]]

[[hooks.Stop.hooks]]
type = "command"
command = 'python3 "$HOME/git/qmk-claude-oled/host/codex_hook.py" idle'
timeout = 3
```

安裝與啟用：

1. 確認 `python3 host/zima_push.py status idle` 可執行；鍵盤未插時靜默
   exit 0 是正常行為。若尚未安裝相依套件，執行 `brew install hidapi` 與
   `python3 -m pip install hid`。
2. 將上方片段合併到 `~/.codex/config.toml`，不要重複建立已有的
   `[features]` table；已有時只加 `hooks = true`。
3. 重開 Codex CLI，執行 `/hooks`，review 並 trust 這五個 hook 定義。
4. 不插鍵盤也可執行 `python3 -m unittest host/test_codex_hook.py` 測試 model
   與 transcript 用量解析。

限制：Codex 目前沒有一般性的「正在等使用者回答」hook，因此可靠的
`waiting` 只有權限請求；agent 在文字中提問並結束 turn 時仍會由 `Stop` 顯示
`idle`。Codex 也沒有 turn-error hook，所以 adapter 不會自動送 `error`。
授權回答之後沒有立即觸發的 hook，`PostToolUse` 只能在該工具執行完後近似回到
`working`；工具執行期間可能仍顯示 `waiting`。若 turn 被強制中斷而未觸發
`Stop`，最後狀態也可能暫時保留。多個 Codex session 同時使用時仍是最後推送者
覆蓋顯示（last-write-wins）。Codex transcript 不是穩定介面；格式若在未來版本
改變，adapter 會 fail-open 並把用量顯示為未知，不會阻擋 Codex。

## 部署到其他機器

每台插 Zima 的機器要：clone 本 repo、裝 hidapi + pip hid、
settings.json 掛 statusline 與 hooks（跨機器同步走 claude-sync 池）。
