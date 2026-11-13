"""Which of the three paper models sits behind each ``--use-llm`` stage."""

import json

from liskill.demo.workflows import LLMWorkflowGenerator, parse_skill_order
from liskill.llm import LLMConfig
from liskill.ontology import TERMS
from liskill.pipeline import LiSkillPipeline
from liskill.understand.train_lora import LoRAConfig

TID = TERMS[0].tid


class RecordingClient:
    """Counts the prompts it is asked to answer instead of calling a server."""

    def __init__(self) -> None:
        self.prompts = []

    def complete(self, prompt, json_mode=False, system=""):
        self.prompts.append(prompt)
        return json.dumps({"terms": [{"term_id": TID, "attitude": "CANNOT"}]})


def test_understanding_client_names_the_fine_tuned_model():
    """The served id must be the adapter, never the un-tuned base checkpoint."""
    config = LLMConfig()
    assert config.model == "Qwen3.5-9B-LiSkill"
    assert config.model != LoRAConfig().base_model.rsplit("/", 1)[-1]


def test_drafting_stage_is_the_flash_checkpoint():
    """§3.3.2 pre-annotation and §4.4.2 workflows share the general drafting model."""
    config = LLMConfig.for_drafting()
    assert config.model == "DeepSeek-V4-Flash-0731"
    assert config.base_url != LLMConfig().base_url
    # §4.1.4: reasoning effort high, vendor default decoding (temperature unset)
    assert config.reasoning_effort == "high"
    assert config.temperature is None


def test_normalization_stage_is_the_local_base_checkpoint():
    """§3.2.2 normalises with the base Qwen3.5-9B, not with the §3.3.3 adapter."""
    config = LLMConfig.for_normalization()
    assert config.model == "Qwen3.5-9B"
    assert config.model != LLMConfig().model
    assert config.base_url == LLMConfig().base_url  # same local server, other name
    assert config.model != LLMConfig.for_drafting().model


def test_term_database_reads_through_the_model_when_a_client_is_given():
    client = RecordingClient()
    termdb = LiSkillPipeline(llm=client).build_termdb()
    assert client.prompts, "Λ(l) silently fell back to the offline reader"
    observations = termdb.observations.get("MIT", {})
    assert set(observations) == {TID}, "observations did not come from the model"
    assert set(observations[TID]) == {"CANNOT"}


def test_term_database_stays_offline_without_a_client():
    termdb = LiSkillPipeline().build_termdb()
    assert termdb.profiles


CATALOG = [
    {"skill_id": "s-pdf", "name": "pdf-report", "description": "Render a data set into a PDF report"},
    {"skill_id": "s-data", "name": "data-connector", "description": "Query the SQL warehouse and return rows"},
]


class ScriptedClient:
    """Answers requirement prompts, then hands back scripted compositions."""

    def __init__(self, requirements, compositions) -> None:
        self.requirements = requirements
        self.compositions = list(compositions)
        self.prompts = []

    def complete(self, prompt, json_mode=False, system=""):
        self.prompts.append(prompt)
        if "Category:" in prompt:
            return json.dumps({"requirements": self.requirements})
        return self.compositions.pop(0)


def test_workflows_come_from_the_model_and_need_a_call_edge():
    client = ScriptedClient(
        requirements=[
            "Query the SQL warehouse and render a PDF report",
            "Render the final PDF report from the returned rows",
        ],
        compositions=['{"skills": ["s-data", "s-pdf"]}', '{"skills": ["s-pdf"]}'],
    )
    chains = LLMWorkflowGenerator(client, categories=["data-report"]).generate(CATALOG, count=5)
    # a requirement that activates one skill produces no edge -> out of the set
    assert [chain.skill_ids for chain in chains] == [["s-data", "s-pdf"]]
    assert chains[0].description.startswith("Query the SQL")
    assert any("Category:" in prompt for prompt in client.prompts)


def test_generated_order_cannot_invent_skills():
    order = parse_skill_order('{"skills": ["s-data", "not-a-skill", "s-pdf"]}', ["s-data", "s-pdf"])
    assert order == ["s-data", "s-pdf"]
