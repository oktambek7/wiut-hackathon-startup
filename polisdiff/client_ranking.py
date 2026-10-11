"""Hybrid retrieval where the semantic half runs in the visitor's browser.

The web app embeds the document passages and the rule queries with multilingual E5
(transformers.js, same model family as the offline app) and sends, per rule, the passage ids
it ranked highest. The server fuses those ranks with its own keyword ranks exactly like the
local hybrid retriever (reciprocal rank fusion). Unknown ids are ignored; a missing or
malformed ranking falls back to keyword search with a visible warning.
"""
from .retrieval import Retriever, lexical_scores
from .service import EXTRA_QUERIES

MAX_IDS_PER_RULE = 40


def rule_queries(rules) -> dict[str, list[str]]:
    return {r.id: r.queries + EXTRA_QUERIES.get(r.id, []) for r in rules}


class ClientRankedRetriever(Retriever):
    def __init__(self, mode: str, rankings: dict, rules, model_label: str):
        super().__init__("lexical")
        self.requested = mode
        self.used = mode
        self.model_revision = model_label
        self._by_queries = {tuple(q): rid for rid, q in rule_queries(rules).items()}
        self._ranks = {rid: {pid: i for i, pid in enumerate(ids[:MAX_IDS_PER_RULE])}
                       for rid, ids in rankings.items() if isinstance(ids, list)}

    def validate(self, passage_ids: set[str]):
        """All ranked ids must exist in this document, otherwise the ranking was made for another file."""
        known = {pid for ranks in self._ranks.values() for pid in ranks}
        if not self._ranks or not known or not known <= passage_ids:
            self._ranks = {}
            self.used = "lexical"
            self.model_revision = None
            self.warning = "Semantic retrieval unavailable (BrowserRankingInvalid); lexical fallback used."

    def search(self, queries, k=5):
        if not self._passages:
            return []
        lexical = lexical_scores(self._passages, queries)
        ranks = self._ranks.get(self._by_queries.get(tuple(queries)), {})
        if self.used == "lexical" or not ranks:
            scores = lexical
        else:
            # Ranks are global across the document; keep this section's order.
            semantic = sorted((ranks[p.id], i) for i, p in enumerate(self._passages) if p.id in ranks)
            scores = [0.0] * len(self._passages)
            for rank, (_, idx) in enumerate(semantic):
                scores[idx] += 1 / (60 + rank + 1)
            if self.used == "hybrid":
                order = sorted(range(len(lexical)), key=lambda i: lexical[i], reverse=True)
                for rank, idx in enumerate(order):
                    if lexical[idx] > 0:
                        scores[idx] += 1 / (60 + rank + 1)
        indices = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:k]
        return [(self._passages[i], float(scores[i])) for i in indices if scores[i] > 0]
