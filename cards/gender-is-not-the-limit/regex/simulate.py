# -*- coding: utf-8 -*-
"""Simulate SillyTavern's regex_scripts application (JS String.replace semantics)
against sample messages, to validate the v3 wheel/footer scripts before shipping.
"""
import json
import re
import sys

import build_wheel_footer as bwf

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

def apply_all_scripts(text, scripts, quiet=False):
    for s in scripts:
        if s.get("disabled"):
            continue
        text, matched = js_replace(s["findRegex"], s["replaceString"], text)
        if not quiet:
            status = "matched" if matched else "NO MATCH"
            print(f"  [{s['scriptName']}] {status}")
        elif not matched:
            print(f"  [{s['scriptName']}] NO MATCH")
    return text

def make_sample(m, t, l, focus="馬提亞斯", label="隱忍", note="測試備註",
                 m_voice="測試馬提亞斯心事。", t_voice="測試阿霆心事。", l_voice="測試Lia心事。",
                 title=None, subtitle=None, synopsis=None):
    """`focus` is whatever [HEAD]'s FOCUS field says (can be a name or 群戲 -
    it no longer drives anything technical). `label` is [WHEEL]'s LABEL,
    which is what actually determines the default avatar-switch selection
    (now 19 possible words: the 18 normal ones + Lia's lock word 親情).
    `note` is [WHEEL]'s NOTE, which the "current" wheel band now displays
    verbatim (dynamic, not the static per-band table text) until the player
    clicks to browse the phase index. `title`/`subtitle`/`synopsis` are
    omitted by default - only the 5 fixed openings set them (all three
    together), which is exactly the signal that switches frame mode."""
    title_block = f"TITLE: {title}\nSUBTITLE: {subtitle}\nSYNOPSIS: {synopsis}\n" if title is not None else ""
    return f"""[HEAD]
FOCUS: 今日焦點・{focus}
CHAPTER: Kapitel I
TIME: 19:00
LOC: 新竹老宅・餐廳
WEATHER: 起風
LEAD: 測試用引言。
{title_block}[/HEAD]

[BODY]
這是測試用的正文內容，用來確認 BODY 區段的比對不會被 WHEEL/FOOT 的規則誤吃。
[/BODY]

[WHEEL]
ROT: 0
ROMAN: Akt III
LABEL: {label}
NOTE: {note}
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
U_POSE: 測試你的姿勢
M_POSE: 測試馬提亞斯姿勢
T_POSE: 測試阿霆姿勢
L_POSE: 測試Lia姿勢
M_VOICE: {m_voice}
T_VOICE: {t_voice}
L_VOICE: {l_voice}
MOOD: 測試心情
[/FOOT]"""

# Must mirror THRESHOLDS in build_wheel_footer.py - Matthias paces evenly,
# Ating/Lia share a different (uneven) table for bands 3-6.
THRESHOLDS = {
    "m": [(0, 19), (20, 39), (40, 59), (60, 74), (75, 89), (90, 100)],
    "t": [(0, 19), (20, 39), (40, 54), (55, 69), (70, 84), (85, 100)],
    "l": [(0, 19), (20, 39), (40, 54), (55, 69), (70, 84), (85, 100)],
}

