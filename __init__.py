"""
MiniMax H3 Prompt Builder — ComfyUI custom nodes.

Assembles spec-compliant MiniMax H3 prompts. The multi-shot builder computes
cut timestamps from per-shot durations and outputs the total duration for the
sampler.

Specs implemented:
  base : docs/VIDEO_PROMPT_WRITING_GUIDE_base_en.md   (T2VA / I2VA / FL2VA / L2VA)
  ref  : docs/VIDEO_PROMPT_WRITING_GUIDE_ref_en.md    (full-reference / r2v)

Install: custom_nodes/comfyui-minimax-h3/__init__.py, with the button
script at custom_nodes/comfyui-minimax-h3/web/minimax_h3_buttons.js
"""

import os

WEB_DIRECTORY = "./web"

# The button script is written out from here on startup rather than shipped as
# a loose file, so there is only ever one file to install and updates can't
# fall out of sync with the Python.
_BUTTON_JS = r"""
import { app } from "../../scripts/app.js";

console.log("[MiniMax H3] button extension loaded");

// Which node's which widget gets the buttons.
const TARGETS = {
    MiniMaxH3Shot: "text",
    MiniMaxH3PromptBuilder: "description",
};

const BUTTONS = [
    { label: "wrap <d> dialogue", before: "<d>[English] ", after: "</d>" },
    { label: 'wrap "on-screen text"', before: '"', after: '"' },
];

// ComfyUI has used both inputEl and element for DOM widgets across versions.
function getTextArea(widget) {
    if (!widget) return null;
    if (widget.inputEl?.tagName === "TEXTAREA") return widget.inputEl;
    if (widget.element?.tagName === "TEXTAREA") return widget.element;
    return widget.element?.querySelector?.("textarea") ?? null;
}

function wrapSelection(node, widgetName, before, after) {
    const widget = node.widgets?.find((w) => w.name === widgetName);
    const el = getTextArea(widget);
    if (!el) {
        console.warn("[MiniMax H3] no textarea found for", widgetName);
        return;
    }

    const start = el.selectionStart ?? 0;
    const end = el.selectionEnd ?? 0;
    const value = el.value ?? "";

    if (start === end) {
        // Nothing highlighted — drop an empty pair at the caret so the tag
        // can still be typed into.
        const insert = before + after;
        el.value = value.slice(0, start) + insert + value.slice(start);
        el.selectionStart = el.selectionEnd = start + before.length;
    } else {
        const selected = value.slice(start, end).trim();
        const replacement = before + selected + after;
        el.value = value.slice(0, start) + replacement + value.slice(end);
        el.selectionStart = start;
        el.selectionEnd = start + replacement.length;
    }

    // Keep the widget's stored value in step with the DOM, or the change is
    // lost the moment the node re-renders.
    widget.value = el.value;
    el.dispatchEvent(new Event("input", { bubbles: true }));
    el.focus();
    node.graph?.setDirtyCanvas(true, true);
}

app.registerExtension({
    name: "minimax.h3.textbuttons",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        const widgetName = TARGETS[nodeData.name];
        if (!widgetName) return;

        const onNodeCreated = nodeType.prototype.onNodeCreated;
        nodeType.prototype.onNodeCreated = function () {
            const result = onNodeCreated?.apply(this, arguments);
            const node = this;

            const created = [];
            for (const spec of BUTTONS) {
                created.push(
                    node.addWidget("button", spec.label, null, () => {
                        wrapSelection(node, widgetName, spec.before, spec.after);
                    })
                );
            }

            // addWidget appends to the bottom of the node; move the buttons up
            // so they sit directly beneath the box they act on.
            const targetIndex = node.widgets.findIndex(
                (w) => w.name === widgetName
            );
            if (targetIndex !== -1) {
                for (const btn of created) {
                    const at = node.widgets.indexOf(btn);
                    if (at !== -1) node.widgets.splice(at, 1);
                }
                node.widgets.splice(targetIndex + 1, 0, ...created);
                node.graph?.setDirtyCanvas(true, true);
            }

            return result;
        };
    },
});
"""


