# Regex 美化範本庫

這些是可以直接複製、依卡片實際欄位修改的 regex 範本。每個範本都包含「模型該輸出的純文字標記格式」與「對應的 `findRegex` / `replaceString`」。放進 `data.extensions.regex_scripts` 陣列時，記得每條給獨立的 `id`，並依 `regex-beautify-guide.md` 補齊 `placement`、`markdownOnly`、`runOnEdit` 等欄位。

## 1. 頂部場景資訊卡（單一主題）

**模型輸出格式：**
```
[SCENE_CARD]
TIME: 2026/06/22 (週一) 09:30
LOC: 場景地點
WEATHER: 天氣
DESC: 一句氛圍描述
[/SCENE_CARD]
```

**findRegex：**
```
\[SCENE_CARD\]\r?\nTIME:\s*(.*?)\r?\nLOC:\s*(.*?)\r?\nWEATHER:\s*(.*?)\r?\nDESC:\s*(.*?)\r?\n\[\/SCENE_CARD\]
```

**replaceString：**
```html
<div style="font-family:sans-serif;max-width:480px;margin:10px auto 4px;background:#F5F0E8;border:1px solid #C4A97D;border-radius:4px;padding:12px 16px;">
  <div style="font-size:11px;color:#7A6A55;letter-spacing:0.05em;">$1 · $2 · $3</div>
  <div style="font-size:13px;color:#3A2E22;font-style:italic;margin-top:6px;line-height:1.6;">$4</div>
</div>
```

## 2. 底部好感度/狀態欄（含進度條）

**模型輸出格式：**
```
[STATUS_CARD]
好感度: 42
關係階段: 動搖試探期
內心話: 一句第一人稱內心獨白
[/STATUS_CARD]
```

**findRegex：**
```
\[STATUS_CARD\]\r?\n好感度:\s*(.*?)\r?\n關係階段:\s*(.*?)\r?\n內心話:\s*(.*?)\r?\n\[\/STATUS_CARD\]
```

**replaceString：**（好感度數值直接套用在進度條寬度 `width:$1%`，因此務必要求模型輸出的是 0-100 的純數字）
```html
<div style="font-family:sans-serif;max-width:480px;margin:4px auto 10px;background:#F5F0E8;border:1px solid #C4A97D;border-radius:4px;padding:12px 16px;">
  <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
    <div style="width:56px;font-size:10px;color:#7A6A55;">好感度</div>
    <div style="flex:1;height:6px;background:#E4DCCE;border-radius:3px;overflow:hidden;">
      <div style="height:100%;width:$1%;background:#8B6F47;"></div>
    </div>
    <div style="width:28px;text-align:right;font-size:11px;font-family:monospace;">$1</div>
  </div>
  <div style="font-size:10px;color:#7A6A55;letter-spacing:0.05em;margin-bottom:6px;">階段：$2</div>
  <div style="font-size:12px;color:#3A2E22;border-left:2px solid #8B6F47;padding-left:8px;line-height:1.6;">$3</div>
</div>
```

## 3. Light / Dark 雙主題切換

當 `[HEADER_CARD]` 內含 `THEME: LIGHT` 或 `THEME: DARK` 欄位時，寫**兩條獨立的 regex**，各自的 `findRegex` 精確鎖定對應主題字串，避免互相誤匹配：

```
findRegex（LIGHT 版）：
\[HEADER_CARD\]\r?\nTHEME:\s*LIGHT\r?\nTIME:\s*(.*?)\r?\n...\[\/HEADER_CARD\]

findRegex（DARK 版）：
\[HEADER_CARD\]\r?\nTHEME:\s*DARK\r?\nTIME:\s*(.*?)\r?\n...\[\/HEADER_CARD\]
```

`replaceString` 兩版內容相同結構，只是配色變數換成深色調色盤（背景色、邊框色、文字色全部對調成深色系）。是否要做雙主題，以及依什麼判斷切換（劇情內時間、使用者裝置主題等），要在 Stage 1/5 跟使用者確認清楚並寫進 `system_prompt` 的主題判斷規則。

## 4. 小遊戲狀態卡（觸發式，含冷卻標記）

**模型輸出格式（遊戲進行中才會出現這段）：**
```
[GAME_CARD]
NAME: 真心話大冒險
STATE: ACTIVE
ROUND: 2/3
TENSION: 65
[/GAME_CARD]
```

**findRegex：**
```
\[GAME_CARD\]\r?\nNAME:\s*(.*?)\r?\nSTATE:\s*(.*?)\r?\nROUND:\s*(.*?)\r?\nTENSION:\s*(.*?)\r?\n\[\/GAME_CARD\]
```

**replaceString：**
```html
<div style="font-family:sans-serif;max-width:480px;margin:4px auto;background:#2A1E2E;border:1px solid #C98CC9;border-radius:4px;padding:10px 14px;">
  <div style="display:flex;justify-content:space-between;align-items:center;">
    <span style="font-size:11px;color:#E8C8E8;letter-spacing:0.08em;">🎲 $1</span>
    <span style="font-size:10px;color:#C98CC9;">$3</span>
  </div>
  <div style="margin-top:6px;height:4px;background:#3A2A3E;border-radius:2px;overflow:hidden;">
    <div style="height:100%;width:$4%;background:#C98CC9;"></div>
  </div>
</div>
```

遊戲未觸發時模型不應輸出 `[GAME_CARD]` 區塊——不需要額外寫「隱藏空卡片」的 regex，只要 `system_prompt` 清楚規定「只有在遊戲進行中才輸出這個區塊」即可。

## 5. 隱藏變量更新記錄（不顯示給讀者）

如果 `variable-system.md` 設計的 `<!-- <VariableUpdateLog>...</VariableUpdateLog> -->` 因為某些酒館前端仍會顯示 HTML 註解導致穿幫，可以額外寫一條 regex 把整段直接清空：

**findRegex：**
```
<!-- <VariableUpdateLog>[\s\S]*?<\/VariableUpdateLog> -->
```

**replaceString：**
```
(留空)
```

用 `[\s\S]*?` 而不是 `.*?` 是因為變量記錄通常跨多行，`.` 預設不匹配換行符。

## 使用提醒

- 所有顏色值、字體只是範例配色，請依 Stage 5 跟使用者確認的視覺風格調整。
- 捕獲群組的順序必須與 `findRegex` 裡欄位出現的順序完全一致，新增/刪除欄位時記得同步調整 `replaceString` 裡的 `$N` 編號。
- 建議先在酒館的 Regex 擴充介面用一小段測試文字確認渲染正確，再把最終版本寫回角色卡的 `regex_scripts`。
