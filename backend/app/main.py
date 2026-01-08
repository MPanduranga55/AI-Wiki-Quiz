import dotenv
from fastapi import FastAPI, HTTPException  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from pydantic import BaseModel, HttpUrl
from typing import List

from .database import Base, engine, get_session
from . import models, crud, scraping, llm


class GenerateQuizRequest(BaseModel):
    """Request body for generating a quiz from a Wikipedia URL."""

    url: HttpUrl


app = FastAPI(title="AI Wiki Quiz Generator")

# Load environment variables from a .env file if present (for DATABASE_URL, GOOGLE_API_KEY)
dotenv.load_dotenv()

# Allow browser clients (frontend) to call the API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    """Create database tables on startup if they do not exist."""
    Base.metadata.create_all(bind=engine)


@app.post("/api/quizzes/generate")
def generate_quiz(payload: GenerateQuizRequest):
    """Scrape, generate quiz with LLM, store it, and return the result."""
    with get_session() as session:
        url = str(payload.url)

        # Cache hit: return existing quiz for this URL
        existing = crud.get_quiz_by_url(session, url)
        if existing:
            return crud.quiz_to_dict(existing)

        # 1) Scrape article
        try:
            html, text = scraping.fetch_and_extract(url)
            # Validate that we actually got text content
            if not text or len(text.strip()) < 100:
                raise ValueError(
                    f"Scraped text is too short ({len(text) if text else 0} chars). "
                    "Wikipedia page may be empty or scraping failed."
                )
        except Exception as e:
            raise HTTPException(status_code=400, detail=f"Failed to fetch article: {e}")

        # 2) LLM analysis + quiz generation
        try:
            analysis = llm.analyze_article(text)
            quiz_items = llm.generate_quiz(text)
            related_topics = llm.generate_related_topics(text)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"LLM generation failed: {e}")

        # Ensure we have 10 questions: synthesize simple fallback questions if LLM returned fewer
        if not isinstance(quiz_items, list):
            quiz_items = []
        if len(quiz_items) < 10:
            try:
                pool = []
                sections = analysis.get("sections") if isinstance(analysis, dict) else []
                if isinstance(sections, list):
                    pool.extend(sections)
                pool.extend(related_topics or [])
                ke = analysis.get("key_entities") if isinstance(analysis, dict) else {}
                for k in ("people", "organizations", "locations"):
                    if isinstance(ke.get(k), list):
                        pool.extend(ke.get(k))
                # fall back to summary sentences
                summary = analysis.get("summary") if isinstance(analysis, dict) else ""
                pool.extend([s.strip() for s in summary.split('.') if s.strip()])
                # dedupe and filter short
                pool = [p for p in dict.fromkeys(pool) if p and len(p) > 3]
                import random
                random.shuffle(pool)
                i = 0
                while len(quiz_items) < 10 and i < len(pool):
                    correct = pool[i]
                    # choose distractors
                    distractors = [d for d in pool if d != correct]
                    random.shuffle(distractors)
                    opts = [correct] + distractors[:3]
                    if len(opts) < 4:
                        i += 1
                        continue
                    random.shuffle(opts)
                    quiz_items.append({
                        "question": "Which of the following is mentioned in the article?",
                        "options": opts,
                        "answer": correct,
                        "explanation": f"Mentioned in article: {correct[:120]}",
                        "difficulty": "medium",
                    })
                    i += 1
            except Exception:
                pass

        # 3) Store in DB and return
        quiz_record = crud.create_quiz(
            session=session,
            url=url,
            raw_html=html,
            analysis=analysis,
            quiz_items=quiz_items,
            related_topics=related_topics,
        )
        return crud.quiz_to_dict(quiz_record)


@app.get("/api/quizzes")
def list_quizzes():
    """Return summaries of all stored quizzes (for history tab)."""
    with get_session() as session:
        quizzes = crud.list_quizzes(session)
        return [crud.quiz_summary_to_dict(q) for q in quizzes]


@app.get("/api/quizzes/{quiz_id}")
def get_quiz(quiz_id: int):
    """Return a single quiz by ID."""
    with get_session() as session:
        quiz = crud.get_quiz_by_id(session, quiz_id)
        if not quiz:
            raise HTTPException(status_code=404, detail="Quiz not found")
        return crud.quiz_to_dict(quiz)


