# -*- coding: utf-8 -*-
"""
Build the production regex_scripts for the switchable wheel + footer.

Design (see conversation for full rationale):
- RT_頭卡: unchanged head-card render, PLUS emits 3 hidden "who is focus" markers
  (rt-fm-m / rt-fm-t / rt-fm-l) so later scripts can default the avatar switch
  to whoever is narratively focused this turn, purely via string matching on
  the FOCUS field (no numeric logic needed here).
- RT_正文: unchanged.
- RT_花冠尾卡 (NEW, replaces RT_花冠轉盤 + RT_尾卡): one combined script that
  spans [WHEEL]...[/WHEEL] through [FOOT]...[/FOOT] (they're adjacent in the
  output format, so this is a safe non-greedy span - it never touches BODY).
  It renders:
    * 3 wheel-sections (Matthias / Ating / Lia), each showing ALL its own
      current-phase text statically per character (no per-turn LLM writing
      needed for the two non-focus characters) - which band is "current" is
      computed purely from the M/T/L numbers via regex numeric-range
      alternation (no arithmetic, just digit-pattern matching), using an
      "empty vs non-empty capture group" + CSS `:not(:empty)` sibling trick
      since replaceString can't conditionally emit literal text.
    * one avatar-switcher row that shows/hides the 3 wheel-sections and
      highlights the matching stat/wear rows in the footer. Default
      selection = whoever RT_頭卡 marked focus; clicking a different avatar
      overrides it (implemented as a 3-layer CSS cascade: marker-default ->
      blanket-hide-once-any-checked -> :has()-based specific re-show, so
      the two mechanisms don't fight). The radio for each avatar is nested
      *inside* its own <label> rather than linked via id/for, and the
      show/hide rules use :has() to reach outside the label - this message's
      markup repeats verbatim in every chat turn, so id="rtf-m" would NOT be
      unique across a long conversation, and `label[for]` binds to the
      first same-id element in the WHOLE document (not the one visually
      nearby), which is why an id/for version silently toggles the wrong
      message. Radio `name` is still seeded with the M/T/L digits as a
      cheap (not perfect) reduction of cross-message radio-group crosstalk,
      since `name` grouping is also page-global.
    * the footer: status grid (unchanged, all 3 numbers always shown+highlit),
      clothing row (you = always shown; the 3 NPCs = switchable, one at a
      time), quote/mood (always tied to the focus character, per the user's
      explicit choice not to make VOICE switchable), wrapped in
      <details>/<summary> so it's collapsible. The 心事 seal now shows the
      focus character's own photo (was a plain "誓" glyph placeholder).
"""
import json
import os
import re

AV_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "avatars")

def b64(name):
    return open(f"{AV_DIR}/{name}.b64", encoding="utf-8").read().strip()

AVATAR = {
    "m": b64("matthias"),
    "t": b64("ating"),
    "l": b64("lia"),
}
AV_NAME = {"m": "馬提亞斯", "t": "阿霆", "l": "Lia"}

# band index 0..5 = favorability bands 0-19/20-39/40-59/60-74/75-89/90-100
PHASE = {
    "m": {
        "roman": "Akt",
        "bands": [
            ("I", "戒備", "用禮貌把心事鎖進抽屜"),
            ("II", "動搖", "不小心多看了一眼，來不及收回"),
            ("III", "隱忍", "克制下的灼熱凝視"),
            ("IV", "試探", "指尖之間，藉口越來越薄"),
            ("V", "失控", "理智潰散，只剩下想靠近的本能"),
            ("VI", "坦白", "把多年的沉默，換成一句真話"),
        ],
    },
    "t": {
        "roman": "Akt",
        "bands": [
            ("I", "裝傻", "刻意不碰舊話題，笑著帶過"),
            ("II", "破功", "提起以前的時候，語氣沒收好"),
            ("III", "吃味", "看到你跟別人靠近，笑容慢半拍"),
            ("IV", "賭氣", "鬧脾氣，但死也不說為什麼"),
            ("V", "認輸", "承認自己從來沒有真的放下"),
            ("VI", "重來", "願意再賭一次，這次不先鬆手"),
        ],
    },
    "l": {
        "roman": "Atto",
        "bands": [
            ("I", "疼愛", "長輩式的溫柔，界線清楚"),
            ("II", "試溫", "說一些界線模糊的話，然後看你"),
            ("III", "貼近", "製造機會，然後停下來等你"),
            ("IV", "明示", "毫不掩飾，但把選擇權交回你手上"),
            ("V", "等待", "她可以等，而且讓你知道她在等"),
            ("VI", "卸甲", "第一次露出不安"),
        ],
    },
}
BAND_ROT = [240, 300, 0, 60, 120, 180]

# Favorability thresholds per character (system_prompt.md <Phases>).
# Matthias paces evenly (20/20/20/15/15/11); Ating and Lia share a faster,
# unevenly-spaced table for bands 3-6 (15/15/15/16) - NOT the same as
# Matthias's, even though bands 1-2 happen to coincide (0-19/20-39).
THRESHOLDS = {
    "m": [(0, 19), (20, 39), (40, 59), (60, 74), (75, 89), (90, 100)],
    "t": [(0, 19), (20, 39), (40, 54), (55, 69), (70, 84), (85, 100)],
    "l": [(0, 19), (20, 39), (40, 54), (55, 69), (70, 84), (85, 100)],
}

def int_range_regex(lo, hi):
    """Build a regex alternation (no arithmetic, pure digit-pattern matching)
    that matches any integer string in [lo, hi], for 0 <= lo <= hi <= 100."""
    parts = []
    if lo <= 9:
        upper = min(hi, 9)
        parts.append('[0-9]' if (lo == 0 and upper == 9) else f'[{lo}-{upper}]')
        lo = 10
    if lo <= hi:
        hi_, include_100 = (99, True) if hi == 100 else (hi, False)
        if lo <= hi_:
            tens_lo, tens_hi = lo // 10, hi_ // 10
            for t in range(tens_lo, tens_hi + 1):
                d_lo = lo - t * 10 if t == tens_lo else 0
                d_hi = hi_ - t * 10 if t == tens_hi else 9
                if d_lo == 0 and d_hi == 9:
                    parts.append(f'{t}[0-9]')
                elif d_lo == d_hi:
                    parts.append(f'{t}{d_lo}')
                else:
                    parts.append(f'{t}[{d_lo}-{d_hi}]')
        if include_100:
            parts.append('100')
    return '|'.join(parts)

def band_regex(ch):
    """6 capturing groups, one per favorability band, for character ch."""
    return "(?:" + "|".join(f"({int_range_regex(lo, hi)})" for lo, hi in THRESHOLDS[ch]) + ")"

