# Copyright 2026 CVS Health and/or one of its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.

"""Tests for BIRD stratified sampling across databases."""

from benchmarks.bird.setup_data import (
    BIRDQuestion,
    _compute_stratified_quotas,
    stratified_sample_questions,
)


def _make_questions(counts: dict) -> list:
    """Build synthetic questions: db_a x3, db_b x2, etc."""
    out = []
    qid = 0
    for db_id, n in sorted(counts.items()):
        for _ in range(n):
            out.append(
                BIRDQuestion(
                    question_id=qid,
                    db_id=db_id,
                    question=f"q{qid}",
                    evidence="",
                    gold_sql="SELECT 1",
                    difficulty="simple",
                )
            )
            qid += 1
    return out


def test_compute_stratified_quotas_sums_to_n():
    counts = {"a": 30, "b": 20, "c": 50}
    q = _compute_stratified_quotas(counts, 25)
    assert sum(q.values()) == 25
    assert q["a"] <= 30 and q["b"] <= 20 and q["c"] <= 50


def test_compute_stratified_quotas_full_pool():
    counts = {"x": 5, "y": 5}
    q = _compute_stratified_quotas(counts, 100)
    assert q == counts


def test_stratified_sample_questions_size_and_determinism():
    counts = {"db_a": 40, "db_b": 35, "db_c": 25}
    pool = _make_questions(counts)
    s1, alloc1 = stratified_sample_questions(pool, 100, seed=7)
    s2, alloc2 = stratified_sample_questions(pool, 100, seed=7)
    assert len(s1) == 100
    assert alloc1 == alloc2
    assert [q.question_id for q in s1] == [q.question_id for q in s2]


def test_stratified_sample_proportional_approximation():
    """100 from 10+20+70 -> expect ~10, ~20, ~70."""
    pool = _make_questions({"small": 10, "med": 20, "large": 70})
    _, alloc = stratified_sample_questions(pool, 100, seed=0)
    assert sum(alloc.values()) == 100
    assert alloc.get("small", 0) == 10
    assert alloc.get("med", 0) == 20
    assert alloc.get("large", 0) == 70
