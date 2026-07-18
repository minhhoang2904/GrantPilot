import unittest
from unittest.mock import patch
import mongo_store


class Policies:
    def __init__(self, existing): self.existing=existing; self.operations=[]
    def find(self, query, projection=None): return [dict(x) for x in self.existing]
    def bulk_write(self, operations, ordered=False):
        self.operations=operations
        return type("Result",(),{"upserted_count":0,"modified_count":len(operations)})()
class DB:
    def __init__(self, existing): self.policies=Policies(existing)


class MongoStoreTest(unittest.TestCase):
    def test_cross_batch_duplicate_updates_existing_policy(self):
        existing={"policy_id":"old","document_id":"d","document_version":1,"canonical_policy_key":"same","review_status":"candidate","is_current":True,"eligible_for_decision":False,"evidence_resolution":"precise"}
        incoming={"policy_id":"new","document_id":"d","document_version":2,"canonical_policy_key":"same","review_status":"approved","is_current":True,"eligible_for_decision":True,"evidence_resolution":"precise"}
        db=DB([existing])
        with patch("policy_normalization.prepare_policy_for_ingest", return_value=dict(incoming)):
            mongo_store.ingest_policies(db,[incoming])
        written=[op._doc for op in db.policies.operations]
        old=next(row for row in written if row["policy_id"]=="old")
        self.assertEqual(old["review_status"],"superseded")
        self.assertFalse(old["is_current"])
        self.assertEqual(old["superseded_by_policy_id"],"new")


if __name__ == "__main__": unittest.main()
