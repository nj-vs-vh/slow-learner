import random
import string
from typing import Any

import pytest
from pytest import param

from slow_learner import TypeLearner
from slow_learner.learnt_types import LearntType, LLiteral, LNone, LTuple, LType, LUnion


@pytest.mark.parametrize(
    "stream, expected_learnt_type, order_independent",
    [
        # literals and simple types
        param([1, 2, 3], LUnion([LLiteral(1), LLiteral(2), LLiteral(3)]), True),
        param(list(range(100)), LType(int), True),
        param(list(range(100)) + [None], LUnion([LType(int), LNone()]), True, id="None is not absorbed into literal"),
        param(["a", *range(100)], LUnion([LType(int), LType(str)]), False),
        param([*range(100), "a"], LUnion([LType(int), LLiteral("a")]), False),
        param([*range(100), *string.ascii_letters], LUnion([LType(int), LType(str)]), True),
        # tuples
        param([(1, "a")], LTuple([LLiteral(1), LLiteral("a")]), True),
        param(
            [(1, "a"), (2, "b")],
            LTuple([LUnion([LLiteral(1), LLiteral(2)]), LUnion([LLiteral("a"), LLiteral("b")])]),
            True,
        ),
        param(
            [(number, letter) for number, letter in zip(range(100), string.ascii_letters)],
            LTuple([LType(int), LType(str)]),
            True,
        ),
        param(
            [(1, letter) for letter in string.ascii_letters],
            LTuple([LLiteral(value=1), LType(str)]),
            True,
        ),
        param(
            [
                *range(10),
                *[(number, letter) for number, letter in zip(range(100), string.ascii_letters)],
                *[(1, 2, letter) for letter in string.ascii_letters],
            ],
            LUnion([LType(int), LTuple([LType(int), LType(str)]), LTuple([LLiteral(1), LLiteral(2), LType(str)])]),
            True,
        ),
        param(),
    ],
)
def test_type_learner(stream: list[Any], expected_learnt_type: LearntType, order_independent: bool):
    random.seed(1312)
    for _ in range(5):
        tl = TypeLearner(max_literal_type_size=5)
        for value in stream:
            tl.observe(value)
        assert tl.learnt_type == expected_learnt_type

        if not order_independent:
            break

        random.shuffle(stream)