def _install_web_assets():
    """Create ./web and write the button script. Reports what it did."""
    module_dir = os.path.dirname(os.path.abspath(__file__))
    web_dir = os.path.join(module_dir, "web")
    target = os.path.join(web_dir, "minimax_h3_buttons.js")
    try:
        os.makedirs(web_dir, exist_ok=True)
        existing = ""
        if os.path.isfile(target):
            with open(target, "r", encoding="utf-8") as fh:
                existing = fh.read()
        if existing != _BUTTON_JS:
            with open(target, "w", encoding="utf-8") as fh:
                fh.write(_BUTTON_JS)
            action = "wrote"
        else:
            action = "verified"
        print("[MiniMax H3] %s %s" % (action, target))
        print("[MiniMax H3] serving at /extensions/%s/minimax_h3_buttons.js"
              % os.path.basename(module_dir))
    except OSError as err:
        print("[MiniMax H3] could not write web assets: %s" % err)


_install_web_assets()


# --------------------------------------------------------------------------
# Alignment-instruction templates.
#
# NOTE: bracket style is verbatim from the official guide, which is internally
# inconsistent — I2VA and L2VA use <Picture N> / [Shot N] while FL2VA uses bare
# Picture N / Shot N. Flip NORMALISE_BRACKETS to make FL2VA match the others.
# --------------------------------------------------------------------------

NORMALISE_BRACKETS = False

MAX_SHOTS = 8

# MiniMax H3 is hardcoded and trained at 24fps. Not exposed as a widget —
# any other value would only ever produce a frame count the sampler rejects.
FPS = 24

I2VA_LINE = (
    "For the target video, at 0.00 seconds into the target video, "
    "<Picture 1> (from [Shot 1]) is fully referenced."
)

FL2VA_LINE = (
    "How the reference pictures align with the target video — "
    "Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; "
    "Picture 2 (from Shot {n}) aligns with the {s}-second mark of the target video."
)

FL2VA_LINE_BRACKETED = (
    "How the reference pictures align with the target video — "
    "<Picture 1> (from [Shot 1]) aligns with the 0.00-second mark of the target video; "
    "<Picture 2> (from [Shot {n}]) aligns with the {s}-second mark of the target video."
)

L2VA_LINE = (
    "How the reference pictures align with the target video — "
    "<Picture 1> (from [Shot {n}]) aligns with the {s}-second mark of the target video."
)

MODES = ["T2VA", "I2VA", "FL2VA", "L2VA"]

CUT_VERBS = [
    "the camera cuts to",
    "the shot cuts to",
    "the shot transitions to",
    "the shot changes to",
    "the shot switches to",
]

# What a referenced asset contributes to a subject. Phrased as
# "<Subject 1> is ..., whose appearance comes from <Picture 1>."
CONTENT_ROLES = [
    "appearance",
    "motion",
    "action",
    "expression",
    "pose",
    "costume",
    "style",
    "scene",
    "environment",
    "camera and cut structure",
    "voice timbre",
]

# Frame-anchor roles instead read
# "<Picture 1> is the last frame of [Shot 2], showing ..."
FRAME_ROLES = [
    "first frame",
    "last frame",
    "keyframe",
    "composition anchor",
]

NONE_OPTION = "-"

TASK_TYPES = [
    "keyframe completion",
    "reference generation",
    "video editing",
    "video continuation",
    "audio reuse",
    "audio reference",
]


def _clean(text):
    return (text or "").strip()


def _fmt_duration(seconds):
    """Spec requires exactly two decimal places."""
    return f"{float(seconds):.2f}"


