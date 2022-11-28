import pytest

from slow_learner.learnt_types import LearntLiteralType, LearntSimpleType, LearntTupleType, LearntType, LearntUnionType
from slow_learner.subtyping import is_subtype


class CustomStr(str):
    pass


@pytest.mark.parametrize(
    "lt1, lt2, expected_result",
    [
        pytest.param(LearntSimpleType(CustomStr), LearntSimpleType(str), True),
        pytest.param(LearntSimpleType(int), LearntLiteralType(1312), False),
        pytest.param(LearntSimpleType(int), LearntSimpleType(float), False),
        pytest.param(LearntLiteralType("hello"), LearntSimpleType(str), True),
        pytest.param(LearntSimpleType(str), LearntUnionType([LearntSimpleType(str), LearntSimpleType(int)]), True),
    ],
)
def test_is_subtype(lt1: LearntType, lt2: LearntType, expected_result: bool):
    assert is_subtype(lt1, lt2) == expected_result
