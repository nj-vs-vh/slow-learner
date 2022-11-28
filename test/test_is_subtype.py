import pytest
from slow_learner import is_subtype, LearntType, LearntSimpleType, LearntLiteralType, LearntTupleType, LearntUnionType


class CustomStr(str):
    pass


@pytest.mark.parametrize(
    'lt1, lt2, expected_result',
    [
        pytest.param(LearntSimpleType(CustomStr), LearntSimpleType(str), True),
        pytest.param(LearntSimpleType(int), LearntLiteralType(1312), False),
        pytest.param(LearntSimpleType(int), LearntSimpleType(float), False),
        pytest.param(LearntLiteralType('hello'), LearntSimpleType(str), True),
        pytest.param(
            LearntSimpleType(str), LearntUnionType([LearntSimpleType(str), LearntSimpleType(int)]), True
        )
    ]
)
def test_is_subtype(lt1: LearntType, lt2: LearntType, expected_result: bool):
    assert is_subtype(lt1, lt2) == expected_result
