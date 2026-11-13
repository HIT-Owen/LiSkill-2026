"""Skill harvesting (§3.1.1).

Self-contained replacement for the early collection stack: no internal
scheduler, no MongoDB requirement, no Redis.  Each platform is described by a
declaration in :mod:`.platforms` and a parser in :mod:`.spiders`.

    records = Collector(sink=JsonlSink("data/raw.jsonl")).run(["clawhub"])

Run with ``offline=True`` (or ``--offline`` on the CLI) to parse the bundled
sample payloads instead of hitting the network, which is how the demo and the
unit tests exercise the parsers.
"""

from .clean import clean_records, deduplicate, is_valid_record  # noqa: F401
from .http import HttpClient  # noqa: F401
from .platforms import NORMALIZED_FIELDS, PLATFORMS, Platform  # noqa: F401
from .runner import Collector  # noqa: F401
from .sink import JsonlSink, MemorySink, MongoSink  # noqa: F401
