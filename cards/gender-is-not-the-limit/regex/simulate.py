# -*- coding: utf-8 -*-
"""Simulate SillyTavern's regex_scripts application (JS String.replace semantics)
against sample messages, to validate the v3 wheel/footer scripts before shipping.
"""
import json
import re
import sys

SCRIPTS_PATH = "scripts_wheel_footer.json"

def js_replace(pattern, repl_template, text):
    """Mimic JS text.replace(/pattern/, "...$1...$2...") - unmatched optional
    groups become empty string, exactly like SillyTavern/JS does."""
    rx = re.compile(pattern, re.MULTILINE)
    m = rx.search(text)
    if not m:
        return text, False

    def group_or_empty(n):
        try:
            v = m.group(n)
        except (IndexError, error_type()):
            return None
        return v if v is not None else ""

    def sub_placeholder(mm):
        n = int(mm.group(1))
        try:
            v = m.group(n)
        except re.error:
            v = None
        return v if v is not None else ""

    replaced = re.sub(r"\$(\d+)", sub_placeholder, repl_template)
    new_text = text[: m.start()] + replaced + text[m.end() :]
    return new_text, True

def error_type():
    return re.error

def apply_all_scripts(text, scripts):
    for s in scripts:
        if s.get("disabled"):
            continue
        text, matched = js_replace(s["findRegex"], s["replaceString"], text)
        status = "matched" if matched else "NO MATCH"
        print(f"  [{s['scriptName']}] {status}")
    return text

def make_sample(m, t, l, focus="馬提亞斯"):
    return f"""[HEAD]
FOCUS: 今日焦點・{focus}
CHAPTER: Kapitel I
TIME: 19:00
LOC: 新竹老宅・餐廳
WEATHER: 起風
LEAD: 測試用引言。
[/HEAD]

[BODY]
這是測試用的正文內容，用來確認 BODY 區段的比對不會被 WHEEL/FOOT 的規則誤吃。
[/BODY]

[WHEEL]
ROT: 0
ROMAN: Akt III
LABEL: 隱忍
NOTE: 測試備註
[/WHEEL]

[FOOT]
SCENE: 老宅 · 餐廳
ACT: Test
CLOCK: 測試 19:00
M: {m}
T: {t}
L: {l}
HEAT: 50
U_WEAR: 測試你的衣著
M_WEAR: 測試馬提亞斯衣著
T_WEAR: 測試阿霆衣著
L_WEAR: 測試Lia衣著
VOICE: 測試心事。
MOOD: 測試心情
[/FOOT]"""

def band_index_from_value(v):
    v = int(v)
    if 0 <= v <= 19:
        return 1
    if 20 <= v <= 39:
        return 2
    if 40 <= v <= 59:
        return 3
    if 60 <= v <= 74:
        return 4
    if 75 <= v <= 89:
        return 5
    if 90 <= v <= 100:
        return 6
    raise ValueError(v)

def check_output(html, ch, expected_band, char_label_map):
    """The regex emits 6 marker <i> tags per character (mk-<ch>1..6), each
    holding the matched digits or empty string. Exactly one should be
    non-empty, and it must be the expected band - that's what the CSS
    `:not(:empty)` cascade keys off in an actual browser."""
    nonempty = []
    for n in range(1, 7):
        m = re.search(rf'class="mk-{ch} mk-{ch}{n}" style="display:none">([^<]*)</i>', html)
        if m and m.group(1) != "":
            nonempty.append(n)
    ok_count = len(nonempty) == 1
    ok_band = nonempty and nonempty[0] == expected_band
    return ok_count, ok_band, nonempty

def main():
    scripts = json.load(open(SCRIPTS_PATH, encoding="utf-8"))

    test_values = [0, 5, 19, 20, 39, 40, 59, 60, 74, 75, 89, 90, 100]
    all_ok = True
    for v in test_values:
        expected = band_index_from_value(v)
        sample = make_sample(m=v, t=v, l=v, focus="馬提亞斯")
        print(f"--- M=T=L={v} (expected band {expected}) ---")
        html = apply_all_scripts(sample, scripts)
        for ch in ("m", "t", "l"):
            ok_count, ok_band, shown = check_output(html, ch, expected, None)
            status = "OK" if (ok_count and ok_band) else "FAIL"
            if status == "FAIL":
                all_ok = False
            print(f"    {ch}: shown={shown} -> {status}")

    # check the "who is focus -> which avatar defaults active" marker
    print("\n--- focus-marker check (阿霆 focus) ---")
    sample = make_sample(m=50, t=50, l=50, focus="阿霆")
    html = apply_all_scripts(sample, scripts)
    has_fm_t = re.search(r'class="rt-fm rt-fm-t"[^>]*>阿霆<', html)
    has_fm_m_empty = re.search(r'class="rt-fm rt-fm-m"[^>]*></i>', html)
    print("  fm-t populated:", bool(has_fm_t))
    print("  fm-m empty:", bool(has_fm_m_empty))
    if not (has_fm_t and has_fm_m_empty):
        all_ok = False

    # tag-balance check on a full sample
    print("\n--- tag balance check ---")
    for tag in ["div", "section", "label", "span", "footer", "details", "summary"]:
        opens = len(re.findall(rf"<{tag}\b[^>]*>", html))
        closes = len(re.findall(rf"</{tag}>", html))
        ok = opens == closes
        if not ok:
            all_ok = False
        print(f"  {tag}: {opens} open / {closes} close -> {'OK' if ok else 'MISMATCH'}")

    print("\n=== OVERALL:", "ALL PASS" if all_ok else "FAILURES FOUND", "===")

    # save one rendered sample for visual inspection
    sample = make_sample(m=68, t=30, l=15, focus="馬提亞斯")
    html = apply_all_scripts(sample, scripts)
    with open("rendered_v3_sample.html", "w", encoding="utf-8") as f:
        f.write(f"<!doctype html><html><body style='background:#1b0f17;padding:20px'>{html}</body></html>")
    print("wrote rendered_v3_sample.html")

    return 0 if all_ok else 1

if __name__ == "__main__":
    sys.exit(main())
