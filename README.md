# ComfyUI — MiniMax H3 Prompt Nodes

Seven nodes that assemble spec-compliant MiniMax H3 prompts, so you write shot
content and the scaffolding is generated for you.

Specs implemented:
- `VIDEO_PROMPT_WRITING_GUIDE_base_en.md` — T2VA / I2VA / FL2VA / L2VA
- `VIDEO_PROMPT_WRITING_GUIDE_ref_en.md` — full-reference (r2v)

---

## Install

Unzip so you end up with:

```
ComfyUI\custom_nodes\comfyui-minimax-h3\__init__.py
```

Restart ComfyUI. No dependencies — pure stdlib.

On startup the console prints:

```
[MiniMax H3] wrote ...\comfyui-minimax-h3\web\minimax_h3_buttons.js
[MiniMax H3] serving at /extensions/comfyui-minimax-h3/minimax_h3_buttons.js
[MiniMax H3 Prompt] registered 7 nodes: ...
```

The `web` folder is written by the Python on every start, so there is only one
file to install and the script can't fall out of sync. If the buttons don't
appear, hard-refresh the browser (Ctrl+Shift+R) — the old script gets cached.

All nodes appear under the **MiniMax H3** category.

---

## The two chains

**Base modes** — one Shot node per shot:

```
Shot → Shot → Shot → Assemble → prompt / total_seconds / frames
```

**Full reference (r2v)** — Subject chain plus the same Shot chain:

```
Subject → Subject ─┐
                   ├→ Ref Prompt Builder r2v → prompt / total_seconds / frames / long_shot
Shot → Shot ───────┘
```

---

## Nodes

### MiniMax H3 Shot
`cut_verb`, `seconds`, `text`, and a `shots` chain socket (leave empty on the
first). Cut timestamps are computed cumulatively — set 5 / 2 / 3.5 and you get
`[Shot 2] At 00:05.0,` and `[Shot 3] At 00:07.0,` automatically. Inserting a
node mid-chain renumbers everything downstream.

Two buttons under the text box wrap a highlighted selection in `<d>[English]
...</d>` or in double quotes for on-screen text.

`shot_seed` is only used by [MiniMax H3 Long Shot](https://github.com/r34vtraining/H3_Longshot),
where each Shot is its own generation. Leave it at -1 to follow Long Shot's seed,
or set a number to re-roll just that Shot. The prompt builders ignore it. It's
named `shot_seed` so broadcasters like Seed Everywhere, which feed every input
called `seed`, don't overwrite it.

### MiniMax H3 Assemble
Terminates a Shot chain. `mode` picks T2VA / I2VA / FL2VA / L2VA and the right
alignment instruction is prepended. FL2VA and L2VA take their duration and last
shot index from the chain, so they can't drift from what you actually wrote.

### MiniMax H3 Subject
One `subject_definitions` line. Two phrasings, chosen by the role:

- content role → `<Subject 1> is <description>, whose <role> comes from <reference>.`
- frame role → `<Picture 1> is the <role> of <reference>, showing <description>.`

`role_2` / `reference_2` handle a subject drawing on two assets — appearance
from an image, motion from a video.

### MiniMax H3 Ref Prompt Builder r2v
The six sections in fixed spec order. `subjects` and `shots` chain inputs
override their text boxes when connected. Three ordered `task_type` dropdowns
build the bracketed summary prefix.

The `long_shot` output carries everything on this node plus the Shot chain, for
the **MiniMax H3 Long Shot** node in the separate Long Shot pack. Long Shot builds
one prompt per Shot from it. The other three outputs are unchanged.

### MiniMax H3 Multi Shot Builder
Fixed eight-slot alternative to the Shot chain, with one global cut verb.

### MiniMax H3 Prompt Builder
Single-body builder — you write the whole description including shot headers.

### MiniMax H3 Shot Timer
Durations in (one per line), formatted shot headers out. Useful when typing a
body by hand instead of chaining Shot nodes.

---

## Notes

**24fps is hardcoded.** MiniMax H3 is trained at 24fps, so it's a module
constant rather than a widget. The `frames` output snaps to the nearest valid
`17n+5` length — the lattice isn't evenly spaced, so a shot can shift by up to
~0.35s.

**Cut times use one decimal** (`00:05.0`). The FL2VA/L2VA alignment line keeps
two decimals, which the spec requires.

**FL2VA bracket style** is reproduced verbatim from the official guide, which is
internally inconsistent — I2VA and L2VA use `<Picture 1>` / `[Shot 1]` while
FL2VA uses bare `Picture 1` / `Shot 1`. Set `NORMALISE_BRACKETS = True` near the
top of `__init__.py` to make them match, if FL2VA misbehaves.
