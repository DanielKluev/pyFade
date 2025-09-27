"""High level dataset access helpers backed by SQLAlchemy with SQLCipher support."""

# pylint: disable=no-member

from __future__ import annotations

import logging
import math
import pathlib

## MUST keep it on top of imports, as they may rely on path changes.
## **NEVER** move this. Disable pylint warning as it's intentional.
from py_fade.features_checker import SUPPORTED_FEATURES # pylint: disable=unused-import,wrong-import-order

import sqlite3
from types import ModuleType
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import joinedload, sessionmaker
from sqlalchemy.orm.session import Session

from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.dataset.data_filter import DataFilter
from py_fade.dataset.dataset_base import dataset_base
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample
from py_fade.providers.llm_response import LLMResponse

if TYPE_CHECKING:
    pass


class DatasetDatabase:
    """Manage a dataset stored in SQLite or SQLCipher format."""

    session: Session | None = None

    def __init__(self, db_path: str | pathlib.Path, password: str = ""):
        self.log = logging.getLogger("DatasetDatabase")
        self.db_path = pathlib.Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.password = password
        self.dataset_base = dataset_base
        self.engine: Engine = self._create_engine()
        self._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.session = None

    # ------------------------------------------------------------------
    def _create_engine(self) -> Engine:
        """Instantiate a SQLAlchemy engine honouring the current encryption state."""

        if self.password:
            if not SUPPORTED_FEATURES["sqlcipher3"]:
                raise RuntimeError(
                    "SQLCipher support is not available. Cannot open encrypted database."
                )
            if self.db_path.exists() and not self.check_password(self.db_path, self.password):
                raise ValueError("Incorrect password for SQLCipher database.")
            self.log.info("Opening SQLCipher encrypted database at %s", self.db_path)
            return create_engine(f"sqlite+pysqlcipher://:{self.password}@/{self.db_path}")

        self.log.info("Opening unencrypted SQLite database at %s", self.db_path)
        return create_engine(f"sqlite:///{self.db_path}")

    def _prepare_for_file_operation(self) -> None:
        """Close active connections so file-level operations can succeed."""

        if self.session:
            self.session.close()
            self.session = None
        self.engine.dispose()

    def _restore_session(self) -> None:
        """Re-create the engine and open a fresh session."""

        self.engine = self._create_engine()
        self._session_factory = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        self.session = self._session_factory()

    @staticmethod
    def _quote_password(password: str) -> str:
        """Escape password for use in SQLCipher PRAGMA statements."""

        return "'" + password.replace("'", "''") + "'"

    @staticmethod
    def _quote_path(path: pathlib.Path) -> str:
        """Escape a filesystem path for inclusion in SQL statements."""

        return "'" + str(path).replace("'", "''") + "'"

    @staticmethod
    def _import_sqlcipher3(purpose: str) -> ModuleType:
        """Import ``sqlcipher3`` lazily and raise a descriptive error on failure."""

        try:
            # pylint: disable=import-outside-toplevel
            import sqlcipher3  # type: ignore
        except ImportError as exc:  # pragma: no cover - defensive guard
            raise RuntimeError(f"sqlcipher3 package is required to {purpose}.") from exc
        return sqlcipher3  # type: ignore[attr-defined]

    def initialize(self) -> None:
        """Create database tables if needed and open a new session."""

        self.dataset_base.metadata.create_all(self.engine)
        if self.session is None:
            self.session = self._session_factory()

    def commit(self) -> None:
        """Persist pending changes to the backing SQLite database."""

        if not self.session:
            raise RuntimeError("Session is not initialized. Call initialize() first.")
        self.session.commit()

    def dispose(self) -> None:
        """Release all database resources held by this instance."""

        if self.session:
            self.session.close()
            self.session = None
        self.engine.dispose()

    def is_encrypted(self) -> bool:
        """Return ``True`` if the underlying database is SQLCipher encrypted."""

        if self.password:
            return True
        return self.check_db_type(self.db_path) == "sqlcipher"

    def encrypt_copy(self, destination: str | pathlib.Path, password: str) -> pathlib.Path:
        """Create a SQLCipher encrypted copy of the current dataset."""

        if self.is_encrypted():
            raise ValueError("Dataset is already encrypted.")
        if not password:
            raise ValueError("Password must not be empty.")
        if not SUPPORTED_FEATURES["sqlcipher3"]:
            raise RuntimeError("SQLCipher support is not available in this environment.")

        dest_path = pathlib.Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            dest_path.unlink()

        if self.session:
            self.session.commit()

        self._prepare_for_file_operation()
        try:
            sqlcipher3 = self._import_sqlcipher3("encrypt datasets")
            conn = sqlcipher3.connect(self.db_path)  # type: ignore[attr-defined]
            try:
                conn.execute("PRAGMA cipher_compatibility = 4;")
                attach_sql = (
                    "ATTACH DATABASE "
                    f"{self._quote_path(dest_path)} "
                    "AS encrypted KEY "
                    f"{self._quote_password(password)};"
                )
                conn.execute(attach_sql)
                conn.execute("SELECT sqlcipher_export('encrypted');")
                conn.execute("DETACH DATABASE encrypted;")
            finally:
                conn.close()
        finally:
            self._restore_session()

        return dest_path

    def save_unencrypted_copy(self, destination: str | pathlib.Path) -> pathlib.Path:
        """Persist a plain SQLite copy of the encrypted dataset."""

        if not self.is_encrypted():
            raise ValueError("Dataset is not encrypted.")
        if not self.password:
            raise RuntimeError("Current password is required to decrypt the dataset.")

        dest_path = pathlib.Path(destination)
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        if dest_path.exists():
            dest_path.unlink()

        if self.session:
            self.session.commit()

        self._prepare_for_file_operation()
        try:
            sqlcipher3 = self._import_sqlcipher3("decrypt datasets")
            conn = sqlcipher3.connect(self.db_path)  # type: ignore[attr-defined]
            try:
                conn.execute(f"PRAGMA key = {self._quote_password(self.password)};")
                attach_sql = (
                    "ATTACH DATABASE "
                    f"{self._quote_path(dest_path)} "
                    "AS plaintext KEY '';"
                )
                conn.execute(attach_sql)
                conn.execute("SELECT sqlcipher_export('plaintext');")
                conn.execute("DETACH DATABASE plaintext;")
            finally:
                conn.close()
        finally:
            self._restore_session()

        return dest_path

    def change_password(self, new_password: str) -> None:
        """Change the encryption password for the dataset in-place."""

        if not self.is_encrypted():
            raise ValueError("Dataset is not encrypted.")
        if not self.password:
            raise RuntimeError("Current password is not known; cannot change password.")
        if not new_password:
            raise ValueError("New password must not be empty.")
        if not SUPPORTED_FEATURES["sqlcipher3"]:
            raise RuntimeError("SQLCipher support is not available in this environment.")

        if self.session:
            self.session.commit()

        self._prepare_for_file_operation()
        try:
            sqlcipher3 = self._import_sqlcipher3("change dataset passwords")
        except Exception:  # pragma: no cover - defensive guard for import errors
            self._restore_session()
            raise

        try:
            conn = sqlcipher3.connect(self.db_path)  # type: ignore[attr-defined]
            try:
                conn.execute(f"PRAGMA key = {self._quote_password(self.password)};")
                conn.execute(f"PRAGMA rekey = {self._quote_password(new_password)};")
            finally:
                conn.close()
        except sqlcipher3.Error as exc:  # type: ignore[attr-defined]
            raise RuntimeError("Failed to change dataset password.") from exc
        else:
            self.password = new_password
        finally:
            self._restore_session()

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

    def add_response_as_prompt_and_completion(
        self, prompt_text: str, response: LLMResponse
    ) -> tuple[PromptRevision, PromptCompletion]:
        """
        Turn response into PromptCompletion, add to sample, and return it.
        """
        if not self.session:
            raise RuntimeError("Session is not initialized. Call initialize() first.")

        prompt_revision = PromptRevision.get_or_create(
            self, prompt_text, response.context_length, response.max_tokens
        )
        completion = PromptCompletion.get_or_create_from_llm_response(
            self, prompt_revision, response
        )
        return prompt_revision, completion

    def get_beams_for_prompt_and_model(
        self, prompt: PromptRevision | str, model_id: str
    ) -> list[LLMResponse]:
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
        completions = (
            self.session.query(PromptCompletionLogprobs)
            .join(PromptCompletion)
            .options(joinedload(PromptCompletionLogprobs.prompt_completion))
            .filter(
                PromptCompletion.prompt_revision_id == prompt_revision.id,
                PromptCompletionLogprobs.logprobs_model_id == model_id,
            )
            .all()
        )

        responses = []
        for logprobs in completions:
            response = LLMResponse.from_completion_and_logprobs(
                logprobs.prompt_completion, logprobs
            )
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

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                conn.execute("PRAGMA schema_version;")
            except sqlite3.DatabaseError:
                pass
            else:
                return "sqlite"
            finally:
                conn.close()
        except sqlite3.DatabaseError:
            pass

        with open(db_path, "rb") as f:
            header = f.read(1024)

        if SUPPORTED_FEATURES.get("sqlcipher3", False):
            try:
                sqlcipher3 = cls._import_sqlcipher3("inspect databases")
            except RuntimeError:
                sqlcipher3 = None

            if sqlcipher3 is not None:
                conn = None
                try:
                    conn = sqlcipher3.connect(db_path)  # type: ignore[attr-defined]
                    try:
                        conn.execute("PRAGMA schema_version;")
                    except sqlcipher3.DatabaseError:  # type: ignore[attr-defined]
                        return "sqlcipher"
                except sqlcipher3.Error:  # type: ignore[attr-defined]
                    return "sqlcipher"
                finally:
                    if conn is not None:
                        conn.close()

        # Compute Shannon entropy on first 1 KB as a last-resort heuristic.
        freq = {}
        for byte in header:
            freq[byte] = freq.get(byte, 0) + 1

        entropy = 0.0
        length = len(header)
        for count in freq.values():
            p = count / length
            entropy -= p * math.log2(p)

        if entropy > 7.0:
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
            # pylint: disable=import-outside-toplevel
            import sqlcipher3  # type: ignore
        except ImportError:
            return False

        try:
            conn = sqlcipher3.connect(db_path)  # type: ignore[attr-defined]
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA key = {cls._quote_password(password)};")
            cursor.execute("SELECT count(*) FROM sqlite_master;")
            cursor.fetchone()
            conn.close()
            return True
        except sqlcipher3.Error:  # type: ignore[attr-defined]
            return False