def _timestamp(seconds):
    """Cut-time format: MM:SS.m — one decimal."""
    minutes = int(seconds // 60)
    remainder = seconds - minutes * 60
    return f"{minutes:02d}:{remainder:04.1f}"


def _strip_field_prefix(text, *field_names):
    """Tolerate a body that already carries its field label."""
    text = _clean(text)
    for name in field_names:
        prefix = f"{name}:"
        if text.lower().startswith(prefix.lower()):
            return text[len(prefix):].lstrip()
    return text


def _default_na(text):
    text = _clean(text)
    return text if text else "N/A"


def _snap_frames(seconds):
    """
    MiniMax H3 wants a frame count of the form 17n+5. Snap to the nearest
    valid value at or above 5 rather than handing the sampler a length it
    will reject.
    """
    raw = float(seconds) * FPS
    n = round((raw - 5) / 17)
    if n < 0:
        n = 0
    return int(17 * n + 5)


def _alignment_line(mode, last_shot_index, total_seconds):
    s = _fmt_duration(total_seconds)
    n = int(last_shot_index)
    if mode == "T2VA":
        return None
    if mode == "I2VA":
        return I2VA_LINE
    if mode == "FL2VA":
        template = FL2VA_LINE_BRACKETED if NORMALISE_BRACKETS else FL2VA_LINE
        return template.format(n=n, s=s)
    if mode == "L2VA":
        return L2VA_LINE.format(n=n, s=s)
    raise ValueError(f"Unknown mode: {mode}")


def _shot_body(shot_list):
    """
    Turn a Shot chain into one body paragraph with cumulative cut times.
    Returns (body_text, total_seconds). Shared by every builder that accepts
    a chain, so timestamps are identical across base modes and r2v.
    """
    chunks, elapsed = [], 0.0

    for i, shot in enumerate(shot_list, start=1):
        body = _clean(shot.get("text", ""))

        if i == 1:
            header = "[Shot 1]"
        else:
            verb = shot.get("cut_verb") or CUT_VERBS[0]
            header = f"[Shot {i}] At {_timestamp(elapsed)}, {verb}"

        chunks.append(f"{header} {body}".rstrip())
        elapsed += float(shot.get("seconds", 0.0) or 0.0)

    return " ".join(chunks), round(elapsed, 3)


def _assemble(shot_list, mode, overall_soundscape, non_diegetic_music):
    """
    Shared assembly for both the fixed-slot builder and the chained Shot nodes.
    shot_list is a list of {"seconds": float, "text": str, "cut_verb": str}
    in playback order. Each shot's cut_verb describes the cut *into* that shot,
    so shot 1's is unused.
    """
    body_text, total = _shot_body(shot_list)
    parts = []
    alignment = _alignment_line(mode, max(len(shot_list), 1), total)
    if alignment:
        parts.append(alignment)
    parts.append("integrated_multimodal_description: " + body_text)
    parts.append(
        "overall_soundscape: "
        + _default_na(_strip_field_prefix(overall_soundscape, "overall_soundscape"))
    )
    parts.append(
        "non_diegetic_music: "
        + _default_na(_strip_field_prefix(non_diegetic_music, "non_diegetic_music"))
    )

    frames = _snap_frames(total)

    return ("\n\n".join(parts), total, frames)


# ==========================================================================
# Chained per-shot nodes — add one Shot node per shot, no fixed ceiling
# ==========================================================================

class MiniMaxH3Shot:
    """
    One shot. Chain them: Shot 1 -> Shot 2 -> Shot 3 -> Assemble.

    Leave `shots` unconnected on the first shot in the chain. Order is set by
    the wiring, so inserting a shot mid-sequence renumbers everything after it
    and recomputes every cut time automatically.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "cut_verb": (
                    CUT_VERBS,
                    {
                        "default": CUT_VERBS[0],
                        "tooltip": "How the cut INTO this shot is worded. "
                        "Ignored on the first shot of the chain, which has no "
                        "cut before it.",
                    },
                ),
                "seconds": (
                    "FLOAT",
                    {
                        "default": 5.0,
                        "min": 0.1,
                        "max": 600.0,
                        "step": 0.1,
                        "tooltip": "Duration of this shot. Sets the next shot's "
                        "cut time and adds to the total.",
                    },
                ),
                "text": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "Body only — the [Shot N] header and timestamp "
                        "are added for you. Style goes at the start of shot 1. "
                        "Use the buttons below to wrap a selection in <d> tags "
                        "or quotes.",
                    },
                ),
            },
            "optional": {
                "shots": ("MMH3_SHOTS", {"tooltip": "Chain from the previous "
                                         "Shot node. Leave empty on shot 1."}),
            },
        }

    RETURN_TYPES = ("MMH3_SHOTS",)
    RETURN_NAMES = ("shots",)
    FUNCTION = "add"
    CATEGORY = "MiniMax H3"

    def add(self, cut_verb, seconds, text, shots=None):
        chain = list(shots) if shots else []
        chain.append({
            "seconds": float(seconds),
            "text": _clean(text),
            "cut_verb": cut_verb,
        })
        return (chain,)


class MiniMaxH3Assemble:
    """
    Terminates a Shot chain and emits the finished prompt.

    frames is the total duration snapped to the nearest 17n+5 at 24fps —
    wire it to a Display Int to check the timing before generating.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "shots": ("MMH3_SHOTS",),
                "mode": (MODES, {"default": "T2VA"}),
                "overall_soundscape": ("STRING", {"multiline": True, "default": ""}),
                "non_diegetic_music": ("STRING", {"multiline": True, "default": ""}),
            }
        }

    RETURN_TYPES = ("STRING", "FLOAT", "INT")
    RETURN_NAMES = ("prompt", "total_seconds", "frames")
    FUNCTION = "build"
    CATEGORY = "MiniMax H3"

    def build(self, shots, mode, overall_soundscape, non_diegetic_music):
        return _assemble(shots or [], mode,
                         overall_soundscape, non_diegetic_music)