WHEEL_BG_SVG = (
    '<svg viewBox="0 0 400 400" style="position:absolute;inset:0;width:100%;height:100%;overflow:visible;">'
    '<defs><radialGradient id="rtgW{X}" cx="50%" cy="48%" r="52%">'
    '<stop offset="0" stop-color="#6f293f" stop-opacity=".23"/>'
    '<stop offset=".66" stop-color="#22131d" stop-opacity=".14"/>'
    '<stop offset="1" stop-color="#0f0910" stop-opacity=".8"/></radialGradient></defs>'
    '<circle cx="200" cy="200" r="175" fill="url(#rtgW{X})" stroke="#b98952" stroke-width="1"/>'
    '<circle cx="200" cy="200" r="167" fill="none" stroke="#70354a" stroke-width="3"/>'
    '<circle cx="200" cy="200" r="160" fill="none" stroke="#c6a06b" stroke-width=".8" stroke-dasharray="1 5"/>'
    '<circle cx="200" cy="200" r="141" fill="none" stroke="#9d7247" stroke-width=".75"/>'
    '<circle cx="200" cy="200" r="132" fill="none" stroke="#5e3042" stroke-width="1"/>'
    '<g fill="none" stroke="#a77a4c" stroke-width=".8" opacity=".92">'
    '<path d="M200 22c-8 19-26 27-42 17 5-18 22-30 42-17Z"/><path d="M200 22c8 19 26 27 42 17-5-18-22-30-42-17Z"/>'
    '<path d="M378 200c-19-8-27-26-17-42 18 5 30 22 17 42Z"/><path d="M378 200c-19 8-27 26-17 42 18-5 30-22 17-42Z"/>'
    '<path d="M200 378c-8-19-26-27-42-17 5 18 22 30 42 17Z"/><path d="M200 378c8-19 26-27 42-17-5 18-22 30-42 17Z"/>'
    '<path d="M22 200c19-8 27-26 17-42-18 5-30 22-17 42Z"/><path d="M22 200c19 8 27 26 17 42-18-5-30-22-17-42Z"/></g>'
    '<g fill="none" stroke="#754058" stroke-width=".75">'
    '<path d="M200 58C238 91 273 96 316 84M342 200c-33 38-38 73-26 116M200 342c-38-33-73-38-116-26M58 200c33-38 38-73 26-116"/>'
    '<path d="M200 58c-38 33-73 38-116 26M342 200c-33-38-38-73-26-116M200 342c38-33 73-38 116-26M58 200c33 38 38 73 26 116"/></g>'
    '<g stroke="#7d5360" stroke-width=".7" opacity=".65">'
    '<path d="M200 68V142M314 134l-64 37M314 266l-64-37M200 332v-74M86 266l64-37M86 134l64 37"/></g>'
    '<g fill="#cba46b"><circle cx="200" cy="68" r="2.6"/><circle cx="314" cy="134" r="2.6"/><circle cx="314" cy="266" r="2.6"/>'
    '<circle cx="200" cy="332" r="2.6"/><circle cx="86" cy="266" r="2.6"/><circle cx="86" cy="134" r="2.6"/></g>'
    '<g fill="none" stroke="#b98854" stroke-width=".8">'
    '<path d="M200 178c13-18 31-11 31 4 0 16-31 36-31 36s-31-20-31-36c0-15 18-22 31-4Z"/></g></svg>'
)

# visual ring position (1=top, going clockwise) -> which band's dot the
# background SVG actually draws there. Fixed by the SVG artwork/ROT angles,
# not something to reorder freely.
POS_TO_BAND = {1: 3, 2: 4, 3: 5, 4: 6, 5: 1, 6: 2}
PHASE_POS_STYLE = {
    1: "top:6.5%;left:calc(50% - 39px);",
    2: "top:25%;right:-2%;",
    3: "right:3%;bottom:17%;",
    4: "bottom:5.5%;left:calc(50% - 39px);",
    5: "bottom:17%;left:3%;",
    6: "top:25%;left:-2%;",
}

def build_wheel_section(ch, name_seed):
    p = PHASE[ch]
    band_divs = "".join(
        f'<div class="bd-{ch}-{i+1}">'
        f'<span style="display:block;color:#a57d4e;font:italic 500 13px/1 \'Cormorant Garamond\',serif;letter-spacing:.12em;">{p["roman"]} {num}</span>'
        f'<strong style="display:block;margin:5px 0 3px;color:#f0ddc3;font-size:clamp(15px,3.4vw,20px);font-weight:600;letter-spacing:.18em;">{label}</strong>'
        f'<small style="display:block;color:#ad8f88;font-size:9px;letter-spacing:.13em;line-height:1.5;">{note}</small>'
        f'</div>'
        for i, (num, label, note) in enumerate(p["bands"])
    )
    # 6 clickable positions around the ring, letting the player browse all
    # six phases for this character - independent of the avatar-switch and
    # the marker-driven "current" default. Each radio is wrapped inside its
    # own <label> (no id/for - see switch_css comment on why) and the CSS
    # keys off the label's own p1..p6 class via :has(), not nth-of-type,
    # since nth-of-type can't distinguish radios that each live inside a
    # different parent <label>. All 6 MUST share one `name` - without it,
    # unnamed radios aren't grouped as mutually exclusive at all (each one
    # toggles independently), so clicking a new position never unchecked the
    # previous one and every previously-clicked band div stayed visible,
    # stacking up instead of being replaced (the "text keeps getting longer"
    # bug). `name` is seeded with this message's own favorability value the
    # same way RADIO_NAME is below, to cut down (not eliminate) cross-message
    # radio-group crosstalk, since `name` grouping is page-global.
    phase_radio_name = f"rt-phase-{ch}-{name_seed}"
    phase_labels = "".join(
        f'<label class="rt-phase p{pos}" style="{PHASE_POS_STYLE[pos]}">'
        f'<input type="radio" name="{phase_radio_name}" class="rt-phase-radio">{p["bands"][POS_TO_BAND[pos]-1][1]}</label>'
        for pos in range(1, 7)
    )
    return f'''<section class="rt-wheel-section char-{ch}" aria-label="{AV_NAME[ch]}・情感命運花冠" style="position:relative;width:min(100%,340px);aspect-ratio:1;margin:0 auto 18px;font-family:'Noto Serif TC','Songti TC',serif;">
{WHEEL_BG_SVG.replace("{X}", ch)}
<div class="rt-pointer-{ch}" style="position:absolute;z-index:4;top:7.4%;left:calc(50% - 5px);width:10px;height:42.6%;transform-origin:50% 100%;">
<div style="position:absolute;top:0;left:50%;width:1px;height:100%;background:linear-gradient(#efd69d,rgba(199,148,83,.1));box-shadow:0 0 7px rgba(235,188,113,.45);"></div>
<div style="position:absolute;top:-7px;left:50%;transform:translateX(-50%);color:#ecd39f;font-size:12px;">◆</div>
</div>
<div class="rt-wheel-center-{ch}" style="position:absolute;z-index:5;inset:30.2%;display:grid;place-items:center;border:1px solid rgba(221,182,114,.7);border-radius:50%;background:radial-gradient(circle,rgba(99,39,58,.52),rgba(28,15,24,.98) 68%);box-shadow:inset 0 0 0 5px rgba(29,16,25,.95),inset 0 0 0 6px rgba(190,145,85,.42),0 0 22px rgba(121,42,69,.27);text-align:center;">
<div style="max-width:84%;">{band_divs}</div>
</div>
{phase_labels}
</section>'''

