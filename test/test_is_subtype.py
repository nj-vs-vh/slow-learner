import pytest

from slow_learner.learnt_types import LearntType, LLiteral, LType, LTuple, LUnion
from slow_learner.subtyping import is_subtype


class CustomStr(str):
    pass


class CustomInt(int):
    pass


class CustomBase:
    pass


class CustomSub(CustomBase):
    pass


@pytest.mark.parametrize(
    "lt1, lt2, expected_result",
    [
        pytest.param(LType(CustomStr), LType(str), True),
        pytest.param(LType(int), LLiteral(1312), False),
        pytest.param(LType(int), LType(float), False),
        pytest.param(LLiteral("hello"), LType(str), True),
        pytest.param(LType(str), LUnion([LType(str), LType(int)]), True),
        pytest.param(
            LTuple([LType(CustomStr), LType(CustomInt), LLiteral('foo')]),
            LTuple([LType(str), LType(int), LLiteral('foo')]),
            True,
        ),
        pytest.param(
            LTuple([LType(CustomStr), LType(CustomInt), LLiteral('foo')]),
            LTuple([LType(str), LType(float), LLiteral('foo')]),
            False,
        ),
        pytest.param(
            LTuple([LType(CustomStr), LType(CustomInt), LLiteral('foo')]),
            LTuple([LType(str), LType(int), LLiteral('bar')]),
            False,
        ),
        pytest.param(
            LTuple([LType(CustomStr), LType(CustomInt), LLiteral('foo')]),
            LTuple([LType(str), LType(int)]),
            False,
        ),
    ],
)
def test_is_subtype(lt1: LearntType, lt2: LearntType, expected_result: bool):
    assert is_subtype(lt1, lt2) == expected_result
