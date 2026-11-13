"""Data collection and preprocessing (§3.1).

Two data sources feed the framework:

* :mod:`.skills` — the skill packages harvested from the 17 markets (§3.1.1):
  platform declarations, parsers, HTTP client, two-stage cleaning, enrichment
  and storage sinks;
* :mod:`.licenses` — the licence reference set that interprets their
  declarations (§3.1.2): four-source merge, SPDX corpus crawler and the bundled
  term-level legal texts.

The public entry points are re-exported here so callers do not need to know the
subpackage layout::

    from liskill.data_collection_preprocessing import Collector, build_reference_set
"""

from .licenses import ReferenceSet, build_reference_set, normalize_alias  # noqa: F401
from .skills import (  # noqa: F401
    PLATFORMS,
    Collector,
    HttpClient,
    JsonlSink,
    MemorySink,
    MongoSink,
    Platform,
    clean_records,
    deduplicate,
    is_valid_record,
)
