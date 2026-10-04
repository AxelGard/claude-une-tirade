#!/usr/bin/env python3
"""une-tirade: read Claude Code's replies out loud, without the code.

Used as a Claude Code hook:
  Stop              -> speak the text Claude wrote this turn
  UserPromptSubmit  -> stop speaking (you started typing a new prompt)

Also usable by hand:
  speak.py --toggle   mute / unmute
  speak.py --stop     stop current speech
  speak.py --test     speak a test sentence
  speak.py --filter   read markdown on stdin, print what would be spoken
"""
import json
import os
import re
import shutil
import signal
import subprocess
import sys

HOME_DIR = os.path.join(os.path.expanduser("~"), ".claude", "une-tirade")
CONFIG_FILE = os.path.join(HOME_DIR, "config.json")
MUTE_FILE = os.path.join(HOME_DIR, "muted")
PID_FILE = os.path.join(HOME_DIR, "speech.pid")

DEFAULT_CONFIG = {
    "voice": "",            # e.g. "Samantha" (macOS: `say -v ?` lists voices)
    "rate": 0,              # words per minute, 0 = system default
    "max_chars": 1500,      # cut long replies off after this many characters
    "code_placeholder": "", # spoken in place of a code block, e.g. "code block"
}


def load_config():
    config = dict(DEFAULT_CONFIG)
    try:
        with open(CONFIG_FILE) as f:
            config.update(json.load(f))
    except (OSError, ValueError):
        pass
    return config


# --------------------------------------------------------------------------
# Turning markdown into something worth hearing
# --------------------------------------------------------------------------

def _inline_code(match):
    code = match.group(1)
    # Short identifiers/words read fine ("the `install` script"); paths,
    # commands and expressions don't.
    if len(code) <= 25 and re.fullmatch(r"[\w.\- ]+", code) and "/" not in code:
        return code
    return ""


def clean_for_speech(text, code_placeholder=""):
    placeholder = f" {code_placeholder}. " if code_placeholder else " "
    # Fenced code blocks (``` or ~~~), including unterminated ones at the end.
    text = re.sub(r"(```|~~~).*?(\1|\Z)", placeholder, text, flags=re.S)
    # Indented code blocks (4+ spaces or tab after a blank line).
    text = re.sub(r"(?m)(^\n)((?: {4,}|\t).*\n?)+", r"\1", text)
    # Tables: drop every line that looks like a table row.
    text = re.sub(r"(?m)^\s*\|.*\|\s*$\n?", "", text)
    # Inline code.
    text = re.sub(r"`([^`\n]+)`", _inline_code, text)
    # Images, then links -> keep the link text only.
    text = re.sub(r"!\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", text)
    # Bare URLs and file paths like src/foo/bar.py:12 or ~/.claude/x.
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"(?<!\w)[~.]?/?(?:[\w.\-]+/)+[\w.\-]+(?::\d+)?", "", text)
    # Headings, blockquotes, list bullets, horizontal rules.
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)
    text = re.sub(r"(?m)^\s*>\s?", "", text)
    text = re.sub(r"(?m)^\s*(?:[-*+]|\d+[.)])\s+", "", text)
    text = re.sub(r"(?m)^\s*([-*_])\s*(?:\1\s*){2,}$", "", text)
    # Emphasis / strikethrough markers.
    text = re.sub(r"(\*\*|__|\*|_|~~)(?=\S)(.+?)(?<=\S)\1", r"\2", text)
    # HTML-ish tags.
    text = re.sub(r"<[^>\n]+>", "", text)
    # Arrows and stray symbols that TTS reads literally.
    text = text.replace("→", ", ").replace("->", ", ").replace("=>", ", ")
    text = re.sub(r"[*#`|]", "", text)
    # Collapse whitespace; end each line as a sentence so speech pauses.
    lines = [ln.strip() for ln in text.splitlines()]
    lines = [ln if ln[-1] in ".!?:;," else ln + "." for ln in lines if ln]
    text = " ".join(lines)
    text = re.sub(r"\s+([.,;:!?])", r"\1", text)
    text = re.sub(r"([.,;:!?])\1+", r"\1", text)
    text = re.sub(r"\s{2,}", " ", text).strip()
    return text if re.search(r"\w", text) else ""


