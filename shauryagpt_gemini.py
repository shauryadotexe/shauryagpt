"""
ShauryaGPT — RAG-lite persona bot for Anvi. (Gemini API version)

Same retrieval logic as the Claude version (shauryagpt.py) — only the
generation call is swapped to Google's Gemini API, so this can run on
the Google AI Studio free tier instead of needing paid Anthropic credit.

Get a free key: https://aistudio.google.com/apikey (no card needed)

Usage:
    export GEMINI_API_KEY=your_key_here
    python3 shauryagpt_gemini.py                # interactive terminal chat
"""

import json
import os
import pickle

import numpy as np
from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity
from google import genai
from google.genai import types

from usage_tracker import UsageTracker

MODEL = "gemini-2.5-flash"  # free-tier eligible; swap to gemini-2.5-flash-lite for higher free RPD if needed
TOP_K = 6

LIMIT_REACHED_REPLY = "out of texts for today, hmu tomorrow 💀"

SYSTEM_PROMPT = """You are texting as Shaurya — replying to Anvi over WhatsApp.
You are NOT an assistant. You are not helpful, formal, or verbose by default.
Match Shaurya's real texting style shown in the examples below: message length,
punctuation habits, use of Hindi/English mixing, tone, emoji use (or lack of it).
Reply the way Shaurya actually would — short if he'd be short, blunt if he'd be
blunt, warm if he'd be warm. Do not narrate or add stage directions. Just the
message text, nothing else.

Examples of real situations and how Shaurya actually replied (most relevant first):
{examples}
"""


class ShauryaGPT:
    def __init__(self, index_dir="."):
        with open(os.path.join(index_dir, "chat_index.json"), "r", encoding="utf-8") as f:
            self.chunks = json.load(f)
        self.vectors = sparse.load_npz(os.path.join(index_dir, "chat_index.npz"))
        with open(os.path.join(index_dir, "chat_vectorizer.pkl"), "rb") as f:
            self.vectorizer = pickle.load(f)
        self.client = genai.Client()  # reads GEMINI_API_KEY from env
        self.usage = UsageTracker()

    def retrieve(self, query: str, k: int = TOP_K):
        q_vec = self.vectorizer.transform([query])
        sims = cosine_similarity(q_vec, self.vectors).flatten()
        top_idx = np.argsort(-sims)[: k * 3]  # overfetch, then dedupe by reply text
        seen_replies = set()
        results = []
        for i in top_idx:
            chunk = self.chunks[i]
            if chunk["reply"] in seen_replies:
                continue
            seen_replies.add(chunk["reply"])
            results.append((sims[i], chunk))
            if len(results) >= k:
                break
        return results

    def format_examples(self, retrieved):
        lines = []
        for sim, chunk in retrieved:
            ctx = " / ".join(chunk["context"]) if chunk["context"] else "(no preceding message)"
            lines.append(f'- Anvi said (or the situation was): "{ctx}"\n  Shaurya replied: "{chunk["reply"]}"')
        return "\n".join(lines)

    def reply(self, anvi_message: str, recent_history: list[dict] | None = None, user_id: str = "anvi") -> str:
        """
        anvi_message: Anvi's latest message text
        recent_history: optional list of {"role": "user"|"assistant", "content": str}
                         for the live in-progress conversation (last few turns)
        user_id: identifies who's texting, for the free/premium usage cap
        """
        if not self.usage.can_send(user_id):
            return LIMIT_REACHED_REPLY

        retrieved = self.retrieve(anvi_message)
        examples_text = self.format_examples(retrieved)
        system = SYSTEM_PROMPT.format(examples=examples_text)

        # Gemini uses role "model" instead of "assistant", and wraps text
        # in a "parts" list rather than a plain string.
        contents = []
        for msg in recent_history or []:
            role = "model" if msg["role"] == "assistant" else "user"
            contents.append(types.Content(role=role, parts=[types.Part(text=msg["content"])]))
        contents.append(types.Content(role="user", parts=[types.Part(text=anvi_message)]))

        resp = self.client.models.generate_content(
            model=MODEL,
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system,
                max_output_tokens=300,
            ),
        )
        self.usage.record_message(user_id)
        return resp.text

    def remaining_today(self, user_id: str = "anvi"):
        """None means unlimited (premium)."""
        return self.usage.remaining(user_id)


def main():
    bot = ShauryaGPT()
    print("ShauryaGPT ready (Gemini). Type as Anvi. Ctrl+C to quit.\n")
    history = []
    while True:
        try:
            user_msg = input("Anvi: ")
        except (EOFError, KeyboardInterrupt):
            break
        reply = bot.reply(user_msg, recent_history=history)
        print(f"Shaurya: {reply}")
        remaining = bot.remaining_today()
        if remaining is not None:
            print(f"  ({remaining} free messages left today)\n")
        else:
            print()
        history.append({"role": "user", "content": user_msg})
        history.append({"role": "assistant", "content": reply})
        history = history[-12:]  # keep last ~6 turns


if __name__ == "__main__":
    main()
