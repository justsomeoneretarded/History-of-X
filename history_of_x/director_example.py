"""Our original illustration/acting example, supplied as craft guidance only."""
from __future__ import annotations

import copy
from functools import lru_cache

POSITIVE_CRAFT_INSTRUCTION = """
CRAFT BASELINE: The supplied example is our own original vector artwork and
authored acting, not a third-party creator's style or historical evidence.
Study its shaped garments and folds, hair/beard, eyes/brows/nose/mouth, hands,
foreground/table/architecture, color and depth. Study the separate shoulder-
pivoted arm, readable facial states, deliberate holds and document ownership.
Deliver an equally developed FINISHED scene for THIS narration. A circle on a
rectangle, featureless soldiers, a tiny mountain silhouette, an isolated portrait
or a moving blockout is an unacceptable proxy even if its JSON validates.
Keep principal people large enough to read their intentions and expressions.
Design the relevant historical costumes, full silhouettes, purposeful hands and
props; use staged action and reaction to explain the passage's causal change.
Give the scene its own composition, location and blocking. Do not reuse the
example's treaty plot, characters, captions, layout or layer names as a template.
The art is the principal output: spend the response budget on finished SVG and
executable acting, not verbose event descriptions. Do not add a date/location UI;
the editor supplies the year. Check that the actors and their actions stay in
frame at all authored keyframes. Return the entire requested scene program.
"""


def _sparse(frames):
    from .scene_film import DEFAULT
    previous = dict(DEFAULT)
    result = []
    for frame in frames:
        pose = {**previous, **{name: frame[name] for name in DEFAULT if name in frame}}
        result.append({"time": frame["time"],
                       **{name: value for name, value in pose.items()
                          if value != previous[name]},
                       **({"ease": frame["ease"]} if frame.get("ease", "smooth") != "smooth" else {})})
        previous = pose
    return result


@lru_cache(maxsize=1)
def _example():
    from .scene_film import acted_treaty_proof
    source = acted_treaty_proof()
    selected = {"left_body", "left_calm_face", "left_angry_face",
                "left_reading_arm", "right_surprised_face", "document"}
    layers = []
    for layer in source["layers"]:
        if layer["id"] in selected:
            layers.append({**layer, "keyframes": _sparse(layer["keyframes"])})
    return {
        "role": "Internal original craft demonstration; never historical evidence or a scene template.",
        "svg_artwork": source["svg"],
        "choreography_excerpt": layers,
        "camera_excerpt": {"keyframes": _sparse(source["camera"]["keyframes"])},
        "acting_observations": [
            "Offer anticipates contact; the document crosses the table and changes ownership.",
            "A reading arm tilts; calm eyebrows change to an angry facial state at discovery.",
            "The reading hand pushes the document back; the other person's face reacts afterward.",
        ],
    }


def positive_request(instruction, payload, images, directory):
    """Attach original SVG detail, executable examples and one rendered guide.

    Opt-in at plan_scene so ordinary compact requests and narration caches retain
    their established identities. The guide cannot be used as an asset: it has
    no approved historical asset ID.
    """
    from pathlib import Path
    from .scene_film import acted_treaty_proof, scene_frame
    directory = Path(directory)
    guide = directory / "original-acting-craft-guide-v1.jpg"
    if not guide.exists():
        scene_frame(acted_treaty_proof(), 6.8, (1280, 720)).save(guide, quality=88)
    result = copy.deepcopy(payload)
    result["original_craft_example"] = copy.deepcopy(_example())
    roles = ["Approved historical subject reference; honor its date/context."] * len(images)
    roles.append("Our original illustration/acting craft guide; not a historical subject or approved asset.")
    result["attached_image_roles"] = roles
    return instruction + "\n" + POSITIVE_CRAFT_INSTRUCTION, result, [*images, guide], roles
