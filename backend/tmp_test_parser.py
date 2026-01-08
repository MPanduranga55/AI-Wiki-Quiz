import json
import re
from typing import Any, List


def _safe_json_parse(text: str) -> Any:
    if not text or not text.strip():
        raise ValueError("LLM returned empty response. Check your API key and model name.")
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()
    if not text:
        raise ValueError("LLM response was empty after cleaning. Check your API key and model name.")

    for marker in ("\nError:", "\nTraceback", "\nException:", "Error:", "Traceback (most recent call last)"):
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx].strip()

    first_curly = text.find("{") if "{" in text else -1
    first_brack = text.find("[") if "[" in text else -1
    if first_curly == -1 and first_brack == -1:
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            raise ValueError(f"Failed to find JSON object/array in LLM response. Response start: {text[:200]}... Error: {e}")

    if first_curly == -1:
        start = first_brack
    elif first_brack == -1:
        start = first_curly
    else:
        start = min(first_curly, first_brack)

    stack: List[str] = []
    in_string = False
    string_char = ""
    escape = False
    end = None
    for i, ch in enumerate(text[start:], start):
        if escape:
            escape = False
            continue
        if ch == "\\" and in_string:
            escape = True
            continue
        if ch in ('"', "'"):
            if not in_string:
                in_string = True
                string_char = ch
            elif ch == string_char:
                in_string = False
            continue
        if in_string:
            continue
        if ch == '{' or ch == '[':
            stack.append(ch)
        elif ch == '}' or ch == ']':
            if not stack:
                continue
            open_ch = stack.pop()
            if not stack:
                end = i
                break

    if end is None:
        closers = []
        for open_ch in reversed(stack):
            closers.append('}' if open_ch == '{' else ']')
        candidate = text[start:] + ''.join(closers)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            last_curly = text.rfind('}')
            last_brack = text.rfind(']')
            last = max(last_curly, last_brack)
            if last > -1 and last > start:
                candidate = text[start:last+1]
                try:
                    return json.loads(candidate)
                except json.JSONDecodeError as e:
                    raise ValueError(f"Failed to parse JSON from LLM response after attempts. Response snippet: {text[start:start+400]}... Error: {e}")
            raise ValueError(f"Failed to parse JSON from LLM response. Response snippet: {text[start:start+200]}...")

    candidate = text[start:end+1].strip()
    try:
        return json.loads(candidate)
    except json.JSONDecodeError as e:
        cleaned = re.sub(r',(\s*[}\]])', r'\1', candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e2:
            raise ValueError(f"Failed to parse JSON from LLM response. Response was: {candidate[:400]}... Error: {e2}")


if __name__ == '__main__':
    tests = [
        # valid JSON with trailing error text
        '{"title": "History of India", "summary": "A long summary."} Error: Unterminated string starting at',
        # valid JSON wrapped in code fences
        '```json\n{"title": "Foo", "items": [1,2,3]}\n```\n',
        # truncated JSON missing final brace
        '{"title": "Truncated", "summary": "This is incomplete...',
        # JSON with trailing commas
        '{"a": 1, "b": 2,}',
    ]

    for i, t in enumerate(tests, 1):
        print(f"--- Test {i} ---")
        try:
            r = _safe_json_parse(t)
            print("Parsed:", r)
        except Exception as e:
            print("Error:", e)
