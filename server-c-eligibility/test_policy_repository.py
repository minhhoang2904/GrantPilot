import unittest
from policy_repository import DECISION_QUERY, MongoPolicyRepository


class FakeCollection:
    def __init__(self): self.query = None
    def find(self, query, projection): self.query = query; return []


class PolicyRepositoryTest(unittest.TestCase):
    def test_decision_path_is_strict(self):
        collection = FakeCollection(); MongoPolicyRepository(collection).get_policies()
        self.assertEqual(collection.query, DECISION_QUERY)
        self.assertEqual(collection.query["review_status"], "approved")
        self.assertTrue(collection.query["eligible_for_decision"])


if __name__ == "__main__": unittest.main()
