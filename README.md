# slow-learner — python type inference tool

See also: [post](https://nj-vs-vh.name/project/slow-learner)

A library and CLI to consume a stream of values (for CLI — JSON documents) and
generate Python types describing it. Features:
- recursion into mappings and collections with generic types generation
- "structured dicts" are turned into `TypedDict`s by default
- values with a small set of observed values are turned into `Literal`s

## Installation

```shell
pip install slow-learner
```

## Usage

As CLI:

```shell
slow-learner learn 1.json 2.json 3.json

# to learn the type of list item
slow-learner learn --spread list.json
```

In Python:

```python
from slow_learner import TypeLearner

tl = TypeLearner(
    max_literal_type_size=5,
    learn_typed_dicts=True,
    max_typed_dict_size=50,
    max_recursive_type_depth=5,
    no_literal_patterns=[r"\.password", r".*secret"],
)

for value in my_values:
    tl.observe(value)

tl.save_type_definition("result.py", "MyType")
```
