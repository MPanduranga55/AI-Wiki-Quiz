import json
import os
from typing import Any, Dict, List
import time
import re
import logging

# Configure basic logging for this module
logging.basicConfig(level=logging.INFO)

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import PromptTemplate  # type: ignore

from .prompts import (
    QUIZ_ANALYSIS_PROMPT,
    QUIZ_GENERATION_PROMPT,
    RELATED_TOPICS_PROMPT,
)


def _get_model() -> ChatGoogleGenerativeAI:
    """Create the Gemini chat model with our preferred settings."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable is not set.")

    return ChatGoogleGenerativeAI(
        # Use the latest 1.5 flash model; plain "gemini-1.5-flash" may 404 on newer APIs
        model="gemini-2.5-flash",
        temperature=0.2,
        max_output_tokens=2048,
        google_api_key=api_key,
    )


def _invoke_chain_with_retries(chain, inputs: Dict[str, Any], max_retries: int = 3):
    """Invoke a LangChain chain with retries on rate-limit / quota errors.

    Returns the chain result object on success or raises the last exception.
    """
    last_exc = None
    for attempt in range(max_retries):
        try:
            return chain.invoke(inputs)
        except Exception as e:
            last_exc = e
            msg = str(e)
            # detect quota / rate limit errors
            if "RESOURCE_EXHAUSTED" in msg or "429" in msg or "quota" in msg.lower() or "rate limit" in msg.lower():
                # try to extract retry delay from message like 'Please retry in 56.73s' or 'retryDelay': '56s'
                m = re.search(r"retry in (\d+(?:\.\d+)?)s", msg)
                if m:
                    delay = float(m.group(1))
                else:
                    m2 = re.search(r"retryDelay\W*(\d+)s", msg)
                    delay = float(m2.group(1)) if m2 else (2 ** attempt) * 5
                time.sleep(min(delay, 120))
                continue
            # non-retryable error
            raise
    # exhausted retries
    raise last_exc


def _safe_json_parse(text: str) -> Any:
    """Parse JSON robustly from LLM output.

    This function attempts several heuristics:
    - strip markdown fences
    - remove trailing diagnostic text after common markers (Error, Traceback)
    - locate the first JSON object/array and extract a balanced chunk while ignoring strings
    - try simple repairs (append missing closing braces/brackets, remove trailing commas)

    Raises ValueError with a helpful message when parsing ultimately fails.
    """
    if not text or not text.strip():
        raise ValueError("LLM returned empty response. Check your API key and model name.")

    text = text.strip()

    # Remove markdown code fences if present
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    text = text.strip()

    if not text:
        raise ValueError("LLM response was empty after cleaning. Check your API key and model name.")

    # If a clean JSON parse works, return it immediately
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip common trailing diagnostic markers
    for marker in ("\nError:", "\nTraceback", "\nException:", "Error:", "Traceback (most recent call last)"):
        idx = text.find(marker)
        if idx != -1:
            text = text[:idx].strip()

    # Find the first JSON object/array start
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

    # Walk to find a balanced JSON (ignore characters inside strings)
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
        if ch in ('"', "\'"):
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
            stack.pop()
            if not stack:
                end = i
                break

    if end is None:
        # try to append missing closers
        closers = []
        for open_ch in reversed(stack):
            closers.append('}' if open_ch == '{' else ']')
        candidate = text[start:] + ''.join(closers)
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            # try to use last closing brace/bracket found in text
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
    except json.JSONDecodeError:
        # final attempt: remove trailing commas before closing braces/brackets
        import re
        cleaned = re.sub(r',(\s*[}\]])', r'\1', candidate)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e2:
            raise ValueError(f"Failed to parse JSON from LLM response. Candidate: {candidate[:400]}... Error: {e2}")


def _repair_with_model(broken_text: str, model: ChatGoogleGenerativeAI, prompt: PromptTemplate) -> str:
    """Ask the model to repair invalid JSON and return its content string."""
    chain = prompt | model
    repaired = chain.invoke({"broken_json": broken_text})
    if not repaired or not hasattr(repaired, "content") or not repaired.content:
        raise ValueError("Model did not return a repair response.")
    return repaired.content


REPAIR_QUIZ_PROMPT = PromptTemplate(
    input_variables=["broken_json"],
    template=(
        "The previous response was intended to be a JSON array of quiz question objects, but it was invalid.\n"
        "Each object must have keys: question (string), options (array of 4 strings), answer (string), explanation (string), difficulty (easy|medium|hard).\n"
        "Do NOT add any commentary — return ONLY the corrected JSON array. Here is the broken response:\n{broken_json}\n"
    ),
)


REPAIR_ANALYSIS_PROMPT = PromptTemplate(
    input_variables=["broken_json"],
    template=(
        "The previous response was intended to be a JSON object with keys: title (string), summary (string), key_entities (object with arrays: people, organizations, locations), sections (array of strings).\n"
        "Do NOT add any commentary — return ONLY the corrected JSON object. Here is the broken response:\n{broken_json}\n"
    ),
)


def analyze_article(article_text: str) -> Dict[str, Any]:
    """Run the analysis prompt to get title, summary, entities, sections."""
    if not article_text or not article_text.strip():
        raise ValueError("Article text is empty. Cannot analyze.")
    
    # Truncate to 8000 chars but ensure we have content
    text_to_send = article_text[:8000].strip()
    if len(text_to_send) < 100:
        raise ValueError(f"Article text is too short ({len(text_to_send)} chars). Need at least 100 characters.")
    
    model = _get_model()
    chain = QUIZ_ANALYSIS_PROMPT | model
    result = _invoke_chain_with_retries(chain, {"article_text": text_to_send})
    if not result or not hasattr(result, 'content') or not result.content:
        raise ValueError("LLM returned empty response. Check your API key and model name.")
    try:
        return _safe_json_parse(result.content)
    except Exception as e:
        # attempt to repair by asking the model to correct its JSON
        try:
            repaired = _repair_with_model(result.content, model, REPAIR_ANALYSIS_PROMPT)
            return _safe_json_parse(repaired)
        except Exception as repair_e:
            raise ValueError(f"Failed to parse and repair JSON from LLM response. Original error: {e}; Repair error: {repair_e}")


def generate_quiz(article_text: str) -> List[Dict[str, Any]]:
    """Run the quiz prompt to get a list of MCQ questions."""
    if not article_text or not article_text.strip():
        raise ValueError("Article text is empty. Cannot generate quiz.")
    
    # Truncate to 8000 chars but ensure we have content
    text_to_send = article_text[:8000].strip()
    if len(text_to_send) < 100:
        raise ValueError(f"Article text is too short ({len(text_to_send)} chars). Need at least 100 characters.")
    
    model = _get_model()
    chain = QUIZ_GENERATION_PROMPT | model
    result = _invoke_chain_with_retries(chain, {"article_text": text_to_send})
    if not result or not hasattr(result, "content") or not result.content:
        raise ValueError("LLM returned empty response. Check your API key and model name.")
    print("[LLM] Initial quiz response (truncated):", (result.content or '')[:1000])
    try:
        data = _safe_json_parse(result.content)
    except Exception as e:
        # attempt to repair via model
        try:
            repaired = _repair_with_model(result.content, model, REPAIR_QUIZ_PROMPT)
            data = _safe_json_parse(repaired)
        except Exception as repair_e:
            raise ValueError(f"Failed to parse and repair JSON from LLM response. Original error: {e}; Repair error: {repair_e}")
    if not isinstance(data, list):
        raise ValueError("Quiz generation result is not a list.")

    # If the model returned fewer than 10 questions, request the missing ones and merge.
    attempts = 0
    while len(data) < 10 and attempts < 3:
        needed = 10 - len(data)
        print(f"[LLM] Need {needed} more questions, attempt {attempts+1}")
        # Prompt to ask for additional questions
        MORE_QUESTIONS_PROMPT = PromptTemplate(
            input_variables=["article_text", "existing_json", "needed"],
            template=(
                "The previous response contained some quiz questions but was missing {needed} questions.\n"
                "Using ONLY the factual content from the article text below, provide exactly {needed} additional multiple-choice question objects (same schema as before).\n"
                "Do NOT repeat questions already present in the existing JSON. Return ONLY a JSON array of the additional question objects.\n\n"
                "Article text:\n{article_text}\n\nExisting questions JSON:\n{existing_json}\n"
            ),
        )

        more_chain = MORE_QUESTIONS_PROMPT | model
        existing_json = json.dumps(data, ensure_ascii=False)
        more_result = _invoke_chain_with_retries(more_chain, {"article_text": text_to_send, "existing_json": existing_json, "needed": str(needed)})
        if not more_result or not hasattr(more_result, "content") or not more_result.content:
            print("[LLM] More questions call returned empty content; stopping attempts")
            break
        try:
            print("[LLM] More questions response (truncated):", (more_result.content or '')[:1000])
            more = _safe_json_parse(more_result.content)
            if isinstance(more, list):
                # append unique questions by question text
                existing_qs = {q.get("question", ""): True for q in data}
                for q in more:
                    if not isinstance(q, dict):
                        continue
                    if q.get("question") in existing_qs:
                        continue
                    data.append(q)
                    existing_qs[q.get("question")] = True
                print(f"[LLM] Appended {len(more)} new questions, total now {len(data)}")
            else:
                # if parse returned a single object, ignore
                pass
        except Exception:
            import traceback
            print("[LLM] Failed parsing/repairing more questions; stopping attempts")
            traceback.print_exc()
            # if repair fails, stop attempting
            break
        attempts += 1

    # Trim to 10
    # If still short, synthesize fallback questions from article sections/related topics/entities
    if len(data) < 10:
        try:
            import random

            pool = []
            # prefer sections and related topics as correct answers
            pool.extend(text_to_send.split('\n'))
            # try to add related topics and sections if available via analysis (best-effort)
            # We'll attempt to extract simple lists using regex from the article text
            # fallback: use related topics prompt to get items (already available higher up in the flow),
            # but here we keep it simple to avoid extra LLM calls.
            # Build a small candidate set from sentences
            sentences = [s.strip() for s in text_to_send.split('.') if s.strip()]
            pool.extend(sentences)
            pool = [p for p in pool if len(p) > 3]
            random.shuffle(pool)
            i = 0
            while len(data) < 10 and i < len(pool):
                correct = pool[i]
                # choose distractors
                distractors = [d for d in pool if d != correct]
                random.shuffle(distractors)
                opts = [correct] + distractors[:3]
                random.shuffle(opts)
                qobj = {
                    "question": f"Which of the following is mentioned in the article?",
                    "options": opts,
                    "answer": correct,
                    "explanation": f"Mentioned in article: {correct[:120]}",
                    "difficulty": "medium",
                }
                data.append(qobj)
                i += 1
        except Exception:
            pass

    return data[:10]


def generate_related_topics(article_text: str) -> List[str]:
    """Run the related-topics prompt to get suggested Wikipedia topics."""
    if not article_text or not article_text.strip():
        raise ValueError("Article text is empty. Cannot generate related topics.")
    
    # Truncate to 8000 chars but ensure we have content
    text_to_send = article_text[:8000].strip()
    if len(text_to_send) < 100:
        raise ValueError(f"Article text is too short ({len(text_to_send)} chars). Need at least 100 characters.")
    
    model = _get_model()
    chain = RELATED_TOPICS_PROMPT | model
    result = _invoke_chain_with_retries(chain, {"article_text": text_to_send})
    if not result or not hasattr(result, 'content') or not result.content:
        raise ValueError("LLM returned empty response. Check your API key and model name.")
    data = _safe_json_parse(result.content)
    if not isinstance(data, list):
        raise ValueError("Related topics result is not a list.")
    return data


