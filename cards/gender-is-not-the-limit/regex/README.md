# 花冠／尾卡 regex（第一版）

`scripts_wheel_footer.json` 是可以直接匯入 SillyTavern（角色卡 → Advanced Definitions → Regex Scripts）的三條腳本：

| scriptName | 對應的輸出標籤 |
|---|---|
| `RT_頭卡` | `[HEAD]...[/HEAD]` |
| `RT_正文` | `[BODY]...[/BODY]` |
| `RT_花冠尾卡` | `[WHEEL]...[/WHEEL]` 到 `[FOOT]...[/FOOT]`（兩個標籤一起吃，因為花冠需要讀到尾卡裡的好感度數字） |

## 運作方式

- 三個角色的花冠六階段文字（羅馬數字／階段名／備註）全部固定寫死在 regex 裡，**目前是第幾階段完全靠 `M:`／`T:`／`L:` 的數字用正規表達式的數字範圍比對算出來**，不需要 AI 每輪額外輸出。
- 頭像列（點頭像切換要看誰的花冠與衣著）預設停在 `[HEAD]` 的 `FOCUS:` 欄位指定的那個人身上；點擊哪個頭像由 CSS radio + `:not(:empty)` 技巧驅動，沒有 JavaScript。
- 尾卡包在 `<details>` 裡，可以收合。

## 重新產生 JSON

不要手動改 `scripts_wheel_footer.json`——改 `build_wheel_footer.py`（版面配置、文字內容、CSS 都在裡面）然後重新跑：

```
python3 build_wheel_footer.py
```

`avatars/*.b64` 是三人頭像的 base64（128px JPEG），會被內嵌進 regex 輸出裡。

## 測試

`simulate.py` 用 Python 模擬 SillyTavern 的 `String.replace($1$2...)` 行為，對 13 組好感度邊界值（0/19/20/39/40/59/60/74/75/89/90/100）＋ 5 個開局的真實內容跑過，確認花冠階段判定、頭像預設焦點、HTML 標籤配對都正確：

```
python3 simulate.py
```

## 已知限制

頭像切換用的是 `id`/`for`（`rtf-m`/`rtf-t`/`rtf-l`）。HTML 的 id 理論上整頁要唯一，在很長的對話串裡每則訊息都會重複輸出一樣的 id，瀏覽器只認頁面上第一個該 id 的元素——保證在**最新一則**訊息上正常運作，往回翻到很久以前的舊訊息可能會失靈。純 regex 文字替換沒辦法生成「每則訊息獨一無二的 id」。

## 尚未整合進來的部分

- `[MEMORY]`／`[FIND]` 兩個小遊戲的 regex（另外在 `/tmp` 的 scratchpad 測試過，還沒搬進本資料夾）
- 自訂開局選單
- 最終組裝成單一 `chara_card_v3` JSON
