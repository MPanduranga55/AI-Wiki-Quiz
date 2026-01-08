from langchain_core.prompts import PromptTemplate  # type: ignore

# Prompt to extract structured info (title, summary, entities, sections).
QUIZ_ANALYSIS_PROMPT = PromptTemplate(
    input_variables=["article_text"],
    template=(
        "You are an assistant that analyzes Wikipedia articles to extract structured data.\n"
        "Given the article text below (which may be truncated), extract the following as JSON:\n"
        "1. title: Short article title.\n"
        "2. summary: 2-4 sentence overview.\n"
        "3. key_entities: with keys 'people', 'organizations', 'locations' as arrays of strings.\n"
        "4. sections: ordered list of major section titles.\n\n"
        "Return ONLY valid JSON with keys: title, summary, key_entities, sections.\n\n"
        "Article text:\n"
        "{article_text}\n"
    ),
)

# Prompt to create multiple-choice quiz questions.
QUIZ_GENERATION_PROMPT = PromptTemplate(
    input_variables=["article_text"],
    template=(
        "You are a quiz generator for Wikipedia articles.\n"
        "Using ONLY the factual content from the article text below, create a diverse quiz\n"
        "of 5 to 10 multiple-choice questions.\n\n"
        "For each question, output an object with keys:\n"
        " - question: the question text\n"
        " - options: an array of 4 answer options (strings)\n"
        " - answer: the exact text of the correct option\n"
        " - explanation: 1-2 sentence explanation grounded in the article\n"
        " - difficulty: one of 'easy', 'medium', 'hard'\n\n"
        "Avoid hallucinations and do not use information that is not clearly supported by the text.\n"
        "Return ONLY a JSON array of question objects.\n\n"
        "Article text:\n"
        "{article_text}\n"
    ),
)

# Prompt to suggest related Wikipedia topics.
RELATED_TOPICS_PROMPT = PromptTemplate(
    input_variables=["article_text"],
    template=(
        "You are an assistant that suggests follow-up Wikipedia topics.\n"
        "Based on the article text below, suggest 5 to 8 related Wikipedia article topics\n"
        "that a learner should read next.\n\n"
        "Return ONLY a JSON array of strings, each string being a Wikipedia topic title.\n\n"
        "Article text:\n"
        "{article_text}\n"
    ),
)


