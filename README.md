# claude-une-tirade
une tirade: a long, uninterrupted speech, sometimes with a slightly negative feel (a rant)

Makes Claude Code **read its replies out loud** while you keep typing as usual.
It only speaks the prose: code blocks, tables, file paths, URLs, and long
inline commands are skipped. Short inline words like `install` are kept.

- When Claude finishes a turn, everything it wrote that turn is spoken.
- When you send a new prompt, the current speech stops.
- If a reply is very long, it's cut off after `max_chars` with "...and more on screen".

Works on macOS (built-in `say`) and Linux (`espeak-ng`, `espeak`, or `spd-say`).
Requires `python3`.

## Setup 

**1. Clone the repo anywhere and symlink it to `~/.claude/une-tirade`**

From the directory where you keep your projects:

```bash
git clone <this-repo-url>
ln -sfn "$(pwd)/claude-une-tirade" ~/.claude/une-tirade
```

Check that the link points to the repo (this should print the path to `speak.py`):

```bash
ls ~/.claude/une-tirade/speak.py
```

On Linux, also install a TTS engine: `sudo apt install espeak-ng`

**2. Add the hooks to `~/.claude/settings.json`**

Merge this into the file (keep whatever settings are already there):

```json
{
  "hooks": {
    "Stop": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/une-tirade/speak.py", "timeout": 10 }] }
    ],
    "UserPromptSubmit": [
      { "hooks": [{ "type": "command", "command": "python3 ~/.claude/une-tirade/speak.py", "timeout": 10 }] }
    ]
  }
}
```

If you already have `Stop` or `UserPromptSubmit` hooks, add the entry to the existing list.

**3. Restart Claude Code.** Check with `/hooks` that both hooks show up.

Test the voice:

```bash
python3 ~/.claude/une-tirade/speak.py --test
```

## Usage

| Command | What it does |
|---|---|
| `python3 ~/.claude/une-tirade/speak.py --toggle` | Mute / unmute |
| `python3 ~/.claude/une-tirade/speak.py --stop` | Stop the current speech |
| `python3 ~/.claude/une-tirade/speak.py --test` | Speak a test sentence |
| `echo '...markdown...' \| python3 ~/.claude/une-tirade/speak.py --filter` | Show what would be spoken |

Inside Claude Code, prefix with `!` to run one without leaving the session,
e.g. `! python3 ~/.claude/une-tirade/speak.py --toggle`.

Tip: add an alias to your shell rc:

```bash
alias tts='python3 ~/.claude/une-tirade/speak.py --toggle'
```

## Configuration (optional)

```bash
cp ~/.claude/une-tirade/config.example.json ~/.claude/une-tirade/config.json
```

| Key | Default | Meaning |
|---|---|---|
| `voice` | `""` (system default) | Voice name. macOS: list with `say -v '?'` (e.g. `"Samantha"`, `"Daniel"`) |
| `rate` | `0` (system default) | Words per minute, e.g. `200` |
| `max_chars` | `1500` | Cut off longer replies. `0` = no limit |
| `code_placeholder` | `""` | Spoken in place of a code block, e.g. `"code block"`. Empty = skip silently |

`config.json` is git-ignored, so each machine can have its own settings.

## Troubleshooting

**`can't open file '.../.claude/une-tirade/speak.py': [Errno 2] No such file or directory`**

The symlink doesn't point to the repo. Check where it points:

```bash
readlink ~/.claude/une-tirade
```

If that isn't the repo folder (a common mistake is running `ln -s` from the
wrong directory, so it points to your home folder), recreate it. Run this from
the folder that contains `claude-une-tirade`:

```bash
ln -sfn "$(pwd)/claude-une-tirade" ~/.claude/une-tirade
ls ~/.claude/une-tirade/speak.py
```

No restart needed: the hook runs the script fresh on every reply.

**Nothing is spoken**

- Check you're not muted: if the file `~/.claude/une-tirade/muted` exists, speech is off. Run `--toggle` to unmute.
- Run `python3 ~/.claude/une-tirade/speak.py --test` to check the voice works.
- Run `/hooks` in Claude Code to check both hooks are registered.

## Updating

```bash
cd ~/.claude/une-tirade && git pull
```

## Uninstall

Remove the two hook entries from `~/.claude/settings.json`, then remove the symlink
with `rm ~/.claude/une-tirade` (no trailing slash, so the repo itself stays).
