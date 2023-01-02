from pathlib import Path

from slow_learner import TypeLearner

tl = TypeLearner(max_literal_type_size=0)


tl.observe(
    {
        "context": {"text": "hello", "from": "en", "to": "ru"},
        "service": {},
        "list": [],
    }
)

tl.observe(
    {
        "context": {"text": ["one", "two", "three"], "to": "zh"},
        "service": {"provider": "someone"},
        "internal": {},
        "list": [],
    }
)
print(tl.learnt_type)
tl.generate_type_definitions(Path("example.py"), "Request", "JSON payload received from the user")
