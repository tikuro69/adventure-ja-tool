import argparse
import json
import os
import re
import sys
from pathlib import Path

import pexpect


ANSI_RE = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
CTRL_RE = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")
SCORE_RE = re.compile(r"\bScore:\s*\d+\s+Moves:\s*\d+\b")


def load_glossary(path: str) -> dict:
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def clean_text(text: str) -> str:
    text = ANSI_RE.sub("", text)
    text = text.replace("\r", "")
    text = text.replace("\b", "")
    text = CTRL_RE.sub("", text)
    lines = [line.rstrip() for line in text.splitlines()]
    return "\n".join(lines).strip()


def compress_blank_lines(text: str) -> str:
    lines = text.splitlines()
    result = []
    blank = False

    for line in lines:
        if line.strip() == "":
            if not blank:
                result.append("")
            blank = True
        else:
            result.append(line)
            blank = False

    return "\n".join(result).strip()


def normalize_output(text: str, user_input: str | None = None) -> str:
    lines = text.splitlines()
    cleaned = []

    for line in lines:
        s = line.strip()

        if not s:
            cleaned.append("")
            continue

        # 入力したコマンドのエコーを消す
        if user_input and s == user_input.strip():
            continue

        # スコア表示行を消す
        if SCORE_RE.search(s):
            s = SCORE_RE.sub("", s).rstrip()
            if not s:
                continue
            cleaned.append(s)
            continue

        # dfrotz の案内を少し整理
        if s in {"Using normal formatting.", "Loading Advent.z5."}:
            cleaned.append(s)
            continue

        cleaned.append(line)

    return compress_blank_lines("\n".join(cleaned))


def translate_line(line: str, glossary: dict) -> str:
    if not line.strip():
        return ""

    templates = [
        (r"^That's not a verb I recognise\.$", "その動詞は認識できません。"),
        (r"^Taken\.$", "取った。"),
        (r"^You can't go in that direction\.$", "その方向には進めません。"),
        (r"^I don't understand that\.$", "その指示は理解できません。"),
        (r"^The bottle is now full of water\.$", "ボトルは水でいっぱいになった。"),
        (r"^That's hardly portable\.$", "それはとても持ち運べません。"),
        (r"^There are some keys on the ground here\.$", "ここには鍵（keys）が地面にある。"),
        (r"^There is tasty food here\.$", "ここには食料（food）がある。"),
        (r"^There is a shiny brass lamp nearby\.$", "ここには真鍮のランプ（lamp）が近くにある。"),
        (r"^There is an empty bottle here\.$", "ここには空のボトル（bottle）がある。"),
        (
            r"^You are inside a building, a well house for a large spring\.$",
            "あなたは建物の中にいる。大きな泉のための小屋のようだ。"
        ),
        (
            r"^You are standing at the end of a road before a small brick building\.$",
            "あなたは小さなレンガ造りの建物の前、道の行き止まりに立っている。"
        ),
        (r"^Around you is a forest\.$", "あたりは森に囲まれている。"),
        (r"^A small stream flows out of the building and down a gully\.$", "小さな流れが建物から流れ出て、溝へと下っている。"),
        (r"^At End Of Road$", "道の行き止まり"),
        (r"^Inside Building$", "建物の中"),
        (r"^set of keys: Taken\.$", "鍵束（set of keys）を取った。"),
        (r"^tasty food: Taken\.$", "食料（tasty food）を取った。"),
        (r"^brass lantern: Taken\.$", "真鍮のランタン（brass lantern）を取った。"),
        (r"^small bottle: Taken\.$", "小さなボトル（small bottle）を取った。"),
        (r"^stream: The bottle is now full of water\.$", "小川（stream）でボトルが水でいっぱいになった。"),
        (r"^well house: That's hardly portable\.$", "泉小屋（well house）はとても持ち運べない。"),
        (r"^spring: That's hardly portable\.$", "泉（spring）はとても持ち運べない。"),
        (r"^pair of 1 foot diameter sewer pipes: That's hardly portable\.$", "直径1フィートの下水管の一対はとても持ち運べない。"),

    ]

    for pattern, ja in templates:
        if re.match(pattern, line):
            return ja

    result = line

    # 長いキー順で単語置換
    for en in sorted(glossary.keys(), key=len, reverse=True):
        ja = glossary[en]
        result = re.sub(rf"\b{re.escape(en)}\b", f"{ja}（{en}）", result)

    # 最低限の頻出語句
    replacements = [
        ("There is ", "ここには"),
        ("There are ", "ここには"),
        ("You are ", "あなたは"),
        (" on the ground here.", "が地面にある。"),
        (" here.", "がある。"),
        (" nearby.", "が近くにある。"),
        (" is now full of water.", "は水でいっぱいになった。"),
    ]
    for en, ja in replacements:
        result = result.replace(en, ja)

    return result


