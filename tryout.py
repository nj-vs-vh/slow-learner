from slow_learner import TypeLearner

tl = TypeLearner(max_literal_type_size=2)

# tl.observe([1])
# tl.observe([1, 1, 1, 1, 1])
# tl.observe([1, 2, 3, 4, 5])
tl.observe({3.14, 1, 2})
# tl.observe([1, 'world'])
# tl.observe(['hello'])

print(tl.learnt_type)
