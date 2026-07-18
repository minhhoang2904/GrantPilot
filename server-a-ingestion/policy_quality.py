"""Compatibility wrapper; canonical normalization lives in policy_normalization."""
from policy_normalization import (  # noqa: F401
    SCHEMA_VERSION,
    apply_duplicates,
    dry_run,
    load_catalog,
    normalize_rules,
    prepare_policy_for_ingest,
)


def ingest_policies(db, policies, **_ignored):
    """Legacy import path delegated to the single Mongo writer."""
    from mongo_store import ingest_policies as write
    return write(db, policies)
