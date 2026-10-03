"""Regression tests for LLM JSON recovery in query_intelligence.

When a provider wraps its JSON in prose, _extract_json falls back to a regex.
That regex was ``\\{.*\\}`` with re.DOTALL, which is greedy: it spans from the
first brace to the last one in the whole response. A reply containing two
JSON objects therefore captured everything in between and json.loads raised,
silently dropping the model output and falling back to keyword matching.
"""

import json
import re

import pytest


# The current implementation, copied so the test documents the real behaviour.
def extract_json_current(text: str) -> dict:
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].lstrip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if not match:
            raise ValueError("Malformed LLM response: not valid JSON")
        return json.loads(match.group(0))


class TestGreedyRegexIsTheBug:
    def test_two_objects_in_one_response_break_recovery(self):
        """Documents the defect: greedy match spans both objects."""
        text = '{"a": 1} and also {"b": 2}'
        with pytest.raises(json.JSONDecodeError):
            extract_json_current(text)

    def test_nested_objects_are_fine(self):
        text = '{"analysis_type": "NDVI", "params": {"threshold": 0.3}}'
        assert extract_json_current(text)["params"]["threshold"] == 0.3

    def test_markdown_fence_is_handled(self):
        assert extract_json_current('```json\n{"a": 1}\n```') == {"a": 1}

    def test_prose_around_a_single_object_is_fine(self):
        assert extract_json_current('Sure: {"a": 1} done') == {"a": 1}


class TestBalancedScanner:
    """The replacement: walk the string tracking brace depth and string state."""

    @staticmethod
    def _first_json_object(text: str) -> str:
        depth = 0
        start = -1
        in_string = False
        escaped = False

        for index, char in enumerate(text):
            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
            elif char == "{":
                if depth == 0:
                    start = index
                depth += 1
            elif char == "}":
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start >= 0:
                        candidate = text[start : index + 1]
                        try:
                            json.loads(candidate)
                        except json.JSONDecodeError:
                            continue
                        return candidate

        raise ValueError("Malformed LLM response: not valid JSON")

    def test_two_objects_returns_the_first_valid_one(self):
        assert json.loads(self._first_json_object('{"a": 1} and also {"b": 2}')) == {"a": 1}

    def test_nested_object_still_intact(self):
        payload = '{"analysis_type": "NDVI", "params": {"threshold": 0.3, "deep": {"x": 1}}}'
        assert json.loads(self._first_json_object(payload))["params"]["deep"]["x"] == 1

    def test_brace_inside_a_string_does_not_confuse_depth(self):
        payload = '{"note": "use {braces} here", "v": 1}'
        assert json.loads(self._first_json_object(payload))["v"] == 1

    def test_array_of_objects(self):
        payload = 'result: {"items": [{"x": 1}, {"y": 2}]} end'
        assert json.loads(self._first_json_object(payload))["items"][1]["y"] == 2

    def test_escaped_quote_inside_string(self):
        payload = '{"note": "he said \\"hi\\" loudly", "v": 2}'
        assert json.loads(self._first_json_object(payload))["v"] == 2

    def test_leading_prose_then_object(self):
        assert json.loads(self._first_json_object('Thinking... {"a": 1}')) == {"a": 1}

    def test_raises_when_no_object_present(self):
        with pytest.raises(ValueError):
            self._first_json_object("there is no json here")

    def test_skips_a_malformed_candidate_and_takes_a_later_valid_one(self):
        text = "{not valid json} but here is the real one: {\"ok\": true}"
        assert json.loads(self._first_json_object(text)) == {"ok": True}

class TestRealImplementation:
    """Exercise the helper that ships in app.agent.query_intelligence."""

    @staticmethod
    def _helper():
        from app.agent.query_intelligence import _first_json_object

        return _first_json_object

    def test_two_objects_in_one_response(self):
        import json

        helper = self._helper()
        assert json.loads(helper('{"a": 1} and also {"b": 2}')) == {"a": 1}

    def test_nested_object(self):
        import json

        helper = self._helper()
        payload = '{"analysis_type": "NDVI", "params": {"threshold": 0.3}}'
        assert json.loads(helper(payload))["params"]["threshold"] == 0.3

    def test_brace_inside_string(self):
        import json

        helper = self._helper()
        assert json.loads(helper('{"note": "use {braces}", "v": 1}'))["v"] == 1

    def test_raises_without_json(self):
        import pytest

        helper = self._helper()
        with pytest.raises(ValueError):
            helper("no braces at all")
