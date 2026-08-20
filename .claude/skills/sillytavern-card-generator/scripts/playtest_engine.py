#!/usr/bin/env python3
"""Playtest engine for SillyTavern character cards.

This script does the parts of a playtest simulation that should be
*computed*, not imagined: which world-book entries would actually fire
given the running conversation, how the card's regex_scripts would
actually render a raw model turn into HTML, and how a JSON Patch
variable-update block actually mutates the tracked state. Writing the
player's line and the character's in-character response is left to
whoever is driving this (an LLM reasoning in-context) — this script
only keeps that generation honest to what the assembled card would
really inject and really render.

Two subcommands, meant to be called once per simulated round, in order:

  context   Before writing this round's character turn: prints which
            world-book entries are currently active given the transcript
            so far, plus the current tracked variable state. Write the
            character's turn using ONLY this injected context plus the
            card's constant system_prompt — not the full lorebook.

  commit    After writing a round (player turn + character turn): applies
            the JSON-Patch variable update found in the character's raw
            output, strips hidden HTML-comment blocks, runs the card's
            regex_scripts to render the final HTML, appends the round to
            a persistent transcript log, and re-renders a standalone HTML
            transcript file.

State persists across calls in --state (world-book trigger bookkeeping +
tracked variables) and --transcript (the full round-by-round record), so
run this repeatedly from round 1 upward.

Example:
  python3 playtest_engine.py context --card card.json --state state.json \\
      --transcript transcript.json --round 3

  # ... write player_turn.txt and char_turn.txt using that context ...

  python3 playtest_engine.py commit --card card.json --state state.json \\
      --transcript transcript.json --round 3 \\
      --player-file player_turn.txt --char-file char_turn.txt \\
      --html transcript.html
"""
import argparse
import html
import json
import re
import sys
from pathlib import Path

PATCH_BLOCK_RE = re.compile(
    r"<!--\s*<VariableUpdateLog>.*?<JSONPatch>(.*?)</JSONPatch>.*?</VariableUpdateLog>\s*-->",
    re.DOTALL,
)
COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


# --------------------------------------------------------------------------
# Card loading
# --------------------------------------------------------------------------

def load_card(card_path):
    card = json.loads(Path(card_path).read_text(encoding="utf-8"))
    data = card.get("data", card)
    entries = (
        (data.get("character_book") or {}).get("entries")
        or (card.get("character_book") or {}).get("entries")
        or []
    )
    regex_scripts = (
        (data.get("extensions") or {}).get("regex_scripts")
        or (card.get("extensions") or {}).get("regex_scripts")
        or []
    )
    return data, entries, regex_scripts


def load_json(path, default):
    p = Path(path)
    if p.exists() and p.stat().st_size > 0:
        return json.loads(p.read_text(encoding="utf-8"))
    return default


def save_json(path, obj):
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


# --------------------------------------------------------------------------
# World-book activation (approximation of SillyTavern's keyword scan)
# --------------------------------------------------------------------------

def entry_matches(entry, text_lower):
    keys = entry.get("keys") or entry.get("key") or []
    return any(k and k.lower() in text_lower for k in keys)


def secondary_ok(entry, text_lower):
    if not entry.get("selective"):
        return True
    sec = entry.get("secondary_keys") or entry.get("keysecondary") or []
    if not sec:
        return True
    ext = entry.get("extensions", {}) or {}
    logic = ext.get("selectiveLogic", 0)
    hits = [bool(k and k.lower() in text_lower) for k in sec]
    # Exact numeric<->logic mapping varies slightly by SillyTavern version;
    # this is a reasonable approximation for playtest purposes, not a
    # byte-perfect emulation. AND_ANY is the common default (0).
    if logic == 3:       # AND_ALL
        return all(hits)
    if logic == 2:        # NOT_ANY
        return not any(hits)
    if logic == 1:        # NOT_ALL
        return not all(hits)
    return any(hits)       # AND_ANY (default / logic == 0)


def active_entries(entries, messages, round_num, trigger_state, default_scan_depth=4):
    """Returns the entries considered active this round. `messages` is the
    chronological list of every player/character turn so far (most recent
    last); each entry only scans its own trailing window of that list
    (extensions.scan_depth, falling back to default_scan_depth), mirroring
    SillyTavern's scan-depth-limited keyword search rather than matching
    against the entire chat history forever. Mutates trigger_state in place
    (per-entry last-triggered round) so sticky / cooldown / delay behave
    correctly across repeated calls."""
    active = []
    for e in entries:
        if not e.get("enabled", True):
            continue
        eid = str(e.get("id"))
        ext = e.get("extensions", {}) or {}
        last_round = trigger_state.get(eid, {}).get("last_round")
        sticky = ext.get("sticky", 0) or 0
        cooldown = ext.get("cooldown", 0) or 0
        delay = ext.get("delay", 0) or 0
        scan_depth = ext.get("scan_depth") or default_scan_depth

        if delay and round_num < delay:
            continue

        window = messages[-scan_depth:] if scan_depth else messages
        text_lower = "\n".join(window).lower()

        hit = True if e.get("constant") else (
            entry_matches(e, text_lower) and secondary_ok(e, text_lower)
        )

        if not hit and sticky and last_round is not None and (round_num - last_round) <= sticky:
            hit = True  # still within its sticky window

        if hit and not e.get("constant") and cooldown and last_round is not None \
                and (round_num - last_round) < cooldown:
            hit = False  # keyword matched again too soon after last trigger

        if hit:
            active.append(e)
            trigger_state[eid] = {"last_round": round_num}
    return active


