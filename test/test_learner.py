import pathlib
import random
import string
import subprocess
import uuid
from typing import Any

import pytest
from pytest import param

from slow_learner import TypeLearner
from slow_learner.learnt_types import (
    LCollection,
    LearntType,
    LLiteral,
    LMapping,
    LMissingTypedDictKey,
    LNone,
    LTuple,
    LType,
    LTypedDict,
    LUnion,
)


@pytest.mark.parametrize(
    "stream, expected_learnt_type, order_independent",
    [
        # literals and simple types
        param([1, 2, 3], LUnion([LLiteral(1), LLiteral(2), LLiteral(3)]), True),
        param(list(range(100)), LType(int), True),
        param(list(range(100)) + [None], LUnion([LType(int), LNone()]), True),
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
        # collections
        param([[1, 2]], LCollection(list, LUnion([LLiteral(1), LLiteral(2)])), True),
        param([list(range(10))], LCollection(list, LType(int)), True),
        param([list(range(10)), [100], [200]], LCollection(list, LType(int)), True),
        param(
            [list(range(10)), ["hello"], ["world"]],
            LCollection(list, LUnion([LType(int), LLiteral("hello"), LLiteral("world")])),
            True,
        ),
        param(
            [list(range(10)), ["hello"], ["world"], ["aaaa", 13.5, "bbb"], ["foo", "bar", "baz", True]],
            LCollection(list, LUnion([LType(float), LType(str)])),
            True,
        ),
        param(
            [[], [], [], []],
            LCollection(list, LUnion([])),
            True,
        ),
        # typed dicts
        param(
            [{"foo": 1, "bar": 2, "baz": 3}],
            LTypedDict({"foo": LLiteral(1), "bar": LLiteral(2), "baz": LLiteral(3)}),
            True,
        ),
        param(
            [{"foo": i, "bar": 2 * i, "baz": 3 * i} for i in range(1000)],
            LTypedDict({"foo": LType(int), "bar": LType(int), "baz": LType(int)}),
            True,
        ),
        param(
            [{"nested": {"letter": s}} for s in string.ascii_letters * 10],
            LTypedDict({"nested": LTypedDict({"letter": LType(str)})}),
            True,
        ),
        param(
            [{"nested": {"list": [s, s * 2, s * 3]}, "literal": 1312} for s in string.ascii_letters * 10],
            LTypedDict({"nested": LTypedDict({"list": LCollection(list, LType(str))}), "literal": LLiteral(1312)}),
            True,
        ),
        param(
            [
                {"typed": "dictionary"},
                {"typed": "yes", "hello": "world"},
                {"typed": "very much so"},
                {"typed": "oooof"},
                {},
                {"typed": "yea"},
                {"typed": "now its a string yo"},
                {"something else": 3},
            ],
            LTypedDict(
                {
                    "typed": LUnion([LType(str), LMissingTypedDictKey()]),
                    "hello": LUnion([LLiteral("world"), LMissingTypedDictKey()]),
                    "something else": LUnion([LLiteral(3), LMissingTypedDictKey()]),
                }
            ),
            True,
        ),
        # homogenious mappings
        param([{s: i for s, i in zip(string.ascii_letters, range(100))}], LMapping(dict, LType(str), LType(int)), True),
        param(
            [
                {"typed": "dict", "field": 3},
                {s: s for s in string.ascii_letters},
                {s: i for s, i in zip(string.ascii_letters, range(100))},
            ],
            LMapping(dict, LType(str), LUnion([LType(str), LType(int)])),
            True,
        ),
        param(
            [*[{i: 4} for i in range(100)], *[{s: 2} for s in string.ascii_letters]],
            LMapping(dict, LUnion([LType(str), LType(int)]), LUnion([LLiteral(2), LLiteral(4)])),
            True,
        ),
    ],
)
def test_type_learner_basic(
    stream: list[Any],
    expected_learnt_type: LearntType,
    order_independent: bool,
    tmp_path: pathlib.Path,
):
    random.seed(1312)
    for _ in range(5):
        tl = TypeLearner(
            max_literal_type_size=5,
            learn_typed_dicts=True,
            max_typed_dict_size=5,
            max_recursive_type_depth=3,
        )
        for value in stream:
            tl.observe(value)
        assert tl.learnt_type == expected_learnt_type

        type_name = "TestType"

        typedef_file = tmp_path / f"{uuid.uuid4().hex}.py"
        tl.generate_type_definitions(typedef_file, type_name, doc="testing type generation")

        assert typedef_file.exists()

        # validating that a valid Python module is generated
        res = subprocess.run(["python", str(typedef_file)], capture_output=True)
        assert res.returncode == 0, f"Generated file does not contain a valid Python code: {res.stderr.decode()}"

        # validating that the generated type does indeed contain all of the samples
        typedef_text = typedef_file.read_text()
        typedef_text += f"\n\ndef func(arg: {type_name}) -> None:\n    pass\n\n"
        for value in stream:
            typedef_text += f"func({value!r})\n"
        typedef_file.write_text(typedef_text)
        res = subprocess.run(["mypy", "--strict", str(typedef_file)], capture_output=True)
        assert res.returncode == 0, f"Mypy finds errors: {res.stdout.decode()}"

        if not order_independent:
            break

        random.shuffle(stream)
