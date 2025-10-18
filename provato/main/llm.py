import os
import json
from typing import Dict
from openai import OpenAI

SYSTEM_PROMPT = (
    "You are an intelligent farm assistant. "
    "Chat naturally with the user, but when the question is factual or about sheep, farms, or related data, "
    "use the provided database context to answer accurately. "
    "If the database lacks detail, answer generally and mark it as general knowledge."
)

# --- OpenAI configuration ---
openai_api_key = os.getenv('OPENAI_API_KEY')
openai_base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
openai_model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

client = OpenAI(api_key=openai_api_key, base_url=openai_base_url)


def _openai_generate(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print("OpenAI generate failed:", e)
        return "I do not have enough information."


def call_llm(question: str, context_text: str, history=None) -> Dict[str, str]:
    history_block = "\n".join(f"{m['role']}: {m['content']}" for m in (history or [])[-8:])
    prompt = (
        f"System: {SYSTEM_PROMPT}\n\n"
        f"You must answer **only** using the provided Neo4j context. "
        f"If the answer is not explicitly present there, respond exactly: "
        f"'I do not have enough information in the database.' "
        f"Do not use general knowledge or assumptions.\n\n"
        f"Context (from Neo4j):\n{context_text or '(none)'}\n\n"
        f"Conversation so far:\n{history_block}\n\n"
        f"User question:\n{question}\n\n"
        f"Answer:"
    )

    answer = _openai_generate(prompt)
    return {"answer": answer, "source": "openai"}


def extract_search_plan(question: str) -> dict:
    prompt = (
        "Translate this natural language question into a Cypher query for a Neo4j graph "
        "with nodes: Animal, Farm, Device, MeteoData. "
        "Use English property names (id, name, breed, sex, type, coordinates, etc.). "
        "If it is a general animal question, return a MATCH for all Animal nodes. "
        "Output only the Cypher query text, nothing else.\n\n"
        f"Question: {question}"
    )
    cypher = _openai_generate(prompt)
    return {"cypher": cypher.strip()}
