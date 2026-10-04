---
name: tts
description: Turn une-tirade text-to-speech on or off, stop it, or check its status. Use when the user wants Claude to stop talking, mute or unmute the voice, or asks whether speech is on.
argument-hint: "[on|off|toggle|stop|status|test]"
allowed-tools: Bash(python3 ~/.claude/une-tirade/speak.py:*)
---

Control une-tirade, the hook that reads Claude Code's replies out loud.

Requested action: `$ARGUMENTS`

Map the request to exactly one command and run it with Bash:

| Request | Command |
|---|---|
| `on`, unmute, start talking | `python3 ~/.claude/une-tirade/speak.py --on` |
| `off`, mute, be quiet | `python3 ~/.claude/une-tirade/speak.py --off` |
| `toggle`, or no argument | `python3 ~/.claude/une-tirade/speak.py --toggle` |
| `stop`, shut up for now (stays enabled) | `python3 ~/.claude/une-tirade/speak.py --stop` |
| `status`, is it on? | `python3 ~/.claude/une-tirade/speak.py --status` |
| `test` | `python3 ~/.claude/une-tirade/speak.py --test` |

Then reply with one short sentence confirming the new state, based on what the command printed. Don't add anything else.
