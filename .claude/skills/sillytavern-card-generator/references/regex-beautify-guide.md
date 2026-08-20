# 正規表達式（Regex）美化設計指南

## 為什麼「美化一律用 regex」

SillyTavern 的 Regex 擴充可以攔截並轉換三個地方的文字：使用者輸入、AI 輸出、以及世界書內容。對於「把角色卡輸出變好看」這件事，**用 regex 攔截 AI 輸出並轉成 HTML，遠比要求模型直接輸出漂亮排版可靠**，原因：

1. **穩定性**：模型每次生成 HTML/CSS 的細節都會有些微差異（顏色值、標籤閉合、縮排），regex 用固定樣板保證輸出 100% 一致。
2. **關注點分離**：模型只需要專心把「這一輪的場景/狀態」正確地填進幾個純文字欄位，不用同時兼顧敘事品質和排版程式碼——生成品質更穩定，也省 token。
3. **可維護性**：使用者想換配色或版型時，只需要改 regex 的 `replaceString`，完全不用碰角色卡的 `system_prompt` 或世界書內容。
4. **不會洩漏格式標記給敘事**：模型只看得到「請輸出 `[HEADER_CARD]...[/HEADER_CARD]`」這種指令，讀者最終看到的是轉換後的 HTML，兩者責任乾淨切開。

因此設計流程固定是兩層：

**第一層（模型輸出層）**：在 `system_prompt`／世界書裡定義一個簡單、好抓取的純文字結構化標記格式。
**第二層（regex 轉換層）**：寫 `findRegex` 抓取該標記並用捕獲群組取出每個欄位，`replaceString` 輸出最終呈現用的 HTML/CSS。

## 設計第一層：純文字標記格式

原則：**欄位順序固定、每個欄位獨占一行、用清楚的 `KEY: value` 或 `[TAG]...[/TAG]` 包起來**，這樣寫 regex 時才好用捕獲群組穩定抓取。範例（狀態欄場景）：

```
[HEADER_CARD]
THEME: LIGHT
TIME: 2026/06/22 (週一) 09:30
LOC: 場景地點
WEATHER: 天氣描述
DESC: 一到兩句話的氛圍描述
[/HEADER_CARD]

（這裡是模型輸出的正文敘事）

[FOOTER_CARD]
PAGE: 1
好感度: 12
關係階段: 初次相遇
[/FOOTER_CARD]
```

跟使用者確認：

- 要不要做 light/dark 兩種主題（例如依故事內時間切換）？如果要，`[HEADER_CARD]` 裡放一個 `THEME: LIGHT|DARK` 欄位，之後對應寫兩條 regex（一條專配 LIGHT、一條專配 DARK），讓 `findRegex` 直接鎖定 `THEME:\s*LIGHT` 或 `THEME:\s*DARK`。
- 有沒有欄位是選填的（可能為空）？`findRegex` 裡對應的捕獲群組要用 `(.*?)` 這種非貪婪、允許空字串的寫法，並確認 `replaceString` 在空值時不會出現難看的空白區塊。

## 設計第二層：findRegex 與 replaceString

實務作法（取材自真實可運作的酒館卡）：

```
findRegex:
\[HEADER_CARD\]\r?\nTHEME:\s*(.*?)\r?\nTIME:\s*(.*?)\r?\nLOC:\s*(.*?)\r?\nWEATHER:\s*(.*?)\r?\nDESC:\s*(.*?)\r?\n\[\/HEADER_CARD\]

replaceString:
<div style="...">$1 $2 $3 $4 $5</div>
```

要點：

- 每一行用 `\r?\n` 而不是只用 `\n`，避免因為換行符是 `\r\n`（Windows 風格）還是 `\n` 導致抓不到。
- 每個欄位值用 `(.*?)`（非貪婪）包住，順序對應 `replaceString` 裡的 `$1`、`$2`……
- `replaceString` 裡可以直接寫內嵌 CSS 的 HTML（`style="..."`），因為酒館聊天視窗預設不吃外部 CSS 檔案，內嵌樣式最保險。
- 想要動畫效果（例如淡入淡出的裝飾符號、呼吸燈式的箭頭顏色）可以在 `replaceString` 裡內嵌一段 `<style>@keyframes ...</style>`，這在酒館的聊天渲染裡是可行的。
- 數值型欄位（好感度等）如果要做成進度條，`replaceString` 裡可以直接用該欄位的值當作 `width:$N%`，讓進度條寬度直接對應數值——不需要額外的計算邏輯，酒館的 regex 不支援算術，所以務必讓模型輸出的原始數值本身就是可以直接套用的百分比或格式。