# --------------------------------------------------------------------------
# Regex beautify (mirrors SillyTavern's Regex extension semantics)
# --------------------------------------------------------------------------

def parse_find_regex(raw):
    """Accepts either a bare pattern string or a JS-style /pattern/flags
    string (as commonly stored in regex_scripts[].findRegex)."""
    raw = raw.strip()
    if raw.startswith("/"):
        last_slash = raw.rfind("/")
        if last_slash > 0:
            pattern, flag_chars = raw[1:last_slash], raw[last_slash + 1:]
            flags = 0
            count = 0 if "g" in flag_chars else 1
            if "i" in flag_chars:
                flags |= re.IGNORECASE
            if "s" in flag_chars:
                flags |= re.DOTALL
            if "m" in flag_chars:
                flags |= re.MULTILINE
            return pattern, flags, count
    # Bare pattern: default to DOTALL (these patterns usually span the
    # whole tagged block) and replace only the first match, matching a
    # typical non-global JS regex.
    return raw, re.DOTALL, 1


def make_replacer(replace_string):
    def repl(m):
        out = replace_string.replace("{{match}}", m.group(0))

        def sub(gm):
            idx = int(gm.group(1))
            try:
                val = m.group(idx)
            except IndexError:
                return gm.group(0)
            return val if val is not None else ""

        return re.sub(r"\$(\d+)", sub, out)

    return repl


def apply_regex_scripts(text, regex_scripts):
    warnings = []
    for script in regex_scripts:
        if script.get("disabled"):
            continue
        find = script.get("findRegex", "")
        replace = script.get("replaceString", "")
        if not find:
            continue
        pattern, flags, count = parse_find_regex(find)
        try:
            compiled = re.compile(pattern, flags)
        except re.error as ex:
            warnings.append(f"regex '{script.get('scriptName')}' failed to compile: {ex}")
            continue
        text = compiled.sub(make_replacer(replace), text, count=count)
    return text, warnings


# --------------------------------------------------------------------------
# JSON Patch variable updates
# --------------------------------------------------------------------------

def apply_json_patch(vars_state, patch_ops):
    for op in patch_ops:
        path = op.get("path", "")
        segments = [s for s in path.split("/") if s]
        if not segments:
            continue
        target = vars_state
        for seg in segments[:-1]:
            target = target.setdefault(seg, {})
        target[segments[-1]] = op.get("value")
    return vars_state


def extract_and_apply_patch(raw_text, vars_state):
    m = PATCH_BLOCK_RE.search(raw_text)
    if not m:
        return vars_state, False, None
    try:
        ops = json.loads(m.group(1))
        apply_json_patch(vars_state, ops)
        return vars_state, True, None
    except json.JSONDecodeError as ex:
        return vars_state, False, f"could not parse JSON Patch block: {ex}"


# --------------------------------------------------------------------------
# HTML transcript rendering
# --------------------------------------------------------------------------

