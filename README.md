## DeepKlarity Technologies – AI Wiki Quiz Generator

Minimal implementation of the assignment: a FastAPI backend that scrapes Wikipedia
HTML, uses Gemini via LangChain to generate a quiz, persists data in SQL, and a
lightweight frontend UI (single HTML file) with two tabs.

### Tech stack

- **Backend**: FastAPI (Python)
- **Database**: MySQL only (via SQLAlchemy, required)
- **Frontend**: Static HTML + vanilla JS (no Node.js backend)
- **LLM**: Google Gemini (`gemini-1.5-flash`) via `langchain-google-genai`
- **Scraping**: `requests` + `BeautifulSoup4`

### Project layout

- `backend/app/main.py` – FastAPI app, endpoints
- `backend/app/database.py` – SQLAlchemy engine and session
- `backend/app/models.py` – `QuizRecord` table
- `backend/app/crud.py` – DB helpers and serializers
- `backend/app/scraping.py` – Wikipedia HTML fetch + extraction
- `backend/app/prompts.py` – LangChain `PromptTemplate`s (quiz + related topics)
- `backend/app/llm.py` – Gemini integration + JSON parsing helpers
- `backend/requirements.txt` – Python dependencies
- `frontend/index.html` – UI with:
  - **Tab 1**: Generate quiz
  - **Tab 2**: Past quizzes (history) + details modal
  - Optional **Take quiz** mode
- `sample_data/` – Place saved JSON responses here for submission

### Environment variables

Create a `.env` or export these before running the backend:

- `GOOGLE_API_KEY` – your Gemini API key
- `DATABASE_URL` – **MySQL only (required)**, format:
  - `mysql+pymysql://user:password@host:3306/ai_quiz`

### Backend – install and run locally

From the project root:

```bash
cd backend
python -m venv venv
venv\Scripts\activate  # on Windows
pip install -r requirements.txt

set GOOGLE_API_KEY=YOUR_KEY_HERE   # or via .env
set DATABASE_URL=mysql+pymysql://user:pass@localhost:3306/ai_quiz

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Key endpoints:

- `POST /api/quizzes/generate`
  - Body: `{ "url": "https://en.wikipedia.org/wiki/Alan_Turing" }`
  - Behavior:
    - Scrapes HTML (no Wikipedia API)
    - Extracts clean text with BeautifulSoup
    - Calls Gemini via LangChain with the prompt templates
    - Stores record in SQL database (including raw HTML)
    - Returns JSON in the target structure (id, url, title, summary, entities, sections, quiz, related_topics)
    - Caches per-URL: if the URL already exists, returns the stored quiz instead of regenerating
- `GET /api/quizzes` – list history (id, url, truncated summary, created_at)
- `GET /api/quizzes/{id}` – full quiz payload

### Frontend – run locally

You can serve `frontend/index.html` directly (e.g. by opening in the browser) while the
backend runs on `http://localhost:8000`.

- Tab **“Generate quiz”**:
  - Paste a Wikipedia article URL
  - Click **Generate quiz**
  - Shows article title, URL, summary, sections, extracted entities, quiz questions, and related topics
  - **Take quiz mode**: toggle hides the correct answers, lets the user type A–D, and shows a score
- Tab **“Past quizzes”**:
  - Table listing previous URLs with title, URL, summary snippet, timestamp
  - **Details** button opens a modal reusing the same structured layout as Tab 1

### Sample data

Populate `sample_data/` by saving responses from `/api/quizzes/generate`, for example:

- `sample_data/alan_turing.json`
- `sample_data/artificial_intelligence.json`

These should mirror the sample structure from the assignment:

```json
{
  "id": 1,
  "url": "https://en.wikipedia.org/wiki/Alan_Turing",
  "title": "Alan Turing",
  "summary": "Alan Turing was a British mathematician and computer scientist...",
  "key_entities": { "people": ["Alan Turing"], "organizations": [], "locations": [] },
  "sections": ["Early life", "World War II", "Legacy"],
  "quiz": [
    {
      "question": "Where did Alan Turing study?",
      "options": ["Harvard University", "Cambridge University", "Oxford University", "Princeton University"],
      "answer": "Cambridge University",
      "difficulty": "easy",
      "explanation": "Mentioned in the 'Early life' section."
    }
  ],
  "related_topics": ["Cryptography", "Enigma machine"]
}
```

### Prompt templates (LangChain)

Implemented in `backend/app/prompts.py`:

- **Article analysis** (`QUIZ_ANALYSIS_PROMPT`):
  - Extracts `title`, `summary`, `key_entities` (`people`, `organizations`, `locations`), and `sections` as structured JSON, grounded in the article text.
- **Quiz generation** (`QUIZ_GENERATION_PROMPT`):
  - Produces 5–10 MCQs with `question`, 4 `options`, `answer`, `explanation`, and `difficulty` (easy/medium/hard).
  - Explicitly instructs the model to avoid hallucinations and stay within the article text.
- **Related topics** (`RELATED_TOPICS_PROMPT`):
  - Returns a JSON array of 5–8 related Wikipedia topics (titles only).

These prompts are wired into Gemini via `backend/app/llm.py`, and all outputs are post-processed
to ensure valid JSON before being stored and served.

### Testing & screenshots

For the assignment submission:

- Start the backend (`uvicorn app.main:app --reload`)
- Open `frontend/index.html` in a browser
- Test multiple URLs (e.g. Alan Turing, Artificial intelligence)
- Save responses into `sample_data/`
- Capture screenshots of:
  - Tab 1 (Generate quiz view with a populated quiz)
  - Tab 2 (History table)
  - The details modal for a past quiz


