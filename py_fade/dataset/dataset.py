import pathlib
import math
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.session import Session
from sqlalchemy.orm import joinedload
from py_fade.dataset.dataset_base import dataset_base
from py_fade.dataset.data_filter import DataFilter
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.sample import Sample

from py_fade.providers.llm_response import LLMResponse
from py_fade.features_checker import SUPPORTED_FEATURES

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
        self.log = logging.getLogger("DatasetDatabase")
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        if password: 
            if not SUPPORTED_FEATURES["sqlcipher3"]:
                raise RuntimeError("SQLCipher support is not available. Cannot open encrypted database.")
            if not self.check_password(db_path, password):
                raise ValueError("Incorrect password for SQLCipher database.")
            self.log.info(f"Opening SQLCipher encrypted database at {self.db_path}")
            self.engine = create_engine(f"sqlite+pysqlcipher://:{password}@/{self.db_path}")
        else:
            self.log.info(f"Opening unencrypted SQLite database at {self.db_path}")
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
    
    @classmethod
    def check_db_type(cls, db_path: str | pathlib.Path) -> str:
        """
        Check if the database at db_path is a valid SQLite, possible SQLCipher or something else.
        Returns 'sqlite', 'sqlcipher', or 'unknown'.
        """
        db_path = pathlib.Path(db_path)
        if not db_path.exists():
            return "unknown"
        
        with open(db_path, "rb") as f:
            header = f.read(1024)

        # Check plain SQLite magic header
        if header.startswith(b"SQLite format 3\000"):
            return "sqlite"

        # Compute Shannon entropy on first 1 KB
        freq = {}
        for byte in header:
            freq[byte] = freq.get(byte, 0) + 1

        entropy = 0.0
        length = len(header)
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)

        # Heuristic thresholds:
        # - Random/encrypted data ~7.9–8.0 bits/byte
        # - Text/structured file significantly lower
        if entropy > 7.5:
            return "sqlcipher"
        return "unknown"
    
    @classmethod
    def check_password(cls, db_path: str | pathlib.Path, password: str) -> bool:
        """
        Check if the provided password can successfully open the SQLCipher database.
        Returns True if successful, False otherwise.
        """
        if not SUPPORTED_FEATURES["sqlcipher3"]:
            return False
        
        db_path = pathlib.Path(db_path)
        if not db_path.exists():
            return False
        
        try:
            import sqlcipher3 # type: ignore
        except ImportError:
            return False
        
        try:
            conn = sqlcipher3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA key = '{password}';")
            cursor.execute("SELECT count(*) FROM sqlite_master;")
            cursor.fetchone()
            conn.close()
            return True
        except Exception:
            return False

