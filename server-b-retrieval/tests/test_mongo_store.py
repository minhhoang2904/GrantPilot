from __future__ import annotations

import unittest

import config
from legal_store import MongoLegalUnitStore


class FakeCollection:
    def __init__(self, rows):
        self.rows = rows

    def find(self, query, projection=None):
        if "unit_id" in query:
            allowed = set(query["unit_id"].get("$in", []))
            return [row for row in self.rows if row.get("unit_id") in allowed]
        if "document_id" in query:
            allowed = set(query["document_id"].get("$in", []))
            return [row for row in self.rows if row.get("document_id") in allowed]
        return list(self.rows)


class FakeDatabase:
    def __init__(self, collections):
        self.collections = collections

    def __getitem__(self, name):
        return self.collections[name]


class FakeClient:
    def __init__(self, database):
        self.database = database

    def __getitem__(self, name):
        return self.database


class MongoLegalUnitStoreTest(unittest.TestCase):
    def test_hydrates_document_fields_from_current_document_schema(self):
        document = {
            "_id": "mongo-id",
            "document_id": "law-04-2017-qh14",
            "version": 1,
            "is_current": True,
            "document_number": "04/2017/QH14",
            "document_title": "Luật Hỗ trợ doanh nghiệp nhỏ và vừa",
            "issued_date": "2017-06-12",
            "effective_from": None,
            "effective_to": None,
            "status": "unknown",
            "source_url": "",
        }
        legal_unit = {
            "unit_id": "law-04-2017-qh14_art-8_cl-3",
            "document_id": "law-04-2017-qh14",
            "article": "8",
            "clause": "3",
            "point": "",
            "text": "Nội dung hỗ trợ tín dụng.",
            "is_current": True,
        }
        database = FakeDatabase(
            {
                config.MONGODB_DOCUMENTS_COLLECTION: FakeCollection([document]),
                config.MONGODB_LEGAL_UNITS_COLLECTION: FakeCollection([legal_unit]),
                config.MONGODB_POLICIES_COLLECTION: FakeCollection([]),
            }
        )
        store = MongoLegalUnitStore(client=FakeClient(database))

        result = store.get_many([legal_unit["unit_id"]])

        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["document_number"], "04/2017/QH14")
        self.assertEqual(
            result[0]["document_title"],
            "Luật Hỗ trợ doanh nghiệp nhỏ và vừa",
        )
        self.assertNotIn("_id", result[0])


if __name__ == "__main__":
    unittest.main()