def wheel_css(ch):
    rules = []
    for i in range(6):
        n = i + 1
        rot = BAND_ROT[i]
        rules.append(
            f'.mk-{ch}{n}:not(:empty) ~ .char-{ch} .rt-pointer-{ch} {{ transform: rotate({rot}deg); }}\n'
            f'.mk-{ch}{n}:not(:empty) ~ .char-{ch} .rt-wheel-center-{ch} .bd-{ch}-{n} {{ display: block; }}'
        )
    # phase-browsing overrides: once ANY of this wheel's 6 positions is
    # clicked, blanket-hide all 6 band divs, then re-show only the clicked
    # one (higher specificity via the extra .p{pos} class wins the tie).
    rules.append(
        f'.char-{ch}:has(.rt-phase-radio:checked) .rt-wheel-center-{ch} .bd-{ch}-1,\n'
        f'.char-{ch}:has(.rt-phase-radio:checked) .rt-wheel-center-{ch} .bd-{ch}-2,\n'
        f'.char-{ch}:has(.rt-phase-radio:checked) .rt-wheel-center-{ch} .bd-{ch}-3,\n'
        f'.char-{ch}:has(.rt-phase-radio:checked) .rt-wheel-center-{ch} .bd-{ch}-4,\n'
        f'.char-{ch}:has(.rt-phase-radio:checked) .rt-wheel-center-{ch} .bd-{ch}-5,\n'
        f'.char-{ch}:has(.rt-phase-radio:checked) .rt-wheel-center-{ch} .bd-{ch}-6 {{ display: none; }}'
    )
    for pos in range(1, 7):
        band = POS_TO_BAND[pos]
        rot = BAND_ROT[band - 1]
        rules.append(
            f'.char-{ch}:has(.p{pos} input:checked) .rt-pointer-{ch} {{ transform: rotate({rot}deg); }}\n'
            f'.char-{ch}:has(.p{pos} input:checked) .rt-wheel-center-{ch} .bd-{ch}-{band} {{ display: block; }}\n'
            f'.char-{ch}:has(.p{pos} input:checked) .p{pos} {{ color: #f0d6ad; text-shadow: 0 0 13px rgba(235,181,109,.52); transform: scale(1.06); }}'
        )
    return "\n".join(rules)

