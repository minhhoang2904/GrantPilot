import unittest
from policy_repository import DECISION_QUERY, MongoPolicyRepository


class Collection:
    def __init__(self, rows=()): self.rows=list(rows); self.query=None
    def find(self, query, projection=None): self.query=query; return list(self.rows)
    def find_one(self, query, projection=None): return self.rows[0] if self.rows else None
    def count_documents(self, query): return len(self.rows)
class Database(dict):
    def __getitem__(self, name): return super().setdefault(name, Collection())
class Client:
    def __init__(self): self.db=Database(); self.admin=type("Admin",(),{"command":lambda *_:None})()
    def __getitem__(self, name): return self.db


class PolicyRepositoryTest(unittest.TestCase):
    def setUp(self):
        self.client=Client(); self.repo=MongoPolicyRepository(self.client)
    def test_decision_query_is_strict(self):
        self.repo.get_policies(); self.assertEqual(self.repo.policies.query, DECISION_QUERY)
    def test_evidence_returns_legal_unit_documents(self):
        self.repo.legal_units.rows=[{"_id":"x","unit_id":"u1","text":"Điều 1"}]
        self.assertEqual(self.repo.get_evidence(["u1"]), [{"unit_id":"u1","text":"Điều 1"}])

if __name__ == "__main__": unittest.main()