def truncate(text, max_chars):
    if not max_chars or len(text) <= max_chars:
        return text
    cut = text[:max_chars]
    end = max(cut.rfind(". "), cut.rfind("! "), cut.rfind("? "))
    if end > max_chars // 2:
        cut = cut[: end + 1]
    return cut + " ... and more on screen."


# --------------------------------------------------------------------------
# Finding what Claude said this turn
# --------------------------------------------------------------------------

def _is_real_user_prompt(entry):
    """A prompt you typed, as opposed to a tool result fed back to Claude."""
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = entry.get("message", {}).get("content")
    if isinstance(content, str):
        return True
    if isinstance(content, list):
        return any(b.get("type") == "text" for b in content if isinstance(b, dict))
    return False


def last_turn_text(transcript_path):
    entries = []
    try:
        with open(transcript_path) as f:
            for line in f:
                try:
                    entries.append(json.loads(line))
                except ValueError:
                    continue
    except OSError:
        return ""

    start = 0
    for i, entry in enumerate(entries):
        if _is_real_user_prompt(entry):
            start = i + 1

    parts = []
    for entry in entries[start:]:
        if entry.get("type") != "assistant":
            continue
        content = entry.get("message", {}).get("content")
        if isinstance(content, str):
            parts.append(content)
        elif isinstance(content, list):
            parts.extend(
                b.get("text", "") for b in content
                if isinstance(b, dict) and b.get("type") == "text"
            )
    return "\n\n".join(p for p in parts if p.strip())


# --------------------------------------------------------------------------
# Speaking
# --------------------------------------------------------------------------

def stop_speaking():
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.killpg(pid, signal.SIGTERM)
    except (OSError, ValueError):
        pass
    try:
        os.remove(PID_FILE)
    except OSError:
        pass


def tts_command(config):
    voice, rate = config.get("voice"), int(config.get("rate") or 0)
    if sys.platform == "darwin" and shutil.which("say"):
        cmd = ["say"]
        if voice:
            cmd += ["-v", voice]
        if rate:
            cmd += ["-r", str(rate)]
        return cmd, "stdin"
    for exe in ("espeak-ng", "espeak"):
        if shutil.which(exe):
            cmd = [exe]
            if voice:
                cmd += ["-v", voice]
            if rate:
                cmd += ["-s", str(rate)]
            return cmd + ["--stdin"], "stdin"
    if shutil.which("spd-say"):
        cmd = ["spd-say", "--wait"]
        if voice:
            cmd += ["-y", voice]
        return cmd, "arg"
    return None, None


def speak(text, config):
    cmd, mode = tts_command(config)
    if not cmd:
        return
    stop_speaking()
    os.makedirs(HOME_DIR, exist_ok=True)
    if mode == "arg":
        cmd = cmd + [text]
    # Detach fully so Claude Code doesn't wait for the speech to finish.
    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE if mode == "stdin" else subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    if mode == "stdin":
        proc.stdin.write(text.encode())
        proc.stdin.close()
    with open(PID_FILE, "w") as f:
        f.write(str(proc.pid))


# --------------------------------------------------------------------------

def handle_hook(payload):
    event = payload.get("hook_event_name")
    if event == "UserPromptSubmit":
        stop_speaking()
        return
    if event != "Stop" or os.path.exists(MUTE_FILE):
        return
    config = load_config()
    raw = last_turn_text(payload.get("transcript_path", ""))
    # The final message may not be flushed to the transcript yet.
    last = payload.get("last_assistant_message") or ""
    if isinstance(last, str) and last.strip() and last.strip() not in raw:
        raw = f"{raw}\n\n{last}" if raw else last
    text = truncate(clean_for_speech(raw, config["code_placeholder"]), config["max_chars"])
    if text:
        speak(text, config)


def main():
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "--toggle":
        os.makedirs(HOME_DIR, exist_ok=True)
        if os.path.exists(MUTE_FILE):
            os.remove(MUTE_FILE)
            print("une-tirade: speech ON")
        else:
            open(MUTE_FILE, "w").close()
            stop_speaking()
            print("une-tirade: speech OFF")
    elif arg == "--stop":
        stop_speaking()
    elif arg == "--test":
        speak("Hello! This is une tirade. Code blocks will be skipped.", load_config())
    elif arg == "--filter":
        print(clean_for_speech(sys.stdin.read(), load_config()["code_placeholder"]))
    else:
        try:
            payload = json.load(sys.stdin)
        except ValueError:
            return
        handle_hook(payload)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # A hook must never break Claude Code.
        pass