## Regex 腳本本身的欄位設定

每條 regex 腳本（對應 `regex_scripts[]`）要決定：

| 欄位 | 說明 |
|---|---|
| `findRegex` | 抓取目標的正則表達式，通常以 `/pattern/flags` 或純 pattern 字串儲存（依酒館版本，多半支援加上 `s`／`i` 等 flag）。 |
| `replaceString` | 取代後的內容，支援 `$1`、`$2`……取用捕獲群組，也支援 `{{match}}` 取整個匹配內容。 |
| `placement` | 這個腳本作用在哪裡——使用者輸入／AI 輸出／世界書／斜線指令。**美化狀態欄一定是作用在 AI 輸出**；如果同時要隱藏使用者手動輸入的觸發指令（例如 `[吹牛遊戲]`）不顯示在聊天紀錄裡，才需要額外一條作用在使用者輸入的腳本。實際的數值代碼請以使用者酒館版本的 Regex 擴充介面為準，不要憑空編號，介面上通常會用勾選框直接標示「User Input／AI Output／Slash Commands／World Info」等中文或英文選項，讓使用者照著勾。 |
| `markdownOnly` | 是否只在 Markdown 渲染模式下套用（多數 HTML 卡片美化建議開啟，避免在純文字模式下出現破碎的標籤）。 |
| `runOnEdit` | 使用者編輯歷史訊息時是否重新套用這條規則（美化用途通常建議開啟，保持一致外觀）。 |
| `depth` / `minDepth` / `maxDepth` | 限制這條規則只作用在對話的特定深度範圍（多數美化規則不需要限制，留空即可）。 |
| `disabled` | 先建好但還不啟用時可以先關閉，方便使用者在酒館介面裡逐條測試。 |

## 小遊戲/觸發事件的美化

流程一樣是「先定義觸發時的純文字標記 → 再用 regex 轉成 HTML」，額外要注意：

1. **觸發邏輯寫在 `system_prompt` 或世界書，不要寫在 regex 裡**——regex 只負責「把已經觸發的遊戲狀態轉成好看的介面」，判斷「現在該不該進入遊戲模式」是模型依照關鍵詞/回合數等條件自行決定的敘事邏輯。
2. 遊戲進行中通常需要**額外的狀態欄位**（例如 `GAME_STATE: BLUFFING_ACTIVE`），可以讓 `[FOOTER_CARD]` 多一個可選欄位，或是額外開一組 `[GAME_CARD]...[/GAME_CARD]` 標記，各自寫一條對應的 regex。
3. **遊戲結束要有明確的退出條件**（例如連續幾輪沒有相關關鍵詞，或使用者/角色明確說要停止），退出後 `GAME_STATE` 要重置回 `NORMAL`，對應的 regex 也要能正確處理「沒有遊戲狀態時該欄位為空」的情況（不要讓它渲染出一個空殼卡片）。
4. 如果遊戲有冷卻機制（例如「觸發過一次後，接下來幾輪不能再觸發」），冷卻邏輯建議寫在世界書條目的 `extensions.cooldown`／`sticky` 欄位，或是明確寫進 `system_prompt` 的規則段落，讓模型自行追蹤回合數。

## 交付前的檢查清單

- [ ] 每個 `findRegex` 有沒有考慮到 `\r\n` 與 `\n` 兩種換行風格？
- [ ] 每個欄位在值為空/未提供時，`replaceString` 呈現出來會不會很醜（例如出現「WEATHER: 」的空殼）？
- [ ] Light/Dark 兩種主題（如果有做）是否各自對應獨立的 `findRegex`（用 `THEME:\s*LIGHT` / `THEME:\s*DARK` 精確區分），避免互相誤匹配？
- [ ] `placement` 是否設對（美化 AI 輸出的規則不該勾到使用者輸入）？
- [ ] 有沒有把整段 regex 範本存進 `assets/regex_snippets.md` 或直接寫進卡片的 `data.extensions.regex_scripts`，方便使用者匯入？