def translate_block(text: str, glossary: dict) -> str:
    lines = text.splitlines()
    translated = [translate_line(line, glossary) for line in lines]
    return compress_blank_lines("\n".join(translated))


def print_block(title: str, text: str) -> None:
    if not text.strip():
        return
    print(f"\n[{title}]")
    print(text)


def read_until_prompt(child: pexpect.spawn, prompt=">") -> str:
    chunks = []

    while True:
        index = child.expect_exact([prompt, "***MORE***", pexpect.EOF, pexpect.TIMEOUT])

        if index == 0:
            chunks.append(child.before)
            break

        elif index == 1:
            chunks.append(child.before)
            child.send(" ")

        elif index == 2:
            chunks.append(child.before)
            break

        elif index == 3:
            chunks.append(child.before)
            joined = "".join(chunks).strip()
            if joined:
                break
            continue

    text = "".join(chunks)
    return clean_text(text)


def split_opening_and_scene(text: str) -> tuple[str, str]:
    lines = text.splitlines()

    scene_markers = {"At End Of Road", "Inside Building", "In Valley", "Forest", "Slit In Streambed"}
    scene_index = None

    for i, line in enumerate(lines):
        if line.strip() in scene_markers:
            scene_index = i
            break

    if scene_index is None:
        return text, ""

    opening = "\n".join(lines[:scene_index]).strip()
    scene = "\n".join(lines[scene_index:]).strip()
    return opening, scene


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--story", default="Advent.z5", help="Path to story file")
    parser.add_argument("--interpreter", default="dfrotz", help="Interpreter command")
    parser.add_argument("--glossary", default="glossary.json", help="Glossary JSON path")
    parser.add_argument("--timeout", type=int, default=5, help="Expect timeout seconds")
    args = parser.parse_args()

    story_path = Path(args.story)
    if not story_path.exists():
        print(f"Story file not found: {story_path}", file=sys.stderr)
        return 1

    glossary = load_glossary(args.glossary)
    cmd = f'{args.interpreter} "{story_path}"'
    print(f"Starting: {cmd}")

    try:
        child = pexpect.spawn(
            cmd,
            encoding="utf-8",
            timeout=args.timeout,
            dimensions=(40, 100),
        )
    except Exception as e:
        print(f"Failed to start interpreter: {e}", file=sys.stderr)
        return 1

    try:
        opening_raw = read_until_prompt(child)
        opening_raw = normalize_output(opening_raw)

        sys_text, scene_text = split_opening_and_scene(opening_raw)

        if sys_text:
            print_block("SYS", sys_text)
        if scene_text:
            print_block("EN", scene_text)
            print_block("JA", translate_block(scene_text, glossary))

        while True:
            try:
                user_input = input("\n> ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nExiting.")
                break

            if not user_input:
                continue

            if user_input.lower() in {"quit", ":quit", ":exit", "exit"}:
                child.sendline("quit")
                break

            child.sendline(user_input)
            reply_raw = read_until_prompt(child)
            reply_raw = normalize_output(reply_raw, user_input=user_input)

            print_block("EN", reply_raw)
            print_block("JA", translate_block(reply_raw, glossary))

    finally:
        if child.isalive():
            child.close(force=True)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())