def band_index_from_value(v, ch):
    v = int(v)
    for i, (lo, hi) in enumerate(THRESHOLDS[ch], start=1):
        if lo <= v <= hi:
            return i
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

    # boundary values that matter for at least one character's table:
    # 0/19/20/39/40/54/55/59/60/69/70/74/75/84/85/89/90/100
    test_values = [0, 19, 20, 39, 40, 54, 55, 59, 60, 69, 70, 74, 75, 84, 85, 89, 90, 100]
    all_ok = True
    for ch in ("m", "t", "l"):
        for v in test_values:
            expected = band_index_from_value(v, ch)
            vals = {"m": 50, "t": 50, "l": 50}
            vals[ch] = v
            sample = make_sample(m=vals["m"], t=vals["t"], l=vals["l"], focus="馬提亞斯")
            html = apply_all_scripts(sample, scripts, quiet=True)
            ok_count, ok_band, shown = check_output(html, ch, expected, None)
            status = "OK" if (ok_count and ok_band) else "FAIL"
            if status == "FAIL":
                all_ok = False
                print(f"--- {ch}={v} (expected band {expected}) --- shown={shown} -> {status}")
    print(f"boundary sweep: {len(test_values)*3} checks run, {'all OK' if all_ok else 'FAILURES ABOVE'}")

    # check the "who is focus -> which avatar defaults active" marker.
    # Driven by [WHEEL]'s LABEL now (not [HEAD]'s FOCUS name), specifically
    # so a FOCUS of "群戲" (group scene - a real, common, previously-fatal
    # case) still works: RT_頭卡 no longer requires a name match at all.
    print("\n--- focus-marker check (WHEEL LABEL=賭氣, i.e. Ating, FOCUS=群戲) ---")
    sample = make_sample(m=50, t=50, l=50, focus="群戲", label="賭氣")
    html = apply_all_scripts(sample, scripts)
    has_fm_t = re.search(r'class="rt-fm rt-fm-t"[^>]*>賭氣<', html)
    has_fm_m_empty = re.search(r'class="rt-fm rt-fm-m"[^>]*></i>', html)
    print("  fm-t populated:", bool(has_fm_t))
    print("  fm-m empty:", bool(has_fm_m_empty))
    if not (has_fm_t and has_fm_m_empty):
        all_ok = False

    print("\n--- LABEL alternation check (18 normal words + Lia's lock word) ---")
    LABEL_WORDS = {
        "m": ["戒備", "動搖", "隱忍", "試探", "失控", "坦白"],
        "t": ["裝傻", "破功", "吃味", "賭氣", "認輸", "重來"],
        "l": ["疼愛", "試溫", "貼近", "明示", "等待", "卸甲"],
    }
    for ch, words in LABEL_WORDS.items():
        for w in words:
            sample = make_sample(m=50, t=50, l=50, focus="群戲", label=w)
            html2 = apply_all_scripts(sample, scripts, quiet=True)
            fm = re.search(rf'class="rt-fm rt-fm-{ch}"[^>]*>([^<]*)</i>', html2)
            ok = bool(fm and fm.group(1) == w)
            if not ok:
                all_ok = False
                print(f"  LABEL={w} (expect fm-{ch} populated) -> FAIL: {fm.group(1) if fm else 'no match'}")
    sample = make_sample(m=50, t=50, l=50, focus="群戲", label=bwf.LOCK_LABEL_L)
    html2 = apply_all_scripts(sample, scripts, quiet=True)
    fm_l = re.search(r'class="rt-fm rt-fm-l"[^>]*>([^<]*)</i>', html2)
    ok_lock_fm = bool(fm_l and fm_l.group(1) == bwf.LOCK_LABEL_L)
    if not ok_lock_fm:
        all_ok = False
        print(f"  LABEL={bwf.LOCK_LABEL_L} (Lia lock, expect fm-l populated) -> FAIL: {fm_l.group(1) if fm_l else 'no match'}")
    print("  18/18 normal + lock word checked" if all_ok else "  see failures above")

    # TITLE/SUBTITLE/SYNOPSIS optional trio -> frame-mode switch check
    print("\n--- TITLE/SUBTITLE/SYNOPSIS optional-field (frame mode) check ---")
    sample_notitle = make_sample(m=50, t=50, l=50)
    html_notitle = apply_all_scripts(sample_notitle, scripts, quiet=True)
    flag_empty = re.search(r'class="rt-title-flag" style="display:none"></i>', html_notitle)
    has_shell_open = '<div class="rt-shell">' in html_notitle
    print("  no TITLE -> flag empty:", bool(flag_empty), "| .rt-shell present:", has_shell_open)
    if not (flag_empty and has_shell_open):
        all_ok = False

    sample_title = make_sample(
        m=50, t=50, l=50,
        title="餐桌上的沉默", subtitle="他把未竟之言，都留在多添的那碗湯裡",
        synopsis="新竹入秋的晚風從天井灌進老宅，他把最後一道湯放下，目光在你身上停了半秒，比平常久。",
    )
    html_title = apply_all_scripts(sample_title, scripts, quiet=True)
    flag_populated = re.search(r'class="rt-title-flag" style="display:none">餐桌上的沉默</i>', html_title)
    has_header = '<div class="rt-kicker">Kapitel I · 馬提亞斯</div><h1>餐桌上的沉默</h1><div class="rt-subtitle">他把未竟之言，都留在多添的那碗湯裡</div>' in html_title
    has_synopsis = '<p class="rt-synopsis">新竹入秋的晚風從天井灌進老宅' in html_title
    has_shell = '<div class="rt-shell">' in html_title
    has_frame_head = 'class="rt-frame rt-frame-head"' in html_title
    has_frame_foot = 'rt-footer rt-frame rt-frame-foot' in html_title
    has_focus_caption = 'FOCUS · 馬提亞斯' in html_title
    print("  TITLE given -> flag populated:", bool(flag_populated), "| header html:", has_header,
          "| synopsis:", has_synopsis, "| shell:", has_shell,
          "| frame-head class:", has_frame_head, "| frame-foot class:", has_frame_foot,
          "| English FOCUS caption:", has_focus_caption)
    if not (flag_populated and has_header and has_synopsis and has_shell and has_frame_head and has_frame_foot and has_focus_caption):
        all_ok = False

    # English structural captions in the head/foot cards
    print("\n--- English head/foot caption check ---")
    sample = make_sample(m=50, t=50, l=50)
    html_cap = apply_all_scripts(sample, scripts, quiet=True)
    captions_ok = True
    for needle in ["FOCUS · 馬提亞斯", ">TIME<", ">LOCATION<", ">WEATHER<", ">HEAT<", ">YOU<", "SECRET: "]:
        if needle not in html_cap:
            captions_ok = False
            print(f"  missing caption: {needle!r}")
    print("  English captions present:", captions_ok)
    if not captions_ok:
        all_ok = False

    # per-character VOICE ("心事"/SECRET) switching + 不在場 check
    print("\n--- per-character SECRET (VOICE) switching check ---")
    sample = make_sample(m=50, t=50, l=50, focus="馬提亞斯", label="隱忍",
                          m_voice="馬提亞斯的心事", t_voice="不在場", l_voice="不在場")
    html_voice = apply_all_scripts(sample, scripts, quiet=True)
    voice_rows_ok = True
    for ch, text in (("m", "馬提亞斯的心事"), ("t", "不在場"), ("l", "不在場")):
        m = re.search(rf'class="rt-voice-row stat-{ch}"[^>]*><b[^>]*>SECRET: </b>([^<]*)</div>', html_voice)
        if not (m and m.group(1) == text):
            voice_rows_ok = False
            print(f"  stat-{ch} SECRET row -> expected {text!r}, got {m.group(1) if m else None!r}")
    # default visibility: only stat-m row should show (mk-m/rt-fm-m focus),
    # stat-t/stat-l rows exist in the markup but are CSS-hidden by default
    # (can't check computed CSS here, but marker+row presence together is
    # what drives it in a real browser - already covered by the switch_css
    # rules being generated per character symmetrically to wear/pose).
    print("  all 3 SECRET rows carry correct text (incl. 不在場 for absent):", voice_rows_ok)
    if not voice_rows_ok:
        all_ok = False

    # dynamic NOTE check: the "current" (marker-matched) band must show
    # this turn's captured NOTE text verbatim, not the static per-band table
    # text - that's the whole point of making it MVU-driven instead of a
    # fixed lookup.
    print("\n--- dynamic NOTE (current band) check ---")
    fresh_note = "這次的藉口比昨天更薄了"
    sample = make_sample(m=45, t=50, l=50, focus="馬提亞斯", label="隱忍", note=fresh_note)
    html_note = apply_all_scripts(sample, scripts, quiet=True)
    dyn_shown = f'<small class="nt-dyn" style="display:block;color:#ad8f88;font-size:9px;letter-spacing:.13em;line-height:1.5;">{fresh_note}</small>' in html_note
    static_present_but_hidden = 'class="nt-static" style="display:none' in html_note
    # the static table note for band III/隱忍 must still be present verbatim
    # (that's what phase-browsing falls back to) and must NOT itself equal
    # this turn's fresh note - i.e. dynamic and static really are two
    # different texts, not the same string rendered twice.
    static_table_text = bwf.PHASE["m"]["bands"][2][2]
    static_shown_is_table_text = f'<small class="nt-static" style="display:none;color:#ad8f88;font-size:9px;letter-spacing:.13em;line-height:1.5;">{static_table_text}</small>' in html_note
    print("  nt-dyn span carries this turn's fresh NOTE:", dyn_shown,
          "| nt-static spans present (for phase-browsing) and default-hidden:", static_present_but_hidden,
          "| nt-static still holds the fixed table text (distinct from fresh NOTE):", static_shown_is_table_text)
    if not (dyn_shown and static_present_but_hidden and static_shown_is_table_text):
        all_ok = False

    # Lia-lock band check: LABEL=親情 must produce a dedicated locked band
    # (mk-l-lock marker populated, bd-l-lock present) independent of L's
    # numeric favorability value, per system_prompt.md <Lia_Lock>.
    print("\n--- Lia-lock wheel band check ---")
    lock_note = "還是會擔心你，只是擔心的方式變了"
    sample = make_sample(m=50, t=50, l=72, focus="Lia", label=bwf.LOCK_LABEL_L, note=lock_note)
    html_lock = apply_all_scripts(sample, scripts, quiet=True)
    mk_lock_populated = re.search(r'class="mk-l-lock" style="display:none">([^<]*)</i>', html_lock)
    has_lock_div = '<div class="bd-l-lock" style="display:none">' in html_lock
    has_lock_label = f'<strong style="display:block;margin:5px 0 3px;color:#f0ddc3;font-size:clamp(15px,3.4vw,20px);font-weight:600;letter-spacing:.18em;">{bwf.LOCK_LABEL_L}</strong>' in html_lock
    has_lock_note = f'<small style="display:block;color:#ad8f88;font-size:9px;letter-spacing:.13em;line-height:1.5;">{lock_note}</small>' in html_lock
    has_lock_css = f'.mk-l-lock:not(:empty) ~ .char-l .rt-pointer-l {{ transform: rotate({bwf.LOCK_ROT_L}deg); }}' in html_lock
    print("  mk-l-lock marker populated:", bool(mk_lock_populated and mk_lock_populated.group(1) == bwf.LOCK_LABEL_L),
          "| bd-l-lock div present:", has_lock_div, "| lock LABEL rendered:", has_lock_label,
          "| lock NOTE rendered dynamically:", has_lock_note, "| lock CSS override present:", has_lock_css)
    if not (mk_lock_populated and mk_lock_populated.group(1) == bwf.LOCK_LABEL_L and has_lock_div and has_lock_label and has_lock_note and has_lock_css):
        all_ok = False

    # intra-wheel 6-phase click-browsing check
    print("\n--- phase-browsing wheel positions check ---")
    sample = make_sample(m=50, t=50, l=50)
    html_phase = apply_all_scripts(sample, scripts, quiet=True)
    phase_labels = re.findall(
        r'<label class="rt-phase p(\d)"[^>]*><input type="radio"[^>]*class="rt-phase-radio">([^<]*)</label>',
        html_phase,
    )
    print(f"  found {len(phase_labels)} phase-radio labels (expect 18)")
    ok_phase = len(phase_labels) == 18
    if ok_phase:
        order = ["m"] * 6 + ["t"] * 6 + ["l"] * 6
        for idx, (pos_str, word) in enumerate(phase_labels):
            pos = int(pos_str)
            ch = order[idx]
            expected_word = bwf.PHASE[ch]["bands"][bwf.POS_TO_BAND[pos] - 1][1]
            if word != expected_word:
                ok_phase = False
                print(f"  [{idx}] ch={ch} pos={pos}: got {word!r} expected {expected_word!r}")
    print("  18 position->word mappings correct:", ok_phase)
    if not ok_phase:
        all_ok = False

    css_ok = True
    for ch in ("m", "t", "l"):
        for pos in range(1, 7):
            band = bwf.POS_TO_BAND[pos]
            rot = bwf.BAND_ROT[band - 1]
            needle = f'.char-{ch}:has(.p{pos} input:checked) .rt-pointer-{ch} {{ transform: rotate({rot}deg); }}'
            if needle not in html_phase:
                css_ok = False
                print("  missing CSS rule:", needle)
    print("  phase-click CSS rotate rules present:", css_ok)
    if not css_ok:
        all_ok = False

    # regression check for the "clicking a new phase doesn't clear the old
    # one, text keeps stacking up" bug: all 6 radios for a given character
    # must share one `name` (otherwise unnamed radios aren't mutually
    # exclusive at all and every click just adds another :checked one).
    print("\n--- phase-radio name-grouping check (regression) ---")
    names_ok = True
    all_names = re.findall(r'<input type="radio" name="([^"]*)" class="rt-phase-radio">', html_phase)
    if len(all_names) != 18:
        names_ok = False
        print(f"  expected 18 named phase radios, found {len(all_names)}")
    else:
        by_char = {"m": all_names[0:6], "t": all_names[6:12], "l": all_names[12:18]}
        for ch, group in by_char.items():
            if len(set(group)) != 1:
                names_ok = False
                print(f"  ch={ch}: radios don't share one name -> {set(group)}")
        if len({n for g in by_char.values() for n in g}) != 3:
            names_ok = False
            print("  the 3 characters' radio groups are not distinct from each other")
    print("  all 6 radios per wheel share one name (mutually exclusive):", names_ok)
    if not names_ok:
        all_ok = False

    # tag-balance check on a full sample
    print("\n--- tag balance check ---")
    for tag in ["div", "section", "label", "span", "footer", "details", "summary", "i", "h1", "p"]:
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
