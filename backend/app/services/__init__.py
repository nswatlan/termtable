"""Business logic. Services validate input, enforce rules (ownership,
enrollment, invitation states...), call repositories, and decide when to
commit. They know nothing about Flask requests or sessions: the logged-in
user's id is passed in explicitly.
"""
