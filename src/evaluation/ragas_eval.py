"""RAGAS evaluation scaffold."""

from __future__ import annotations

from typing import List, Dict
from loguru import logger

from ragas import evaluate
from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall


def run_ragas(dataset: List[Dict]) -> Dict[str, float]:
    """Run RAGAS over a list of records: {question, answer, contexts}.

    contexts: list of strings used by the agent.
    Returns metric scores.
    """
    if not dataset:
        return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0, "context_recall": 0.0}
    try:
        result = evaluate(
            dataset,
            metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        )
        scores = result.to_pandas().mean(numeric_only=True).to_dict()
        return {k: float(v) for k, v in scores.items()}
    except Exception as e:
        logger.error(f"RAGAS evaluation failed: {e}")
        return {"faithfulness": 0.0, "answer_relevancy": 0.0, "context_precision": 0.0, "context_recall": 0.0}


