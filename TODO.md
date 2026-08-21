# 技能本身的待辦

> 這裡只放 `.claude/skills/sillytavern-card-generator/` 的改進項目。
> 各張卡片的製作進度放在該卡自己的資料夾裡（例如 `cards/gender-is-not-the-limit/TODO.md`）。

## 可以從實作中回饋進技能的經驗

做《性別不是限制，性吸引力才是》時遇到、但技能文件裡還沒寫的東西：

- [ ] **多角色單卡的焦點判定**：三線並行時要怎麼決定「本輪由誰主導」。這是通用問題，
      應該寫進 `references/` 成為一份指南，而不是只存在於某張卡的 system_prompt。
- [ ] **JavaScript 在酒館會被過濾**：互動效果要用 CSS radio `:checked` 技巧替代。
      這條實作教訓應該補進 `references/regex-beautify-guide.md`。
- [ ] **內嵌圖片的重量控制**：頭像用 data URI 內嵌時的尺寸/畫質建議（128px、JPEG、
      3-5KB），以及為什麼不要把大張花邊塞進 `border-image`（每則訊息都會重複扛）。
- [ ] **不可逆的角色界線旗標**：當使用者要求「角色被認真拒絕後永久改變行為」時的
      實作模式（最高優先權規則 + 單向旗標 + 明確的判定標準）。這個模式有普遍價值。
- [ ] **視覺化要「顯示」而非「告訴」**：小遊戲卡片的設計教訓——與其在文字欄寫
      「他在看你」，不如把視線畫成圖。可以補進美化指南。

## 尚未驗證的部分

- [ ] `playtest_engine.py` 只在自製的測試資料上跑過，還沒用真實完整的卡片實測過一次。
- [ ] 技能描述的觸發準確度未做過優化（skill-creator 的 description optimization）。
