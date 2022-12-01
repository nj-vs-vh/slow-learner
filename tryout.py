from slow_learner import TypeLearner

tl = TypeLearner(max_literal_type_size=0)


tl.observe(
    {
        "context": {"text": "hello", "from": "en", "to": "ru"},
        "service": {},
    }
)
print(tl.learnt_type)

tl.observe(
    {
        "context": {"text": ["one", "two", "three"], "to": "zh"},
        "service": {"provider": "someone"},
    }
)
print(tl.learnt_type)