def render_html(transcript, out_path):
    rounds_html = []
    for r in transcript["rounds"]:
        player_html = html.escape(r.get("player_raw", "")).replace("\n", "<br>")
        rounds_html.append(f"""
        <div class="round" id="round-{r['round']}">
          <div class="round-label">第 {r['round']} 頁</div>
          <div class="bubble-player"><div class="role-tag">玩家</div>{player_html}</div>
          <div class="bubble-char">{r['char_html']}</div>
        </div>""")

    vars_rows = "".join(
        f"<tr><td>{r['round']}</td><td><code>{html.escape(json.dumps(r['vars_snapshot'], ensure_ascii=False))}</code></td></tr>"
        for r in transcript["rounds"]
    )

    warn_items = "".join(
        f"<li>第 {r['round']} 頁：{html.escape(w)}</li>"
        for r in transcript["rounds"] for w in r.get("warnings", [])
    )
    warn_block = f"<h2>渲染警告</h2><ul>{warn_items}</ul>" if warn_items else ""

    page = f"""<!doctype html>
<html lang="zh-TW"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{html.escape(transcript.get('card_name', ''))} 試玩模擬紀錄</title>
<style>
  body {{ font-family: -apple-system, "Noto Sans TC", "PingFang TC", sans-serif;
          max-width: 720px; margin: 0 auto; padding: 28px 16px 80px;
          background:#faf8f4; color:#2b2620; line-height:1.6; }}
  h1 {{ font-size: 18px; border-bottom: 1px solid #ddd3c4; padding-bottom: 10px; }}
  h2 {{ font-size: 14px; margin-top: 40px; color:#7a6a4a; }}
  .round {{ margin-bottom: 30px; padding-bottom: 22px; border-bottom: 1px dashed #ddd3c4; }}
  .round-label {{ font-size: 11px; color: #a08e6c; letter-spacing: .08em; margin-bottom: 8px; }}
  .bubble-player {{ background: #efe7d8; padding: 10px 14px; border-radius: 10px; margin-bottom: 12px; }}
  .role-tag {{ font-size: 10px; color: #8a7a5c; margin-bottom: 4px; letter-spacing:.06em; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 12px; margin-top: 10px; }}
  td, th {{ border: 1px solid #ddd3c4; padding: 6px 8px; text-align: left; vertical-align: top; }}
  code {{ font-size: 11px; word-break: break-all; }}
</style></head>
<body>
<h1>{html.escape(transcript.get('card_name', ''))} · 試玩模擬紀錄（共 {len(transcript['rounds'])} 頁）</h1>
{''.join(rounds_html)}
<h2>變量狀態追蹤</h2>
<table><tr><th>回合</th><th>狀態快照</th></tr>{vars_rows}</table>
{warn_block}
</body></html>"""
    Path(out_path).write_text(page, encoding="utf-8")


# --------------------------------------------------------------------------
# Subcommands
# --------------------------------------------------------------------------

def cmd_context(args):
    _, entries, _ = load_card(args.card)
    state = load_json(args.state, {"vars": {}, "triggers": {}})
    transcript = load_json(args.transcript, {"rounds": []})

    messages = []
    for r in transcript["rounds"]:
        messages.append(r.get("player_raw", ""))
        messages.append(r.get("char_raw", ""))

    active = active_entries(
        entries, messages, args.round, state.setdefault("triggers", {}),
        default_scan_depth=args.scan_depth,
    )
    save_json(args.state, state)

    print(json.dumps({
        "round": args.round,
        "current_vars": state.get("vars", {}),
        "active_world_entries": [
            {"comment": e.get("comment", ""), "content": e.get("content", "")}
            for e in active
        ],
    }, ensure_ascii=False, indent=2))


def cmd_commit(args):
    data, _entries, regex_scripts = load_card(args.card)
    state = load_json(args.state, {"vars": {}, "triggers": {}})
    transcript = load_json(args.transcript, {"rounds": [], "card_name": data.get("name", "")})

    player_raw = Path(args.player_file).read_text(encoding="utf-8") if args.player_file else ""
    char_raw = Path(args.char_file).read_text(encoding="utf-8")

    state["vars"], patch_found, patch_warning = extract_and_apply_patch(char_raw, state.get("vars", {}))
    visible_raw = COMMENT_RE.sub("", char_raw)
    char_html, warnings = apply_regex_scripts(visible_raw, regex_scripts)
    if patch_warning:
        warnings.append(patch_warning)

    transcript["rounds"].append({
        "round": args.round,
        "player_raw": player_raw,
        "char_raw": char_raw,
        "char_html": char_html,
        "vars_snapshot": json.loads(json.dumps(state.get("vars", {}))),
        "patch_found": patch_found,
        "warnings": warnings,
    })
    save_json(args.transcript, transcript)
    save_json(args.state, state)

    if args.html:
        render_html(transcript, args.html)

    print(json.dumps({
        "round": args.round,
        "patch_found": patch_found,
        "vars_after": state.get("vars", {}),
        "warnings": warnings,
    }, ensure_ascii=False, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_ctx = sub.add_parser("context", help="print active world-book entries + vars before writing a round")
    p_ctx.add_argument("--card", required=True)
    p_ctx.add_argument("--state", required=True)
    p_ctx.add_argument("--transcript", required=True)
    p_ctx.add_argument("--round", type=int, required=True)
    p_ctx.add_argument("--scan-depth", type=int, default=4,
                        help="default trailing-message window for non-constant entries without their own scan_depth (default: 4, i.e. ~last 2 rounds)")
    p_ctx.set_defaults(func=cmd_context)

    p_commit = sub.add_parser("commit", help="apply patch + regex, append round, re-render transcript")
    p_commit.add_argument("--card", required=True)
    p_commit.add_argument("--state", required=True)
    p_commit.add_argument("--transcript", required=True)
    p_commit.add_argument("--round", type=int, required=True)
    p_commit.add_argument("--player-file", required=False, default=None)
    p_commit.add_argument("--char-file", required=True)
    p_commit.add_argument("--html", required=False, default=None)
    p_commit.set_defaults(func=cmd_commit)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
