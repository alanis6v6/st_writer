# chara_card_v3 欄位規格參考

這份文件記錄組裝最終角色卡 JSON 時需要的精確欄位與型別，取材自實際可在 SillyTavern 匯入運作的角色卡結構。組裝時直接以 `assets/character_card_template.json` 為骨架填寫，本文件用來查對每個欄位的意義與型別。

## 頂層結構

角色卡 JSON 同時保留「V2 相容的頂層欄位」與「V3 的 `data` 巢狀欄位」，兩邊內容通常保持一致（V2 欄位是為了向下相容舊版酒館）：

```json
{
  "name": "...",
  "description": "...",
  "personality": "...",
  "scenario": "...",
  "first_mes": "...",
  "mes_example": "...",
  "spec": "chara_card_v3",
  "spec_version": "3.0",
  "data": {
    "name": "...",
    "description": "...",
    "personality": "...",
    "scenario": "...",
    "first_mes": "...",
    "mes_example": "...",
    "creator_notes": "...",
    "system_prompt": "...",
    "post_history_instructions": "",
    "tags": [],
    "creator": "",
    "character_version": "v1",
    "alternate_greetings": [],
    "character_book": { "entries": [], "name": "世界書名稱" },
    "extensions": { }
  }
}
```

## 核心敘事欄位

| 欄位 | 用途 | 設計提醒 |
|---|---|---|
| `name` | 角色顯示名稱 | 可以包含本名＋暱稱／英文名 |
| `description` | 角色卡的「首頁介紹」 | 通常是給讀者看的行銷/氛圍文字，可以分層寫（表層人設 + 加鎖的深層設定預告） |
| `personality` | 性格摘要 | 給模型參考的性格核心，也可能顯示在部分前端介面 |
| `scenario` | 情境設定 | 世界觀時空背景 + 初次相遇的判定邏輯（例如依使用者輸入身分決定開局） |
| `first_mes` | 開場白 | 可以是完整開場文字，也可以像 Stage 5 設計的做法一樣，放一個會被 regex 攔截轉換成「選擇開局」介面的標記文字 |
| `mes_example` | 對話範例 | 用 `<START>` 分隔多組範例，每組示範 `{{user}}` / `{{char}}` 的對話 |
| `alternate_greetings` | 替代開場白陣列 | 每一則都是完整的開場情境，適合用來實現「多種初遇身分」的設計 |
| `system_prompt` | 系統提示詞 | 承載本技能各階段確認的所有規則：核心演繹原則、敘事技法、語言風貌規範、世界觀氛圍、心理狀態狀態機、變量更新規則、輸出格式指令、小遊戲邏輯等 |
| `post_history_instructions` | 歷史訊息後指令 | 較少用，通常留空或放置需要每輪最後才強調一次的短指令 |
| `creator_notes` | 創作者備註 | 給其他人看的說明，不會進入模型上下文 |
| `tags` | 標籤陣列 | 方便分類/搜尋 |

## `character_book`（世界書）

```json
{
  "entries": [
    {
      "id": 0,
      "keys": ["關鍵詞1", "關鍵詞2"],
      "secondary_keys": [],
      "comment": "條目名稱（給創作者看的標籤，不影響觸發）",
      "content": "實際會被注入模型上下文的內容",
      "constant": false,
      "selective": true,
      "insertion_order": 100,
      "enabled": true,
      "position": "before_char",
      "use_regex": true,
      "extensions": {
        "position": 0,
        "exclude_recursion": false,
        "display_index": 0,
        "probability": 100,
        "useProbability": true,
        "depth": 4,
        "selectiveLogic": 0,
        "group": "",
        "group_override": false,
        "group_weight": 100,
        "prevent_recursion": false,
        "delay_until_recursion": false,
        "scan_depth": null,
        "match_whole_words": null,
        "case_sensitive": null,
        "automation_id": "",
        "role": 0,
        "vectorized": false,
        "sticky": 0,
        "cooldown": 0,
        "delay": 0,
        "match_persona_description": false,
        "match_character_description": false,
        "match_character_personality": false,
        "match_character_depth_prompt": false,
        "match_scenario": false,
        "match_creator_notes": false,
        "triggers": [],
        "ignore_budget": false
      }
    }
  ],
  "name": "世界書名稱"
}
```

重點欄位意義（設計原則見 `worldbook-guide.md`）：

- `keys` / `secondary_keys`：觸發關鍵詞，`selective: true` 時 `secondary_keys` 才會生效，邏輯由 `extensions.selectiveLogic` 決定（0 通常對應 AND_ANY，實際對照請以使用者酒館版本介面為準）。
- `constant`：`true` 代表每輪常駐注入，不受關鍵詞限制。
- `position`：字串型式的粗略插入位置（例如 `"before_char"`／`"after_char"`），精確位置與深度由 `extensions.position`、`extensions.depth` 進一步控制（部分版本用 `extensions.position` 的數字對應「角色定義前/後」「作者備註頂/底部」「依深度插入」等更多選項，介面上通常有清楚的下拉選單，讓使用者對照調整）。
- `enabled`：是否啟用這條條目；系統性條目（如變量欄位字典）常故意設 `false`，只當文件用。
- `extensions.probability` / `useProbability`：機率觸發。
- `extensions.group` 系列：分組互斥。
- `extensions.sticky` / `cooldown` / `delay`：黏著/冷卻/延遲，常用在事件與小遊戲設計。

## `data.extensions.regex_scripts`（美化用 regex）

```json
[
  {
    "id": "唯一識別碼",
    "scriptName": "給創作者看的腳本名稱",
    "findRegex": "正則表達式字串",
    "replaceString": "取代後內容，可用 $1 $2 ... 取用捕獲群組",
    "trimStrings": [],
    "placement": [2],
    "disabled": false,
    "markdownOnly": true,
    "promptOnly": false,
    "runOnEdit": true,
    "substituteRegex": 0,
    "minDepth": null,
    "maxDepth": null
  }
]
```

設計細節與 `placement` 對照方式見 `regex-beautify-guide.md`；`substituteRegex` 是酒館內部用來標記巨集替換行為的欄位，一般填 `0` 即可，除非使用者的版本另有指定用法。

## `data.extensions` 的其他常見欄位

```json
{
  "talkativeness": "0.5",
  "fav": false,
  "world": "世界書名稱（需與 character_book.name 對應）",
  "depth_prompt": { "prompt": "", "depth": 4, "role": "system" },
  "regex_scripts": [ /* 見上 */ ]
}
```

## 組裝檢查清單

- [ ] 頂層與 `data` 內的核心敘事欄位內容一致（沒有漏同步）
- [ ] `character_book.entries` 涵蓋 Stage 2 checklist 確認過的登場人物/事件/NPC/世界觀規則
- [ ] 如果做了 MVU，STATUS_DATA 字典條目、變量更新腦條目、輸出格式指令條目三者俱全且邏輯一致
- [ ] `regex_scripts` 對應到 `system_prompt`／世界書裡定義的每一種純文字標記格式，沒有標記定義了卻沒對應 regex，也沒有 regex 卻沒有標記會觸發它
- [ ] `alternate_greetings`（如果有多開局設計）每則都完整可獨立運作
- [ ] JSON 語法正確（沒有多餘逗號、字串正確跳脫換行符），建議輸出前實際跑一次 JSON 解析驗證