# ==========================================================================
# Multi-shot builder
# ==========================================================================

class MiniMaxH3MultiShotBuilder:
    """
    Per-shot boxes with per-shot durations.

    Cut timestamps are computed cumulatively and prepended to each shot after
    the first. Total duration feeds both the FL2VA/L2VA alignment line and the
    sampler outputs, so the numbers cannot drift apart.

    shot_count controls how many boxes are read. The bundled JS hides the
    unused ones; if it fails to load they simply stay visible and are ignored.
    """

    @classmethod
    def INPUT_TYPES(cls):
        required = {
            "mode": (MODES, {"default": "T2VA"}),
            "shot_count": (
                "INT",
                {
                    "default": 1,
                    "min": 1,
                    "max": MAX_SHOTS,
                    "tooltip": "How many shot boxes to read. Boxes beyond this "
                    "are ignored.",
                },
            ),
            "cut_verb": (CUT_VERBS, {"default": CUT_VERBS[0]}),
        }

        for i in range(1, MAX_SHOTS + 1):
            required[f"shot_{i}_seconds"] = (
                "FLOAT",
                {
                    "default": 5.0 if i == 1 else 3.0,
                    "min": 0.1,
                    "max": 600.0,
                    "step": 0.1,
                    "tooltip": f"Duration of shot {i}. Sets the cut time of "
                    f"shot {i + 1} and adds to the total.",
                },
            )
            required[f"shot_{i}_text"] = (
                "STRING",
                {
                    "multiline": True,
                    "default": "",
                    "tooltip": "Body only — the [Shot N] header and timestamp "
                    "are added for you."
                    + (" Style goes at the start of shot 1." if i == 1 else ""),
                },
            )

        required["overall_soundscape"] = (
            "STRING",
            {
                "multiline": True,
                "default": "",
                "tooltip": "Ambience, physical action sounds, non-verbal human "
                "sounds. No dialogue or score. Blank becomes N/A.",
            },
        )
        required["non_diegetic_music"] = (
            "STRING",
            {
                "multiline": True,
                "default": "",
                "tooltip": "Instrumentation, tempo, rhythm, dynamics. No mood "
                "words. Blank becomes N/A.",
            },
        )
        return {"required": required}

    RETURN_TYPES = ("STRING", "FLOAT", "INT")
    RETURN_NAMES = ("prompt", "total_seconds", "frames")
    FUNCTION = "build"
    CATEGORY = "MiniMax H3"

    def build(self, mode, shot_count, cut_verb,
              overall_soundscape, non_diegetic_music, **kwargs):
        count = max(1, min(int(shot_count), MAX_SHOTS))
        shot_list = [
            {
                "seconds": kwargs.get(f"shot_{i}_seconds", 0.0),
                "text": kwargs.get(f"shot_{i}_text", ""),
                "cut_verb": cut_verb,
            }
            for i in range(1, count + 1)
        ]
        return _assemble(shot_list, mode,
                         overall_soundscape, non_diegetic_music)


