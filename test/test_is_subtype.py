import pytest

from slow_learner.learnt_types import LearntType, LLiteral, LTuple, LType, LUnion
from slow_learner.subtyping import is_subtype


class CustomStr(str):
    pass


class CustomInt(int):
    pass


class CustomBase:
    pass


class CustomSub1(CustomBase):
    pass


class CustomSub2(CustomBase):
    pass


@pytest.mark.parametrize(
    "lt1, lt2, expected_result",
    [
        # simple types and literals
        pytest.param(LType(CustomStr), LType(str), True, id="subclass => is subtype"),
        pytest.param(LType(int), LLiteral(1312), False),
        pytest.param(LType(int), LType(float), False),
        pytest.param(LLiteral("hello"), LType(str), True, id="literal instance => is subtype"),
        # tuples
        pytest.param(
            LTuple([LType(CustomStr), LType(CustomInt), LLiteral("foo")]),
            LTuple([LType(str), LType(int), LLiteral("foo")]),
            True,
        ),
        pytest.param(
            LTuple([LType(CustomStr), LType(CustomInt), LLiteral("foo")]),
            LTuple([LType(str), LType(float), LLiteral("foo")]),
            False,
        ),
        pytest.param(
            LTuple([LType(CustomStr), LType(CustomInt), LLiteral("foo")]),
            LTuple([LType(str), LType(int), LLiteral("bar")]),
            False,
        ),
        pytest.param(
            LTuple([LType(CustomStr), LType(CustomInt), LLiteral("foo")]),
            LTuple([LType(str), LType(int)]),
            False,
        ),
        pytest.param(
            LTuple([LLiteral(1), LLiteral(3), LLiteral(True), LLiteral('2')]),
            LTuple([LType(int), LType(int), LType(bool), LType(str)]),
            True,
            id="tuple of literals is a subtype of tuple of their types",
        ),
        # unions
        pytest.param(LType(str), LUnion([LType(str), LType(int)]), True, id="simple type is a union member => subtype"),
        pytest.param(LUnion([LType(str), LType(int)]), LType(int), False),
        pytest.param(
            LTuple([LType(str), LType(int)]),
            LUnion([LType(str), LTuple([LType(str), LType(int)])]),
            True,
            id="tuple type is a union member => subtype",
        ),
        pytest.param(
            LType(CustomSub1),
            LUnion([LType(int), LType(CustomBase)]),
            True,
            id="simple type is a subtype of one of union's members",
        ),
        pytest.param(
            LUnion([LType(str), LType(bytes)]),
            LUnion([LType(int), LType(str), LType(bytes)]),
            True,
            id="union's members are a subset of another union's members",
        ),
        pytest.param(
            LUnion([LType(CustomSub1), LType(CustomSub2)]),
            LType(CustomBase),
            True,
            id="union's members are all subtypes of a simple type",
        ),
    ],
)
def test_is_subtype(lt1: LearntType, lt2: LearntType, expected_result: bool):
    assert is_subtype(lt1, lt2) == expected_result
