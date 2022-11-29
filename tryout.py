from slow_learner import TypeLearner

tl = TypeLearner(max_literal_type_size=2)

tl.observe((1, 2, 3))
tl.observe((1, 2, 4))
tl.observe((1, 2, 7))