# ==========================================================================
# Single-body builder (kept — simpler when you don't need per-shot boxes)
# ==========================================================================

class MiniMaxH3PromptBuilder:
    """Write the whole body yourself; this only adds the scaffolding."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "mode": (MODES, {"default": "T2VA"}),
                "description": (
                    "STRING",
                    {"multiline": True, "default": "[Shot 1] Live-action, cinematic, "},
                ),
                "overall_soundscape": ("STRING", {"multiline": True, "default": ""}),
                "non_diegetic_music": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "duration_seconds": (
                    "FLOAT",
                    {"default": 6.00, "min": 0.0, "max": 600.0, "step": 0.01},
                ),
                "last_shot_index": ("INT", {"default": 1, "min": 1, "max": 99}),
            },
        }

    RETURN_TYPES = ("STRING",)
    RETURN_NAMES = ("prompt",)
    FUNCTION = "build"
    CATEGORY = "MiniMax H3"

    def build(self, mode, description, overall_soundscape, non_diegetic_music,
              duration_seconds=6.00, last_shot_index=1):
        body = _strip_field_prefix(description, "integrated_multimodal_description")
        parts = []
        alignment = _alignment_line(mode, last_shot_index, duration_seconds)
        if alignment:
            parts.append(alignment)
        parts.append(f"integrated_multimodal_description: {body}")
        parts.append(
            "overall_soundscape: "
            + _default_na(_strip_field_prefix(overall_soundscape, "overall_soundscape"))
        )
        parts.append(
            "non_diegetic_music: "
            + _default_na(_strip_field_prefix(non_diegetic_music, "non_diegetic_music"))
        )
        return ("\n\n".join(parts),)


# ==========================================================================
# Full-reference (r2v) builder
# ==========================================================================

class MiniMaxH3Subject:
    """
    One subject_definitions line. Chain them:
    Subject 1 -> Subject 2 -> ... -> the r2v builder's `subjects` input.

    Two phrasings, chosen by the role:

      content role  -> <Subject 1> is <description>, whose <role> comes from
                       <reference>.
      frame role    -> <Picture 1> is the <role> of <reference>, <description>.

    An image that only defines a character is cited inside that character's
    Subject line. It earns its own <Picture N> line only when it is a concrete
    frame anchor — that's what the frame roles are for.
    """

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "label": (
                    "STRING",
                    {
                        "default": "<Subject 1>",
                        "tooltip": "The label this line defines. <Subject N> for "
                        "reusable visible content, <Picture N> only for a "
                        "concrete frame anchor, <Video N> for whole-video "
                        "relationships, <Audio N> for sound.",
                    },
                ),
                "description": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "Who or what this is, plus the features to "
                        "follow. e.g. 'Thimble, the peach-pink plush creature "
                        "with dandelion-puff antennae and rosy cheeks'.",
                    },
                ),
                "role": (
                    CONTENT_ROLES + FRAME_ROLES,
                    {
                        "default": CONTENT_ROLES[0],
                        "tooltip": "What the reference supplies. The frame roles "
                        "at the bottom of the list switch to frame-anchor "
                        "phrasing, where reference should be a shot like "
                        "[Shot 1].",
                    },
                ),
                "reference": (
                    "STRING",
                    {
                        "default": "<Picture 1>",
                        "tooltip": "The asset this role comes from — <Picture 1>, "
                        "<Video 1>, <Audio 1>. For a frame role, the shot it "
                        "anchors, e.g. [Shot 1].",
                    },
                ),
                "role_2": (
                    [NONE_OPTION] + CONTENT_ROLES,
                    {
                        "default": NONE_OPTION,
                        "tooltip": "Optional second role, for a subject that "
                        "draws on two assets — appearance from one, motion from "
                        "another.",
                    },
                ),
                "reference_2": (
                    "STRING",
                    {"default": "", "tooltip": "The asset supplying role_2."},
                ),
            },
            "optional": {
                "subjects": ("MMH3_SUBJECTS", {"tooltip": "Chain from the "
                             "previous Subject node. Leave empty on the first."}),
            },
        }

    RETURN_TYPES = ("MMH3_SUBJECTS",)
    RETURN_NAMES = ("subjects",)
    FUNCTION = "add"
    CATEGORY = "MiniMax H3"

    def add(self, label, description, role, reference, role_2, reference_2,
            subjects=None):
        chain = list(subjects) if subjects else []

        head = _clean(label)
        desc = _clean(description).rstrip(".")
        ref = _clean(reference)
        ref2 = _clean(reference_2)

        if role in FRAME_ROLES:
            line = f"{head} is the {role}"
            if ref:
                line += f" of {ref}"
            if desc:
                line += f", showing {desc}"
        else:
            line = f"{head} is"
            if desc:
                line += f" {desc}"
            clauses = []
            if ref:
                clauses.append(f"whose {role} comes from {ref}")
            if role_2 != NONE_OPTION and ref2:
                clauses.append(f"whose {role_2} comes from {ref2}")
            if clauses:
                joiner = ", " if desc else " "
                line += joiner + " and ".join(clauses)

        chain.append(line.rstrip(".") + ".")
        return (chain,)


class MiniMaxH3RefPromptBuilder:
    """The six-section full-reference output format, in fixed spec order."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "subject_definitions": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "<Subject 1> is ",
                        "tooltip": "Cite a defining image inside the Subject "
                        "line; give <Picture N> its own line only when it is a "
                        "concrete frame anchor.",
                    },
                ),
                "task_type": (
                    TASK_TYPES,
                    {
                        "default": "reference generation",
                        "tooltip": "The primary relationship. Combine up to "
                        "three; they appear in the order selected.",
                    },
                ),
                "task_type_2": (
                    [NONE_OPTION] + TASK_TYPES,
                    {"default": NONE_OPTION, "tooltip": "Optional second type."},
                ),
                "task_type_3": (
                    [NONE_OPTION] + TASK_TYPES,
                    {"default": NONE_OPTION, "tooltip": "Optional third type."},
                ),
                "summary": ("STRING", {"multiline": True, "default": ""}),
                "retention_analysis": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "Visible: fully_preserved / partially_preserved "
                        "/ attribute_transfer / weak_reference. Audio: fully_copy "
                        "/ partially_copy / reference / weak_reference. Never (Sx).",
                    },
                ),
                "style_line": (
                    "STRING",
                    {
                        "multiline": True,
                        "default": "",
                        "tooltip": "1-2 sentences, placed BEFORE [Shot 1] — r2v "
                        "differs from T2VA here.",
                    },
                ),
                "detailed_description": (
                    "STRING",
                    {"multiline": True, "default": "[Shot 1] "},
                ),
                "overall_soundscape": ("STRING", {"multiline": True, "default": ""}),
                "non_diegetic_music": ("STRING", {"multiline": True, "default": ""}),
            },
            "optional": {
                "subjects": ("MMH3_SUBJECTS", {"tooltip": "Chain of Subject "
                             "nodes. Overrides the subject_definitions box when "
                             "connected."}),
                "shots": ("MMH3_SHOTS", {"tooltip": "Chain of Shot nodes. "
                          "Overrides the detailed_description box and supplies "
                          "the duration outputs."}),
            },
        }

    RETURN_TYPES = ("STRING", "FLOAT", "INT")
    RETURN_NAMES = ("prompt", "total_seconds", "frames")
    FUNCTION = "build"
    CATEGORY = "MiniMax H3"

    def _format_task_prefix(self, selected):
        """Keep the selected order, drop blanks and repeats."""
        kept = []
        for name in selected:
            if name and name != NONE_OPTION and name not in kept:
                kept.append(name)
        if not kept:
            kept = ["reference generation"]
        return "[" + " + ".join(kept) + "]"

    def build(self, subject_definitions, task_type, task_type_2, task_type_3,
              summary, retention_analysis, style_line, detailed_description,
              overall_soundscape, non_diegetic_music, subjects=None,
              shots=None):
        selected = [task_type, task_type_2, task_type_3]

        if subjects:
            subjects_text = "\n".join(subjects)
        else:
            subjects_text = _strip_field_prefix(subject_definitions,
                                                "subject_definitions")
        retention_text = _strip_field_prefix(retention_analysis,
                                             "retention_analysis")
        if shots:
            body, total = _shot_body(shots)
        else:
            # No chain wired — the body is typed in and there is nothing to
            # measure, so the duration outputs report zero.
            body = _strip_field_prefix(detailed_description,
                                       "detailed_description")
            total = 0.0
        style = _clean(style_line)

        summary_text = _strip_field_prefix(summary, "summary")
        if summary_text.startswith("["):
            summary_block = summary_text
        else:
            summary_block = (
                f"{self._format_task_prefix(selected)} {summary_text}".strip()
            )

        if style:
            body = f"{style}\n{body}"

        parts = [
            f"subject_definitions:\n{subjects_text}",
            f"summary:\n{summary_block}",
            f"retention_analysis:\n{retention_text}",
            f"detailed_description:\n{body}",
            "overall_soundscape:\n"
            + _default_na(_strip_field_prefix(overall_soundscape, "overall_soundscape")),
            "non_diegetic_music:\n"
            + _default_na(_strip_field_prefix(non_diegetic_music, "non_diegetic_music")),
        ]
        return ("\n\n".join(parts), total, _snap_frames(total))


