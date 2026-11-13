"""Collection layer (§3.1): parsers, cleaning, offline driver."""

import pytest

from liskill.data_collection_preprocessing.skills.clean import clean_records, content_hash, is_valid_record
from liskill.data_collection_preprocessing.skills.fixtures import FIXTURES
from liskill.data_collection_preprocessing.skills.platforms import PLATFORMS, platform_names
from liskill.data_collection_preprocessing.skills.runner import Collector
from liskill.data_collection_preprocessing.skills.sink import MemorySink
from liskill.data_collection_preprocessing.skills.spiders import get_parser, github_full_name, repo_relative_path


def test_all_seventeen_platforms_are_declared():
    assert len(PLATFORMS) == 17
    for name in platform_names():
        assert get_parser(PLATFORMS[name]) is not None


def test_github_helpers():
    assert github_full_name("https://github.com/owner/repo/tree/main/skill") == "owner/repo"
    assert repo_relative_path("https://github.com/owner/repo/tree/main/skill/sub") == "skill/sub"
    assert repo_relative_path("https://github.com/owner/repo") == ""


@pytest.mark.parametrize("name", sorted(FIXTURES))
def test_every_parser_reads_its_payload(name):
    platform = PLATFORMS[name]
    parser = get_parser(platform)
    records, has_more = parser(platform, FIXTURES[name][0], 1)
    assert records, f"{name} produced no record"
    assert isinstance(has_more, bool)
    for record in records:
        assert record["platform"] == name
        assert record["name"]


def test_records_carry_the_table4_fields():
    platform = PLATFORMS["agentskills.in"]
    records, _ = get_parser(platform)(platform, FIXTURES["agentskills.in"][0], 1)
    sample = records[0]
    for field in ("platform", "name", "description", "repo_url", "repo_full_name", "relative_path"):
        assert field in sample
    assert sample["repo_full_name"] == "example/data-connector"


def test_invalid_records_are_dropped():
    assert is_valid_record({"name": "a", "description": "", "skill_md_content": ""}) is False
    assert is_valid_record({"name": "", "description": "b"}) is False
    assert (
        is_valid_record({"name": "a", "description": "b", "skill_md_content": "---\nx: 1\n---\nshort"})
        is False
    )
    long_body = "---\nname: a\n---\n" + "x" * 80
    assert is_valid_record({"name": "a", "description": "b", "skill_md_content": long_body}) is True


def test_dedup_keeps_the_earliest_record():
    raw = [
        {"platform": "a", "name": "skill", "description": "d", "collected_at": 200, "skill_md_content": ""},
        {"platform": "b", "name": "skill", "description": "d", "collected_at": 100, "skill_md_content": ""},
    ]
    unique, stats = clean_records(raw)
    assert len(unique) == 1
    assert unique[0]["platform"] == "b"
    assert unique[0]["skill_id"] == content_hash("skill", "d")[:16]
    assert stats.dedup_rate == 50.0


def test_offline_collection_runs_all_platforms():
    sink = MemorySink()
    report = Collector(sink=sink, offline=True).run()
    assert len(report.platforms) == 17
    assert report.raw_records > 0
    assert report.cleaning is not None
    assert report.unique_records <= report.raw_records
    assert all(platform.records > 0 for platform in report.platforms)
