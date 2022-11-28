from slow_learner import TypeLearner


tl = TypeLearner()

# tl.observe((1, 2, 3))
# tl.observe((1, 2, 4))
# tl.observe((1, 2, 7))

for i in range(100):
    tl.observe(i)