# ==========================================================================
# Standalone shot timer
# ==========================================================================

class MiniMaxH3ShotTimer:
    """Durations in, spec-formatted shot headers out."""

    @classmethod
    def INPUT_TYPES(cls):
        return {
            "required": {
                "durations": ("STRING", {"multiline": True, "default": "5\n2"}),
                "cut_verb": (CUT_VERBS, {"default": CUT_VERBS[0]}),
            }
        }

    RETURN_TYPES = ("STRING", "FLOAT")
    RETURN_NAMES = ("shot_headers", "total_seconds")
    FUNCTION = "build"
    CATEGORY = "MiniMax H3"

    def build(self, durations, cut_verb):
        values = []
        for line in _clean(durations).splitlines():
            line = line.strip().rstrip("s").strip()
            if not line:
                continue
            try:
                values.append(float(line))
            except ValueError:
                continue

        if not values:
            return ("[Shot 1] ", 0.0)

        headers, elapsed = [], 0.0
        for i, dur in enumerate(values, start=1):
            if i == 1:
                headers.append("[Shot 1] ")
            else:
                headers.append(f"[Shot {i}] At {_timestamp(elapsed)}, {cut_verb} ")
            elapsed += dur

        return ("\n".join(headers), round(elapsed, 3))


NODE_CLASS_MAPPINGS = {
    "MiniMaxH3Shot": MiniMaxH3Shot,
    "MiniMaxH3Assemble": MiniMaxH3Assemble,
    "MiniMaxH3MultiShotBuilder": MiniMaxH3MultiShotBuilder,
    "MiniMaxH3PromptBuilder": MiniMaxH3PromptBuilder,
    "MiniMaxH3Subject": MiniMaxH3Subject,
    "MiniMaxH3RefPromptBuilder": MiniMaxH3RefPromptBuilder,
    "MiniMaxH3ShotTimer": MiniMaxH3ShotTimer,
}

NODE_DISPLAY_NAME_MAPPINGS = {
    "MiniMaxH3Shot": "MiniMax H3 Shot",
    "MiniMaxH3Assemble": "MiniMax H3 Assemble",
    "MiniMaxH3MultiShotBuilder": "MiniMax H3 Multi Shot Builder",
    "MiniMaxH3PromptBuilder": "MiniMax H3 Prompt Builder",
    "MiniMaxH3Subject": "MiniMax H3 Subject",
    "MiniMaxH3RefPromptBuilder": "MiniMax H3 Ref Prompt Builder r2v",
    "MiniMaxH3ShotTimer": "MiniMax H3 Shot Timer",
}

print("[MiniMax H3 Prompt] registered %d nodes: %s"
      % (len(NODE_CLASS_MAPPINGS), ", ".join(NODE_DISPLAY_NAME_MAPPINGS.values())))
