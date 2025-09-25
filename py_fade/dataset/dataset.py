import pathlib, hashlib, json
from sqlalchemy import Column, Integer, String, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import joinedload
from sqlalchemy.types import JSON
from py_fade.dataset.dataset_base import dataset_base
from py_fade.dataset.data_filter import DataFilter
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.sample import Sample

from py_fade.providers.llm_response import LLMResponse

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    pass
    

class DatasetDatabase:
    """
    Manages a SQLite database for storing dataset entries.
    Each entry includes a prompt, response, prefill, and metadata.

    If password is provided, use sqlcipher to encrypt the database.
    """
    session: Session | None = None
    def __init__(self, db_path: str | pathlib.Path, password: str = ""):
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(f"sqlite:///{self.db_path}")
        self.SessionFactory = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.dataset_base = dataset_base
        self.password = password

    def initialize(self):
        self.dataset_base.metadata.create_all(self.engine)
        self.session = self.SessionFactory()

    def commit(self):
        if not self.session:
            raise RuntimeError("Session is not initialized. Call initialize() first.")
        self.session.commit()

    def list_unique_group_paths(self) -> list[str]:
        """
        List all unique group paths in the samples.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call initialize() first.")

        results = self.session.query(Sample.group_path).distinct().all()
        return [r[0] for r in results if r[0] is not None]


    def get_prompts(self, data_filter: DataFilter | None = None) -> list[PromptRevision]:
        """
        Retrieve a list of unique prompts from the database, optionally filtered by DataFilter.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call initialize() first.")

        query = self.session.query(PromptRevision).all()
        if data_filter:
            query = data_filter.apply_to_query(query)
        return query

    def add_response_as_prompt_and_completion(self, prompt_text:str, response: LLMResponse) -> tuple[PromptRevision, PromptCompletion]:
        """
        Turn response into PromptCompletion, add to sample, and return it.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call initialize() first.")
        
        prompt_revision = PromptRevision.get_or_create(self, prompt_text, response.context_length, response.max_tokens)
        completion = PromptCompletion.get_or_create_from_llm_response(self, prompt_revision, response)
        return prompt_revision, completion
    
    def get_beams_for_prompt_and_model(self, prompt: PromptRevision|str, model_id: str) -> list[LLMResponse]:
        """
        Retrieve all beam completions for a given prompt text and model_id.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call initialize() first.")
        
        if isinstance(prompt, str):
            prompt_revision = PromptRevision.get_by_hash(self, prompt)
        else:
            prompt_revision = prompt
        if not prompt_revision:
            return []
        
        # Find completions which have completion_logprobs.logprobs_model_id == given model_id
        completions = self.session.query(PromptCompletionLogprobs).join(PromptCompletion).options(joinedload(PromptCompletionLogprobs.prompt_completion)).filter(
            PromptCompletion.prompt_revision_id == prompt_revision.id,
            PromptCompletionLogprobs.logprobs_model_id == model_id
        ).all()

        responses = []
        for logprobs in completions:
            response = LLMResponse.from_completion_and_logprobs(logprobs.prompt_completion, logprobs)
            responses.append(response)
        return responses