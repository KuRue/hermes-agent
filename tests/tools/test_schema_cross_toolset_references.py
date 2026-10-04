"""No schema description may name a tool the session does not have.

tools/AGENTS.md: "Schema descriptions must not name tools from other toolsets …
Those tools may be unavailable (missing key, disabled toolset) and the model
hallucinates calls to them. Cross-references are added dynamically in
``get_tool_definitions()``." The rule is the point of ``_CROSS_TOOLSET_POINTERS``,
and this is the contract test that rule was missing.

These run over a RESTRICTED bundle on purpose: in a full bundle every tool is
present, so the rule cannot fail and the test would pass vacuously. A child
spawned with a narrow ``toolsets`` list is the case that matters.
"""

import re

import pytest

from model_tools import get_tool_definitions

# The file tools contrast themselves with the SHELL, not with the `terminal` tool:
# "Use this instead of sed/awk in terminal". That is a prohibition, so it cannot
# induce a call to an absent tool the way a positive pointer can, and rewording it
# would lose the contrast that sells the tool. Allowlisted with the reason, rather
# than left for the next reader to "fix" into a hallucination.
_ALLOWED_GHOSTS = {
    ("patch", "terminal"),
    ("read_file", "terminal"),
    ("search_files", "terminal"),
    ("write_file", "terminal"),
}

_RESTRICTED_BUNDLES = (["file"], ["web"])


def _known_tool_names():
    # Deliberately no import of the pointer table here: this sweep has to be able to
    # fail on a tree that has no table at all, which a module-level import would
    # convert into a collection error instead of a behavioural failure.
    defs = get_tool_definitions(quiet_mode=True)
    assert defs, "no tool definitions resolved; the sweep below would pass vacuously"
    return {d["function"]["name"] for d in defs}


def _ghosts(defs, known):
    """(tool, named-but-absent) pairs across a resolved bundle."""
    present = {d["function"]["name"] for d in defs}
    found = []
    for d in defs:
        owner = d["function"]["name"]
        description = d["function"].get("description") or ""
        for name in sorted(known - present):
            if name == owner:
                continue
            if re.search(rf"(?<![\w-]){re.escape(name)}(?![\w-])", description):
                found.append((owner, name))
    return found


@pytest.mark.parametrize("bundle", _RESTRICTED_BUNDLES)
def test_no_schema_description_names_an_absent_tool(bundle):
    known = _known_tool_names()
    defs = get_tool_definitions(enabled_toolsets=list(bundle), quiet_mode=True)
    assert defs, f"bundle {bundle} resolved no tools; the assertion would be vacuous"

    violations = [g for g in _ghosts(defs, known) if g not in _ALLOWED_GHOSTS]
    assert not violations, (
        f"schema descriptions in bundle {bundle} name tools the session does not "
        f"have (the model will hallucinate calls to them): {violations}. "
        f"Move the pointer into _CROSS_TOOLSET_POINTERS so it is appended only "
        f"when the target is available."
    )


def test_cross_toolset_pointer_is_appended_only_when_its_target_is_available():
    """The mechanism itself: a table row is honoured, and only under availability."""
    from model_tools import _CROSS_TOOLSET_POINTERS

    full = {d["function"]["name"]: d for d in get_tool_definitions(quiet_mode=True)}
    checked = 0
    for owner, pointers in _CROSS_TOOLSET_POINTERS.items():
        if owner not in full:
            continue  # tool not in this environment's bundle; nothing to assert
        description = full[owner]["function"].get("description") or ""
        for target, sentence in pointers:
            checked += 1
            assert (sentence in description) is (target in full), (
                f"{owner}: pointer {sentence!r} should be present iff {target} is "
                f"available (target available: {target in full})"
            )
    assert checked, "no pointer rows were exercised"


def test_read_file_names_no_vision_tool_when_vision_is_absent():
    """The static/dynamic boundary: the file bundle must be silent about images."""
    defs = get_tool_definitions(enabled_toolsets=["file"], quiet_mode=True)
    names = {d["function"]["name"] for d in defs}
    assert "vision_analyze" not in names, "vision unexpectedly available; bundle is wrong"
    read_file = next(d for d in defs if d["function"]["name"] == "read_file")
    assert "vision_analyze" not in (read_file["function"].get("description") or "")
