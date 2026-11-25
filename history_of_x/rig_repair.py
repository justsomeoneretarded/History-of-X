"""Make an implied pickup explicit only when a later placement requires it.

This repairs a saved model plan, not the renderer's ownership rules. The normal
contact, timing and geometry checks still run on the resulting scene.
"""
from __future__ import annotations
import copy
import math


def explicit_pickups(spec):
    result = copy.deepcopy(spec)
    if not isinstance(result, dict):
        return result, []
    actions = result.get("actions")
    nodes = result.get("nodes")
    if not isinstance(actions, list) or not isinstance(nodes, list):
        return result, []
    props = {n.get("id") for n in nodes if isinstance(n, dict) and n.get("kind") == "prop"}
    repairs = []

    def interval(action):
        if not isinstance(action, dict):
            return None
        start, seconds = action.get("time"), action.get("duration", .5)
        if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x)
               for x in (start, seconds)):
            return None
        return (start, start + seconds) if start >= 0 and seconds >= 0 else None

    ordered = sorted(enumerate(actions), key=lambda pair: (interval(pair[1]) or (float("inf"),))[0])
    for index, action in ordered:
        span = interval(action)
        if not span or action.get("type") != "place":
            continue
        obj, actor, hand = action.get("object"), action.get("node"), action.get("hand", "front")
        if obj not in props:
            continue
        history = []
        for other_index, other in enumerate(actions):
            other_span = interval(other)
            if other_index == index or not other_span or other_span[1] > span[0] + 1e-7:
                continue
            operation = other.get("type")
            target = other.get("target", other.get("object")) if operation == "take" else other.get("object")
            if operation in ("take", "place") and target == obj:
                owner = (other.get("node"), other.get("hand", "front")) if operation == "take" else None
                history.append((other_span[1], other_index, owner))
        latest = max(history, default=(-1., -1, None))
        if latest[2] == (actor, hand):
            continue
        contacts = []
        for contact_index, contact in enumerate(actions):
            contact_span = interval(contact)
            if (contact_span and contact.get("type") == "reach" and
                contact.get("node") == actor and contact.get("hand", "front") == hand and
                contact.get("target") == obj and contact_span[1] <= span[0] + 1e-7 and
                contact_span[0] >= latest[0] - 1e-7):
                contacts.append((contact_span[1], contact_index, contact_span[0]))
        if not contacts:
            continue
        end, contact_index, start = max(contacts)
        # Do not infer a pickup through a competing use of the same hand.
        conflict = any(
            interval(other) and other.get("type") == "take" and
            other.get("node") == actor and other.get("hand", "front") == hand and
            other.get("target", other.get("object")) != obj and
            start <= interval(other)[0] < span[0]
            for other in actions if isinstance(other, dict)
        )
        if conflict:
            continue
        actions[contact_index]["type"] = "take"
        repairs.append({"action_index": contact_index, "actor": actor, "hand": hand,
                        "object": obj, "time": start, "repair": "reach_to_explicit_pickup"})
    return result, repairs
