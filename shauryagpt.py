"""
ShauryaGPT — RAG-lite persona bot for Anvi.

Retrieval: embeds Anvi's new message with the same TF-IDF vectorizer
used to build the index, finds the k most similar past situations
(by preceding-context similarity), and pulls YOUR real reply from
each as a few-shot example.

Generation: sends those examples + recent live conversation + Anvi's
new message to Claude Haiku 4.5, instructed to reply the way you would.

Usage:
    python3 shauryagpt.py                # interactive terminal chat
    from shauryagpt import reply         # or import and call reply() from a server
"""

import json
import os
import pickle

import numpy as np
from scipy import sparse
from sklearn.metrics.pairwise import cosine_similarity
from anthropic import Anthropic

from usage_tracker import UsageTracker

MODEL = "claude-haiku-4-5-20251001"
TOP_K = 6
RECENCY_HALFLIFE_DAYS = 120  # blend similarity with recency so tone reflects how you talk *now*

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
        self.client = Anthropic()  # reads ANTHROPIC_API_KEY from env
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

        messages = list(recent_history or [])
        messages.append({"role": "user", "content": anvi_message})

        resp = self.client.messages.create(
            model=MODEL,
            max_tokens=300,
            system=system,
            messages=messages,
        )
        self.usage.record_message(user_id)
        return resp.content[0].text

    def remaining_today(self, user_id: str = "anvi"):
        """None means unlimited (premium)."""
        return self.usage.remaining(user_id)


def main():
    bot = ShauryaGPT()
    print("ShauryaGPT ready. Type as Anvi. Ctrl+C to quit.\n")
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
