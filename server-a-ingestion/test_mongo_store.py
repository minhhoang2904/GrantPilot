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


class Rows:
    def __init__(self, rows): self.rows=rows
    def find_one(self, query, projection=None):
        return next((dict(row) for row in self.rows if all(row.get(key) == value for key, value in query.items() if not isinstance(value, dict))), None)
    def find(self, query, projection=None):
        ids=set((query.get("unit_id") or {}).get("$in", []))
        return [dict(row) for row in self.rows if not ids or row.get("unit_id") in ids]


class IntegrityDB(DB):
    def __init__(self, documents, units):
        super().__init__([])
        self.legal_documents=Rows(documents)
        self.legal_units=Rows(units)


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
        self.assertNotIn("payload", old["payload"])

    def test_reingest_same_identity_writes_incoming_without_self_supersession(self):
        existing={"policy_id":"same","document_id":"d","document_version":1,"canonical_policy_key":"same","review_status":"candidate","is_current":True,"eligible_for_decision":False,"evidence_resolution":"precise","payload":{"policy_id":"same","payload":{"legacy":"nested"}}}
        incoming={"policy_id":"same","document_id":"d","document_version":1,"canonical_policy_key":"same","review_status":"approved","is_current":True,"eligible_for_decision":True,"evidence_resolution":"precise"}
        db=DB([existing])
        with patch("policy_normalization.prepare_policy_for_ingest", return_value=dict(incoming)):
            mongo_store.ingest_policies(db,[incoming])
        self.assertEqual(len(db.policies.operations), 1)
        written=db.policies.operations[0]._doc
        self.assertEqual(written["review_status"], "approved")
        self.assertTrue(written["is_current"])
        self.assertIsNone(written["superseded_by_policy_id"])
        self.assertNotIn("payload", written["payload"])

    def test_mongo_write_boundary_rejects_swapped_legal_unit_source(self):
        document={"document_id":"decree-80-2021-nd-cp","document_number":"80/2021/NĐ-CP","source_url":"https://vanban.chinhphu.vn/decree-80","version":1,"is_current":True}
        unit={"unit_id":"unit-1","document_id":document["document_id"],"document_number":"06/2022/TT-BKHĐT","source_url":"https://vbpl.vn/circular-06","version":1,"is_current":True,"article":"12","clause":"1"}
        policy={"policy_id":"integrity-write","pipeline":{"document_id":document["document_id"]},"evidence_unit_ids":[unit["unit_id"]],"rules":{"all":[{"field":"is_sme","operator":"==","value":True}]}}
        db=IntegrityDB([document],[unit])
        mongo_store.ingest_policies(db,[policy])
        written=db.policies.operations[0]._doc
        self.assertEqual(written["review_status"],"rejected")
        self.assertFalse(written["eligible_for_decision"])
        self.assertEqual(written["evidence_resolution"],"unresolved")
        codes={item["code"] for item in written["validation_issues_current"]}
        self.assertIn("evidence_document_number_mismatch",codes)
        self.assertIn("evidence_source_url_mismatch",codes)


if __name__ == "__main__": unittest.main()
