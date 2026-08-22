# 花冠／尾卡 regex（第一版）

`scripts_wheel_footer.json` 是可以直接匯入 SillyTavern（角色卡 → Advanced Definitions → Regex Scripts）的三條腳本：

| scriptName | 對應的輸出標籤 |
|---|---|
| `RT_頭卡` | `[HEAD]...[/HEAD]` |
| `RT_正文` | `[BODY]...[/BODY]` |
| `RT_花冠尾卡` | `[WHEEL]...[/WHEEL]` 到 `[FOOT]...[/FOOT]`（兩個標籤一起吃，因為花冠需要讀到尾卡裡的好感度數字） |

加上 `scripts_minigames.json`（記憶配對／探索發現兩個小遊戲，來自另一輪測試，格式相同可直接合併）。

## 運作方式

- 三個角色的花冠六階段文字（羅馬數字／階段名／備註）全部固定寫死在 regex 裡，**目前是第幾階段完全靠 `M:`／`T:`／`L:` 的數字用正規表達式的數字範圍比對算出來**，不需要 AI 每輪額外輸出。
- ⚠️ **門檻不是三人共用同一組**：馬提亞斯是 0-19/20-39/40-59/60-74/75-89/90-100，
  阿霆與 Lia 是 0-19/20-39/**40-54/55-69/70-84/85-100**（後段切得比較密）。
  `build_wheel_footer.py` 裡的 `THRESHOLDS` 字典分開定義，`int_range_regex()` 用純
  數字比對（不是算術）產生對應的 regex——改門檻只要改這個字典，不要手動兜 regex。
- **卡片寬度比照參考卡（Ian）的標準**：外框（`.rt-shell`）`max-width:480px`，裡面
  的頭卡／正文／花冠尾卡跟著等比縮小（花冠 `min(78vw,340px)`，其餘 `min(100%,420px)`）。
  之前用的 650-760px 是照桌機螢幕抓的，在手機聊天欄裡太寬，會把格線擠壓變形。
- 頭像列（點頭像切換要看誰的花冠與衣著）預設停在 `[HEAD]` 的 `FOCUS:` 欄位指定的那個人身上；點擊哪個頭像由 CSS radio + `:not(:empty)`／`:has()` 技巧驅動，沒有 JavaScript。
- 尾卡包在 `<details>` 裡，可以收合。
- 「心事」旁的圓形頭像會顯示**當輪焦點角色**的照片（不是固定符號，也不跟著頭像切換走——VOICE／MOOD 本來就只跟著敘事焦點）。

## 重新產生 JSON

不要手動改 `scripts_wheel_footer.json`——改 `build_wheel_footer.py`（版面配置、文字內容、CSS 都在裡面）然後重新跑：

```
python3 build_wheel_footer.py
```

`avatars/*.b64` 是三人頭像的 base64（128px JPEG），會被內嵌進 regex 輸出裡。

## 測試

`simulate.py` 用 Python 模擬 SillyTavern 的 `String.replace($1$2...)` 行為，對每個角色各自的 18 組好感度邊界值＋ 5 個開局的真實內容跑過，確認花冠階段判定（含馬提亞斯與阿霆／Lia 不同的門檻表）、頭像預設焦點、HTML 標籤配對都正確：

```
python3 simulate.py
```

## 已知限制（曾經是 bug，現在改用 `:has()` 解決）

頭像切換原本用 `id`/`for`（`rtf-m`/`rtf-t`/`rtf-l`）連結，但這組標籤在**每一則訊息**都會逐字重複輸出——HTML 的 id 理論上整頁要唯一，`label[for]` 綁定會抓「整個頁面第一個」該 id 的元素，不是視覺上鄰近的那個，所以在很長的對話串裡點頭像常常沒反應（其實是切到別則訊息看不到的地方去了）。

現在改成：radio 直接包在自己的 `<label>` 裡面（不用 id/for 就能點擊觸發），CSS 改用 `.rt-focus-switch:has(.av-m input:checked) ~ ...` 從外面搆到花冠／尾卡區塊。`:has()` 在主流瀏覽器引擎已經穩定支援多年，這裡放心使用。radio 的 `name` 屬性仍然用 M/T/L 數字當種子（例如 `rt-focus-889220`）降低跨訊息的分組互相影響，但這只是次要的體感改善，不是必要修復——真正解決「點了沒反應」的是 `:has()` 這個改動。

## 已知限制（尚未解決）

若 AI 生成的正文格式跟固定的欄位順序／換行有出入（例如多一行空白、欄位順序跑掉），regex 會整段吃不到，退回顯示原始標籤文字。已知第一版開局（`first_mes`／`alternate_greetings`）保證吃得到，因為是逐字對齊 regex 寫的；**AI 自己接續生成的後續回合則不保證**，需要拿到實際的原始輸出文字才能比對出確切差異並修正。

## 尚未整合進來的部分

- 自訂開局選單（第六個開局的輸入介面）
- 卡片封面圖

這兩個資料夾以外的東西（連同這裡的五條 regex）已經組裝成單一 `chara_card_v3` JSON，
見上一層目錄的 `assemble_card.py` 與 `gender_is_not_the_limit.json`。