def main():
    css_parts = []
    for ch in ("m", "t", "l"):
        css_parts.append(wheel_css(ch))
    wheel_css_all = "\n".join(css_parts)

    bd_hide_selector = ",\n".join(f".bd-{ch}-{n}" for ch in ("m", "t", "l") for n in range(1, 7))

    # `.rt-scope` used to be the single big bordered frame wrapping the whole
    # message (head->body->wheel->footer). Body length varies wildly (a
    # couple hundred characters up to ~1200+), and a single tall bordered
    # box either looked awkwardly empty or forced the frame to stretch with
    # it. Split it: `.rt-scope` is now an *invisible* wrapper (box-sizing
    # reset + font/color inheritance only, no border/background) so the
    # sibling-selector plumbing between head/wheel/footer still works
    # regardless of body length; the gold double-ring + corner ornaments
    # move onto `.rt-frame`, a reusable bordered "bookend" card applied
    # separately to the head-card and the footer, with body+wheel floating
    # unframed and unconstrained in between.
    shell_css = '''
.rt-scope, .rt-scope * { box-sizing: border-box; }
.rt-scope {
  display: block;
  color: #efe2ce;
  font-family: "Noto Serif TC", "Songti TC", serif;
}
.rt-frame {
  position: relative;
  overflow: hidden;
  border: 1px solid #a97945;
  border-radius: 5px;
  background:
    radial-gradient(circle at 50% 18%, rgba(126, 45, 70, .24), transparent 40%),
    linear-gradient(145deg, rgba(255,255,255,.02), transparent 42%),
    #160e16;
  box-shadow: inset 0 0 0 3px #21131c, inset 0 0 0 4px rgba(184,137,78,.42), 0 10px 30px rgba(14,4,12,.35);
}
.rt-frame::before, .rt-frame::after {
  content: ""; position: absolute; pointer-events: none; inset: 6px;
  border: 1px solid rgba(202, 162, 100, .36);
}
.rt-frame::after { inset: 9px; border-style: double; border-width: 3px; border-color: rgba(106, 43, 61, .78); }
.rt-frame-corner {
  position: absolute; z-index: 2; width: 38px; height: 38px; color: #c69b5f; opacity: .75; pointer-events: none;
}
.rt-frame-corner svg { width: 100%; height: 100%; }
.rt-frame-corner.nw { top: 6px; left: 6px; }
.rt-frame-corner.ne { top: 6px; right: 6px; transform: scaleX(-1); }
.rt-frame-corner.sw { bottom: 6px; left: 6px; transform: scaleY(-1); }
.rt-frame-corner.se { bottom: 6px; right: 6px; transform: scale(-1); }

/* Openings (the 5 fixed first_mes/alternate_greetings) carry an optional
   TITLE/SUBTITLE/SYNOPSIS trio that ordinary AI-generated turns never emit.
   Its presence is the sole signal, via the .rt-title-flag marker below, that
   switches from the default "two independent bookend cards" look (used from
   page 2 onward, since body length varies too much per turn for one
   continuous frame to look right) to the original "one full-wrap cover
   frame" the 5 openings were designed with - a single bordered .rt-shell
   wraps a kicker/title/subtitle header, a synopsis line, the head-card, the
   body+wheel, and the footer together, exactly like the reference mockup.
   .rt-shell is always opened at the start of RT_頭卡 and closed at the end
   of RT_花冠尾卡; by default it draws no border/background at all (a no-op
   passthrough, so .rt-frame-head/.rt-frame-foot keep their own independent
   bookend-card borders) and only becomes the single visible frame - with
   .rt-frame-head/.rt-frame-foot's own borders suppressed so there's exactly
   one border, not three - when the flag is non-empty. */
.rt-title-flag { display: none; }
.rt-shell { display: block; }
.rt-shell-corner { display: none; }
.rt-header { display: none; }
.rt-synopsis { display: none; }
.rt-title-flag:not(:empty) ~ .rt-shell {
  position: relative; overflow: hidden;
  width: min(100%,420px); margin: 14px auto 18px; padding: 20px 17px 17px;
  border: 1px solid #a97945; border-radius: 6px;
  background:
    radial-gradient(circle at 50% 18%, rgba(126, 45, 70, .24), transparent 40%),
    linear-gradient(145deg, rgba(255,255,255,.02), transparent 42%),
    #160e16;
  box-shadow: inset 0 0 0 3px #21131c, inset 0 0 0 4px rgba(184,137,78,.42), 0 10px 30px rgba(14,4,12,.35);
}
.rt-title-flag:not(:empty) ~ .rt-shell::before,
.rt-title-flag:not(:empty) ~ .rt-shell::after {
  content: ""; position: absolute; pointer-events: none; inset: 7px;
  border: 1px solid rgba(202, 162, 100, .36);
}
.rt-title-flag:not(:empty) ~ .rt-shell::after { inset: 10px; border-style: double; border-width: 3px; border-color: rgba(106, 43, 61, .78); }
.rt-title-flag:not(:empty) ~ .rt-shell .rt-shell-corner { display: block; }
.rt-title-flag:not(:empty) ~ .rt-shell .rt-header { display: block; }
.rt-title-flag:not(:empty) ~ .rt-shell .rt-synopsis { display: block; }
.rt-title-flag:not(:empty) ~ .rt-shell .rt-frame-head,
.rt-title-flag:not(:empty) ~ .rt-shell .rt-frame-foot {
  border: none; border-radius: 0; box-shadow: none; background: none;
}
.rt-title-flag:not(:empty) ~ .rt-shell .rt-frame-head::before,
.rt-title-flag:not(:empty) ~ .rt-shell .rt-frame-head::after,
.rt-title-flag:not(:empty) ~ .rt-shell .rt-frame-foot::before,
.rt-title-flag:not(:empty) ~ .rt-shell .rt-frame-foot::after { content: none; }
.rt-title-flag:not(:empty) ~ .rt-shell .rt-frame-head .rt-frame-corner,
.rt-title-flag:not(:empty) ~ .rt-shell .rt-frame-foot .rt-frame-corner { display: none; }
.rt-title-flag:not(:empty) ~ .rt-shell .rt-footer.rt-frame-foot {
  border-top: 1px solid rgba(189,145,89,.3); padding-top: 16px;
}

.rt-shell-corner {
  position: absolute; z-index: 2; width: 46px; height: 46px; color: #c69b5f; opacity: .78; pointer-events: none;
}
.rt-shell-corner svg { width: 100%; height: 100%; }
.rt-shell-corner.nw { top: 8px; left: 8px; }
.rt-shell-corner.ne { top: 8px; right: 8px; transform: scaleX(-1); }
.rt-shell-corner.sw { bottom: 8px; left: 8px; transform: scaleY(-1); }
.rt-shell-corner.se { bottom: 8px; right: 8px; transform: scale(-1); }

.rt-header { position: relative; z-index: 3; padding: 4px 6px 16px; text-align: center; }
.rt-kicker { color: #b9905d; font: 600 10.5px/1.4 "Cormorant Garamond", serif; letter-spacing: .3em; text-transform: uppercase; }
.rt-header h1 { margin: 6px 0 4px; color: #f4e8d4; font-size: clamp(21px,5.6vw,28px); font-weight: 500; letter-spacing: .17em; text-indent: .17em; text-shadow: 0 1px 18px rgba(217,165,112,.15); }
.rt-header .rt-subtitle { color: #a98f86; font-size: 11px; letter-spacing: .16em; }
.rt-title-rule { display: grid; grid-template-columns: 1fr auto 1fr; gap: 10px; align-items: center; width: min(100%,240px); margin: 13px auto 0; color: #c59a5c; }
.rt-title-rule i { display: block; height: 5px; border-top: 1px solid rgba(201,160,96,.7); border-bottom: 1px solid rgba(117,55,68,.85); }
.rt-synopsis { position: relative; z-index: 3; margin: 0 0 18px; padding: 13px 16px; color: #cbb9aa; text-align: center; font-size: 12px; line-height: 1.9; letter-spacing: .05em; }
'''

    # Avatar-switch selection logic uses :has() rather than id/for or bare
    # sibling radios. Why: this message's HTML repeats verbatim in every
    # turn, so id="rtf-m" (and any radio `name`) is NOT unique across a long
    # chat - `label[for]` binds to the first same-id element in the WHOLE
    # document, so clicking an avatar on message #12 could silently toggle
    # message #1's hidden radio instead. Wrapping the radio inside its
    # <label> sidesteps that (no id needed for the click to register at
    # all), and :has() lets the surrounding stylesheet still reach outside
    # the label to show/hide the matching wheel-section - :has() has been
    # baseline-supported (Safari/Chrome/Firefox) for years at this point,
    # so it's a safe bet. `name` is still seeded with the M/T/L digits below
    # as a cheap (not perfect) reduction of cross-message radio-group
    # crosstalk, since `name` grouping is also page-global.
    switch_css = '''
.rt-focus-radio { position: absolute; width: 0; height: 0; opacity: 0; }
.rt-fm { display: none; }
.rt-focus-switch { display: flex; justify-content: center; gap: 34px; margin: 22px 0 6px; }
.rt-av { cursor: pointer; display: block; text-align: center; opacity: .55; }
.rt-av:hover { opacity: .85; }
.rt-av span { display: block; width: 56px; height: 56px; margin: 0 auto 6px; border-radius: 50%; overflow: hidden; border: 1px solid rgba(201,156,95,.5); }
.rt-av img { width: 100%; height: 100%; object-fit: cover; display: block; }
.rt-av small { display: block; color: #cbb9aa; font-size: 10px; letter-spacing: .1em; }

.rt-wheel-section { display: none; }
''' + bd_hide_selector + ''' { display: none; }
.rt-fm-m:not(:empty) ~ .rt-wheel-section.char-m,
.rt-fm-t:not(:empty) ~ .rt-wheel-section.char-t,
.rt-fm-l:not(:empty) ~ .rt-wheel-section.char-l { display: block; }
.rt-focus-switch:has(.rt-focus-radio:checked) ~ .rt-wheel-section.char-m,
.rt-focus-switch:has(.rt-focus-radio:checked) ~ .rt-wheel-section.char-t,
.rt-focus-switch:has(.rt-focus-radio:checked) ~ .rt-wheel-section.char-l { display: none; }
.rt-focus-switch:has(.av-m input:checked) ~ .rt-wheel-section.char-m,
.rt-focus-switch:has(.av-t input:checked) ~ .rt-wheel-section.char-t,
.rt-focus-switch:has(.av-l input:checked) ~ .rt-wheel-section.char-l { display: block; }

.rt-fm-m:not(:empty) ~ .rt-focus-switch .av-m,
.rt-fm-t:not(:empty) ~ .rt-focus-switch .av-t,
.rt-fm-l:not(:empty) ~ .rt-focus-switch .av-l { opacity: 1; }
.rt-fm-m:not(:empty) ~ .rt-focus-switch .av-m span,
.rt-fm-t:not(:empty) ~ .rt-focus-switch .av-t span,
.rt-fm-l:not(:empty) ~ .rt-focus-switch .av-l span { box-shadow: 0 0 0 2px #c99c5f, 0 0 14px rgba(201,156,95,.6); }
.rt-focus-switch:has(.av-m input:checked) .av-m,
.rt-focus-switch:has(.av-t input:checked) .av-t,
.rt-focus-switch:has(.av-l input:checked) .av-l { opacity: 1; }
.rt-focus-switch:has(.av-m input:checked) .av-m span,
.rt-focus-switch:has(.av-t input:checked) .av-t span,
.rt-focus-switch:has(.av-l input:checked) .av-l span { box-shadow: 0 0 0 2px #c99c5f, 0 0 14px rgba(201,156,95,.6); }

.rt-wear-row.stat-m, .rt-wear-row.stat-t, .rt-wear-row.stat-l { display: none; }
.rt-fm-m:not(:empty) ~ .rt-footer .rt-wear-row.stat-m,
.rt-fm-t:not(:empty) ~ .rt-footer .rt-wear-row.stat-t,
.rt-fm-l:not(:empty) ~ .rt-footer .rt-wear-row.stat-l { display: grid; }
.rt-focus-switch:has(.rt-focus-radio:checked) ~ .rt-footer .rt-wear-row.stat-m,
.rt-focus-switch:has(.rt-focus-radio:checked) ~ .rt-footer .rt-wear-row.stat-t,
.rt-focus-switch:has(.rt-focus-radio:checked) ~ .rt-footer .rt-wear-row.stat-l { display: none; }
.rt-focus-switch:has(.av-m input:checked) ~ .rt-footer .rt-wear-row.stat-m,
.rt-focus-switch:has(.av-t input:checked) ~ .rt-footer .rt-wear-row.stat-t,
.rt-focus-switch:has(.av-l input:checked) ~ .rt-footer .rt-wear-row.stat-l { display: grid; }

.rt-pose-row.stat-m, .rt-pose-row.stat-t, .rt-pose-row.stat-l { display: none; }
.rt-fm-m:not(:empty) ~ .rt-footer .rt-pose-row.stat-m,
.rt-fm-t:not(:empty) ~ .rt-footer .rt-pose-row.stat-t,
.rt-fm-l:not(:empty) ~ .rt-footer .rt-pose-row.stat-l { display: grid; }
.rt-focus-switch:has(.rt-focus-radio:checked) ~ .rt-footer .rt-pose-row.stat-m,
.rt-focus-switch:has(.rt-focus-radio:checked) ~ .rt-footer .rt-pose-row.stat-t,
.rt-focus-switch:has(.rt-focus-radio:checked) ~ .rt-footer .rt-pose-row.stat-l { display: none; }
.rt-focus-switch:has(.av-m input:checked) ~ .rt-footer .rt-pose-row.stat-m,
.rt-focus-switch:has(.av-t input:checked) ~ .rt-footer .rt-pose-row.stat-t,
.rt-focus-switch:has(.av-l input:checked) ~ .rt-footer .rt-pose-row.stat-l { display: grid; }

.rt-fm-m:not(:empty) ~ .rt-footer .stat-m,
.rt-fm-t:not(:empty) ~ .rt-footer .stat-t,
.rt-fm-l:not(:empty) ~ .rt-footer .stat-l,
.rt-focus-switch:has(.av-m input:checked) ~ .rt-footer .stat-m,
.rt-focus-switch:has(.av-t input:checked) ~ .rt-footer .stat-t,
.rt-focus-switch:has(.av-l input:checked) ~ .rt-footer .stat-l {
  margin: -8px -14px;
  padding: 8px 14px;
  border-radius: 6px;
  background: linear-gradient(90deg, transparent, rgba(201,156,95,.34) 50%, transparent);
}

.rt-footer-details summary { list-style: none; cursor: pointer; position: relative; }
.rt-footer-details summary::-webkit-details-marker { display: none; }
.rt-footer-details summary::after { content: "▾"; position: absolute; right: 0; top: 0; color: #c99c5f; transition: transform .2s ease; }
.rt-footer-details:not([open]) summary::after { transform: rotate(-90deg); }

.rt-seal { position: absolute; inset: 0; display: none; }
.rt-seal img { width: 100%; height: 100%; object-fit: cover; display: block; }
.rt-fm-m:not(:empty) ~ .rt-footer .rt-seal-m,
.rt-fm-t:not(:empty) ~ .rt-footer .rt-seal-t,
.rt-fm-l:not(:empty) ~ .rt-footer .rt-seal-l { display: block; }
'''

    # base chrome for the 6 clickable phase-position labels on each wheel
    # (shared across all 3 characters - the per-position placement is inline,
    # this just supplies the pill look + hides the native radio dot).
    phase_css = '''
.rt-phase-radio { position: absolute; width: 0; height: 0; opacity: 0; }
.rt-phase {
  position: absolute; z-index: 8; display: block; text-align: center;
  width: 74px; min-height: 30px; padding: 6px 5px; border-radius: 40%;
  background: radial-gradient(ellipse at center, rgba(20,12,20,.95) 0%, rgba(20,12,20,.82) 55%, rgba(20,12,20,0) 100%);
  color: #ae9887; font: 500 10.5px/1.3 "Noto Serif TC", serif; letter-spacing: .1em; cursor: pointer;
  transition: color 180ms ease, text-shadow 180ms ease, transform 180ms ease;
}
.rt-phase:hover { color: #f0d6ad; }
'''

    full_css = "<style>\n" + shell_css + "\n" + wheel_css_all + "\n" + phase_css + "\n" + switch_css + "\n</style>\n"

    CORNER_SVG = (
        '<span class="rt-frame-corner {POS}" aria-hidden="true"><svg viewBox="0 0 100 100">'
        '<path d="M3 48C6 19 19 6 48 3M3 67C13 31 31 13 67 3M7 87c8-30 26-48 56-56M16 16c17 0 24 7 24 24C23 40 16 33 16 16Zm27 27c17-2 27 6 29 23-17 2-27-6-29-23ZM9 52c12 1 19 8 20 20-12-1-19-8-20-20Z" fill="none" stroke="currentColor" stroke-width="1"/>'
        '<circle cx="16" cy="16" r="3" fill="none" stroke="currentColor"/></svg></span>'
    )
    frame_corners = "".join(CORNER_SVG.replace("{POS}", p) for p in ("nw", "ne", "sw", "se"))
    SHELL_CORNER_SVG = CORNER_SVG.replace("rt-frame-corner", "rt-shell-corner")
    shell_corners = "".join(SHELL_CORNER_SVG.replace("{POS}", p) for p in ("nw", "ne", "sw", "se"))

    # ---- RT_頭卡 ----
    # FOCUS no longer has to name one of the three characters literally -
    # "今日焦點・群戲" (group scene, per <Focus_Engine>) is valid and common,
    # and an earlier version of this regex required a name match here,
    # silently failing (and taking the whole shared <style> block down with
    # it, since it's only emitted here) on every group-scene turn. Default
    # avatar-switch selection is now driven by the [WHEEL] block's LABEL
    # instead (see wheel_foot_find below), which always names one specific
    # character's phase regardless of how FOCUS is worded.
    # FOCUS's value always carries the literal "今日焦點・" prefix verbatim
    # (system_prompt.md's <Output_Format> spec: "FOCUS: 今日焦點・（本輪主導角色）"),
    # so that prefix belongs in the fixed part of the pattern, not inside the
    # capture group - otherwise every place that reuses $1 (the headcard's
    # own "今日焦點・$1" line, and the new kicker below) ends up showing the
    # prefix twice.
    head_find = (
        r"\[HEAD\]\r?\nFOCUS:\s*今日焦點・(.*?)\r?\n"
        r"CHAPTER:\s*(.*?)\r?\nTIME:\s*(.*?)\r?\nLOC:\s*(.*?)\r?\nWEATHER:\s*(.*?)\r?\nLEAD:\s*(.*?)\r?\n"
        r"(?:TITLE:\s*(.*?)\r?\nSUBTITLE:\s*(.*?)\r?\nSYNOPSIS:\s*(.*?)\r?\n)?"
        r"\[\/HEAD\]"
    )
    # groups: 1=FOCUS (just the name/群戲 part, "今日焦點・" is now literal)
    #         2=CHAPTER 3=TIME 4=LOC 5=WEATHER 6=LEAD
    #         7=TITLE 8=SUBTITLE 9=SYNOPSIS (optional, all-or-nothing - only
    #         the 5 fixed openings carry these; ordinary AI-generated turns
    #         never emit them, which is exactly the signal .rt-title-flag
    #         uses to pick a frame mode)
    head_replace = (
        f'{full_css}'
        '<div class="rt-scope">'
        '<i class="rt-title-flag" style="display:none">$7</i>'
        '<div class="rt-shell">'
        f'{shell_corners}'
        '<div class="rt-header"><div class="rt-kicker">$2 · $1</div><h1>$7</h1><div class="rt-subtitle">$8</div><div class="rt-title-rule"><i></i><span>❦</span><i></i></div></div>'
        '<p class="rt-synopsis">$9</p>'
        '<div class="rt-frame rt-frame-head" style="width:min(100%,420px);margin:14px auto 18px;padding:16px 21px 17px;">'
        f'{frame_corners}'
        '<div style="display:grid;grid-template-columns:1fr auto;align-items:baseline;gap:12px;padding-bottom:12px;border-bottom:1px solid rgba(189,145,89,.22);">'
        '<div style="min-width:0;overflow:hidden;color:#f0ddc3;font-size:15px;font-weight:600;letter-spacing:.16em;text-overflow:ellipsis;white-space:nowrap;">今日焦點・$1</div>'
        '<div style="color:#d4b07b;font:italic 600 13px/1 \'Cormorant Garamond\',serif;letter-spacing:.08em;white-space:nowrap;">$2</div></div>'
        '<div style="display:grid;grid-template-columns:1fr 1.3fr 1fr;gap:10px 20px;padding:13px 0 12px;border-bottom:1px solid rgba(189,145,89,.22);">'
        '<div style="min-width:0;"><div style="margin-bottom:5px;color:#a99287;font-size:9px;letter-spacing:.18em;text-transform:uppercase;">時間</div><div style="position:relative;padding-left:11px;overflow:hidden;color:#dec29d;font-size:12px;letter-spacing:.06em;text-overflow:ellipsis;white-space:nowrap;"><span style="position:absolute;left:0;top:1px;color:#99754d;font-size:7px;">◆</span>$3</div></div>'
        '<div style="min-width:0;"><div style="margin-bottom:5px;color:#a99287;font-size:9px;letter-spacing:.18em;text-transform:uppercase;">地點</div><div style="position:relative;padding-left:11px;overflow:hidden;color:#dec29d;font-size:12px;letter-spacing:.06em;text-overflow:ellipsis;white-space:nowrap;"><span style="position:absolute;left:0;top:1px;color:#99754d;font-size:7px;">◆</span>$4</div></div>'
        '<div style="min-width:0;"><div style="margin-bottom:5px;color:#a99287;font-size:9px;letter-spacing:.18em;text-transform:uppercase;">氣候</div><div style="position:relative;padding-left:11px;overflow:hidden;color:#dec29d;font-size:12px;letter-spacing:.06em;text-overflow:ellipsis;white-space:nowrap;"><span style="position:absolute;left:0;top:1px;color:#99754d;font-size:7px;">◆</span>$5</div></div></div>'
        '<div style="display:grid;grid-template-columns:auto 1fr;gap:9px;padding-top:12px;color:#bfaea1;font-size:11px;line-height:1.75;letter-spacing:.06em;"><span style="color:#c99c5f;font-size:9px;line-height:1.9;">❖</span><span>$6</span></div></div>'
    )

    # who-is-focus markers now come from [WHEEL]'s LABEL (18 words, unique
    # per character - see head_find above for why FOCUS itself isn't safe
    # to use for this).
    LABEL_WORDS = {ch: [label for _, label, _ in PHASE[ch]["bands"]] for ch in ("m", "t", "l")}
    label_alt = "(?:" + "|".join(f"({w})" for ch in ("m", "t", "l") for w in LABEL_WORDS[ch]) + ")"

    wheel_foot_find = (
        r"\[WHEEL\]\r?\nROT:\s*.*?\r?\nROMAN:\s*.*?\r?\nLABEL:\s*" + label_alt + r"\r?\nNOTE:\s*.*?\r?\n\[\/WHEEL\]\r?\n\r?\n"
        r"\[FOOT\]\r?\nSCENE:\s*(.*?)\r?\nACT:\s*(.*?)\r?\nCLOCK:\s*(.*?)\r?\n"
        rf"M:\s*{band_regex('m')}\r?\n"
        rf"T:\s*{band_regex('t')}\r?\n"
        rf"L:\s*{band_regex('l')}\r?\n"
        r"HEAT:\s*(.*?)\r?\nU_WEAR:\s*(.*?)\r?\nM_WEAR:\s*(.*?)\r?\nT_WEAR:\s*(.*?)\r?\nL_WEAR:\s*(.*?)\r?\n"
        r"U_POSE:\s*(.*?)\r?\nM_POSE:\s*(.*?)\r?\nT_POSE:\s*(.*?)\r?\nL_POSE:\s*(.*?)\r?\n"
        r"VOICE:\s*(.*?)\r?\nMOOD:\s*(.*?)\r?\n\[\/FOOT\]"
    )
    # groups: 1-6 LABEL=m words, 7-12 LABEL=t words, 13-18 LABEL=l words
    #         19 SCENE 20 ACT 21 CLOCK
    #         22-27 M bands  28-33 T bands  34-39 L bands
    #         40 HEAT
    #         41 U_WEAR 42 M_WEAR 43 T_WEAR 44 L_WEAR
    #         45 U_POSE 46 M_POSE 47 T_POSE 48 L_POSE
    #         49 VOICE 50 MOOD
    MVAL = "$22$23$24$25$26$27"
    TVAL = "$28$29$30$31$32$33"
    LVAL = "$34$35$36$37$38$39"

    def marker_block(ch, group_start):
        return "".join(f'<i class="mk-{ch} mk-{ch}{i+1}" style="display:none">${group_start+i}</i>' for i in range(6))

    fm_m = "".join(f"${i}" for i in range(1, 7))
    fm_t = "".join(f"${i}" for i in range(7, 13))
    fm_l = "".join(f"${i}" for i in range(13, 19))
    focus_markers = (
        f'<i class="rt-fm rt-fm-m" style="display:none">{fm_m}</i>'
        f'<i class="rt-fm rt-fm-t" style="display:none">{fm_t}</i>'
        f'<i class="rt-fm rt-fm-l" style="display:none">{fm_l}</i>'
    )
    markers_all = focus_markers + marker_block("m", 22) + marker_block("t", 28) + marker_block("l", 34)

    RADIO_NAME = f"rt-focus-{MVAL}{TVAL}{LVAL}"  # see switch_css comment above
    avatar_switch = (
        '<div class="rt-focus-switch" aria-label="切換角色狀態">'
        f'<label class="rt-av av-m"><input type="radio" name="{RADIO_NAME}" class="rt-focus-radio"><span><img src="data:image/jpeg;base64,{AVATAR["m"]}" alt=""></span><small>馬提亞斯</small></label>'
        f'<label class="rt-av av-t"><input type="radio" name="{RADIO_NAME}" class="rt-focus-radio"><span><img src="data:image/jpeg;base64,{AVATAR["t"]}" alt=""></span><small>阿霆</small></label>'
        f'<label class="rt-av av-l"><input type="radio" name="{RADIO_NAME}" class="rt-focus-radio"><span><img src="data:image/jpeg;base64,{AVATAR["l"]}" alt=""></span><small>Lia</small></label>'
        '</div>'
    )

    wheels_html = (
        build_wheel_section("m", MVAL)
        + build_wheel_section("t", TVAL)
        + build_wheel_section("l", LVAL)
    )

    footer_html = f'''<footer class="rt-footer rt-frame rt-frame-foot" aria-label="角色狀態尾卡" style="width:min(100%,420px);margin:0 auto 14px;padding:17px 21px 18px;">
{frame_corners}
<details class="rt-footer-details" open>
<summary style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:15px;padding-bottom:13px;border-bottom:1px solid rgba(189,145,89,.22);color:#a99287;font-size:10px;letter-spacing:.13em;">
<span>$19</span><span style="color:#d4b07b;font:italic 600 15px/1 'Cormorant Garamond',serif;letter-spacing:.08em;">$20</span><span style="text-align:right;">$21</span>
</summary>
<div style="display:grid;grid-template-columns:1fr;gap:9px;padding:14px 0 13px;">
<div class="rt-status-line stat-m" style="display:grid;grid-template-columns:58px 1fr auto;align-items:center;gap:9px;min-width:0;"><span style="overflow:hidden;color:#bca79a;font-size:10px;letter-spacing:.14em;text-overflow:ellipsis;white-space:nowrap;">馬提亞斯</span><span style="position:relative;height:5px;border-top:1px solid #745160;border-bottom:1px solid rgba(197,154,91,.35);"><i style="position:absolute;top:-1px;left:0;height:2px;width:{MVAL}%;background:linear-gradient(90deg,#7e3f58,#d1a265,#f2d09e);box-shadow:0 0 7px rgba(209,162,101,.35);"></i></span><span style="color:#d7bb91;font:600 11px/1 'Cormorant Garamond',serif;">{MVAL}</span></div>
<div class="rt-status-line stat-t" style="display:grid;grid-template-columns:58px 1fr auto;align-items:center;gap:9px;min-width:0;"><span style="overflow:hidden;color:#bca79a;font-size:10px;letter-spacing:.14em;text-overflow:ellipsis;white-space:nowrap;">阿霆</span><span style="position:relative;height:5px;border-top:1px solid #745160;border-bottom:1px solid rgba(197,154,91,.35);"><i style="position:absolute;top:-1px;left:0;height:2px;width:{TVAL}%;background:linear-gradient(90deg,#7e3f58,#d1a265,#f2d09e);box-shadow:0 0 7px rgba(209,162,101,.35);"></i></span><span style="color:#d7bb91;font:600 11px/1 'Cormorant Garamond',serif;">{TVAL}</span></div>
<div class="rt-status-line stat-l" style="display:grid;grid-template-columns:58px 1fr auto;align-items:center;gap:9px;min-width:0;"><span style="overflow:hidden;color:#bca79a;font-size:10px;letter-spacing:.14em;text-overflow:ellipsis;white-space:nowrap;">Lia</span><span style="position:relative;height:5px;border-top:1px solid #745160;border-bottom:1px solid rgba(197,154,91,.35);"><i style="position:absolute;top:-1px;left:0;height:2px;width:{LVAL}%;background:linear-gradient(90deg,#7e3f58,#d1a265,#f2d09e);box-shadow:0 0 7px rgba(209,162,101,.35);"></i></span><span style="color:#d7bb91;font:600 11px/1 'Cormorant Garamond',serif;">{LVAL}</span></div>
<div style="display:grid;grid-template-columns:58px 1fr auto;align-items:center;gap:9px;min-width:0;"><span style="overflow:hidden;color:#bca79a;font-size:10px;letter-spacing:.14em;text-overflow:ellipsis;white-space:nowrap;">心動震盪</span><span style="position:relative;height:5px;border-top:1px solid #745160;border-bottom:1px solid rgba(197,154,91,.35);"><i style="position:absolute;top:-1px;left:0;height:2px;width:$40%;background:linear-gradient(90deg,#7e3f58,#d1a265,#f2d09e);box-shadow:0 0 7px rgba(209,162,101,.35);"></i></span><span style="color:#d7bb91;font:600 11px/1 'Cormorant Garamond',serif;">$40</span></div>
</div>
<div style="display:grid;grid-template-columns:1fr;gap:9px;padding:13px 0 12px;border-top:1px solid rgba(189,145,89,.22);">
<div class="rt-wear-row you" style="display:grid;grid-template-columns:52px 1fr;align-items:baseline;gap:9px;min-width:0;"><span style="color:#e4c9a4;font-size:9px;letter-spacing:.14em;white-space:nowrap;">你</span><span style="position:relative;padding-left:10px;color:#e4c9a4;font-size:10.5px;letter-spacing:.04em;line-height:1.5;"><span style="position:absolute;left:0;top:0;color:#c99c5f;font-size:7px;">◇</span>$41</span></div>
<div class="rt-wear-row stat-m" style="grid-template-columns:52px 1fr;align-items:baseline;gap:9px;min-width:0;"><span style="color:#a99287;font-size:9px;letter-spacing:.14em;white-space:nowrap;">馬提亞斯</span><span style="position:relative;padding-left:10px;color:#cbb9aa;font-size:10.5px;letter-spacing:.04em;line-height:1.5;"><span style="position:absolute;left:0;top:0;color:#8a6a45;font-size:7px;">◇</span>$42</span></div>
<div class="rt-wear-row stat-t" style="grid-template-columns:52px 1fr;align-items:baseline;gap:9px;min-width:0;"><span style="color:#a99287;font-size:9px;letter-spacing:.14em;white-space:nowrap;">阿霆</span><span style="position:relative;padding-left:10px;color:#cbb9aa;font-size:10.5px;letter-spacing:.04em;line-height:1.5;"><span style="position:absolute;left:0;top:0;color:#8a6a45;font-size:7px;">◇</span>$43</span></div>
<div class="rt-wear-row stat-l" style="grid-template-columns:52px 1fr;align-items:baseline;gap:9px;min-width:0;"><span style="color:#a99287;font-size:9px;letter-spacing:.14em;white-space:nowrap;">Lia</span><span style="position:relative;padding-left:10px;color:#cbb9aa;font-size:10.5px;letter-spacing:.04em;line-height:1.5;"><span style="position:absolute;left:0;top:0;color:#8a6a45;font-size:7px;">◇</span>$44</span></div>
</div>
<div style="display:grid;grid-template-columns:1fr;gap:9px;padding:13px 0 12px;border-top:1px solid rgba(189,145,89,.22);">
<div class="rt-pose-row you" style="display:grid;grid-template-columns:52px 1fr;align-items:baseline;gap:9px;min-width:0;"><span style="color:#e4c9a4;font-size:9px;letter-spacing:.14em;white-space:nowrap;">你</span><span style="position:relative;padding-left:10px;color:#e4c9a4;font-size:10.5px;letter-spacing:.04em;line-height:1.5;"><span style="position:absolute;left:0;top:0;color:#c99c5f;font-size:7px;">✦</span>$45</span></div>
<div class="rt-pose-row stat-m" style="grid-template-columns:52px 1fr;align-items:baseline;gap:9px;min-width:0;"><span style="color:#a99287;font-size:9px;letter-spacing:.14em;white-space:nowrap;">馬提亞斯</span><span style="position:relative;padding-left:10px;color:#cbb9aa;font-size:10.5px;letter-spacing:.04em;line-height:1.5;"><span style="position:absolute;left:0;top:0;color:#8a6a45;font-size:7px;">✦</span>$46</span></div>
<div class="rt-pose-row stat-t" style="grid-template-columns:52px 1fr;align-items:baseline;gap:9px;min-width:0;"><span style="color:#a99287;font-size:9px;letter-spacing:.14em;white-space:nowrap;">阿霆</span><span style="position:relative;padding-left:10px;color:#cbb9aa;font-size:10.5px;letter-spacing:.04em;line-height:1.5;"><span style="position:absolute;left:0;top:0;color:#8a6a45;font-size:7px;">✦</span>$47</span></div>
<div class="rt-pose-row stat-l" style="grid-template-columns:52px 1fr;align-items:baseline;gap:9px;min-width:0;"><span style="color:#a99287;font-size:9px;letter-spacing:.14em;white-space:nowrap;">Lia</span><span style="position:relative;padding-left:10px;color:#cbb9aa;font-size:10.5px;letter-spacing:.04em;line-height:1.5;"><span style="position:absolute;left:0;top:0;color:#8a6a45;font-size:7px;">✦</span>$48</span></div>
</div>
<div style="display:grid;grid-template-columns:auto 1fr;align-items:start;gap:15px;padding-top:12px;border-top:1px solid rgba(189,145,89,.22);"><span style="position:relative;display:block;width:31px;height:31px;border-radius:50%;overflow:hidden;border:1px solid #8d584d;box-shadow:inset 0 0 0 3px #27151e;background:#3c1c2a;"><span class="rt-seal rt-seal-m"><img src="data:image/jpeg;base64,{AVATAR["m"]}" alt=""></span><span class="rt-seal rt-seal-t"><img src="data:image/jpeg;base64,{AVATAR["t"]}" alt=""></span><span class="rt-seal rt-seal-l"><img src="data:image/jpeg;base64,{AVATAR["l"]}" alt=""></span></span><div style="min-width:0;"><div style="color:#bfaea1;font-size:11px;line-height:1.7;letter-spacing:.06em;"><b style="color:#dec29d;font-weight:500;">心事：</b>$49</div><div style="margin-top:6px;text-align:right;color:#d4b07b;font-size:11px;font-weight:500;letter-spacing:.08em;">$50</div></div></div>
</details>
</footer>'''

    # the first trailing "</div>" closes .rt-shell (opened at the very start
    # of head_replace, wrapping everything from the title header through the
    # footer so its border/background can span all of it in title mode); the
    # second closes .rt-scope.
    wheel_foot_replace = markers_all + avatar_switch + wheels_html + footer_html + "</div></div>"

    scripts = [
        {
            "id": "rt-head-001",
            "scriptName": "RT_頭卡",
            "findRegex": head_find,
            "replaceString": head_replace,
            "trimStrings": [], "placement": [2], "disabled": False,
            "markdownOnly": True, "promptOnly": False, "runOnEdit": True,
            "substituteRegex": 0, "minDepth": None, "maxDepth": None,
        },
        {
            "id": "rt-body-002",
            "scriptName": "RT_正文",
            "findRegex": r"\[BODY\]\r?\n([\s\S]*?)\r?\n\[\/BODY\]",
            "replaceString": "<div style=\"font-family:'Noto Serif TC','Songti TC',serif;width:min(100%,420px);margin:0 auto 22px;padding:4px 4px 0;color:#dcccbe;font-size:13.5px;line-height:2.15;letter-spacing:.045em;text-align:justify;white-space:pre-wrap;\">$1</div><div style=\"width:min(100%,220px);margin:20px auto 22px;text-align:center;color:#9d7447;font-size:11px;\">❖</div>",
            "trimStrings": [], "placement": [2], "disabled": False,
            "markdownOnly": True, "promptOnly": False, "runOnEdit": True,
            "substituteRegex": 0, "minDepth": None, "maxDepth": None,
        },
        {
            "id": "rt-wheelfoot-003",
            "scriptName": "RT_花冠尾卡",
            "findRegex": wheel_foot_find,
            "replaceString": wheel_foot_replace,
            "trimStrings": [], "placement": [2], "disabled": False,
            "markdownOnly": True, "promptOnly": False, "runOnEdit": True,
            "substituteRegex": 0, "minDepth": None, "maxDepth": None,
        },
    ]

    out_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "scripts_wheel_footer.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(scripts, f, ensure_ascii=False, indent=2)
    print("wrote", out_path)

if __name__ == "__main__":
    main()
