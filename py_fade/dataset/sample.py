import datetime
from sqlalchemy import Column, Float, ForeignKey, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, DateTime

from py_fade.dataset.dataset_base import dataset_base
from py_fade.dataset.data_filter import DataFilter
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.providers.llm_response import LLMResponse

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase

class Sample(dataset_base):
    """
    Class to hold main sample object, which is a pinned prompt revision and it's completions.
    """
    __tablename__ = "samples"
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String, nullable=False)
    group_path: Mapped[str | None] = mapped_column(String, nullable=True)
    date_created: Mapped[datetime.datetime] = mapped_column(DateTime, nullable=False, default=datetime.datetime.now)
    prompt_revision_id: Mapped[int] = mapped_column(ForeignKey("prompt_revisions.id"), nullable=True)
    prompt_revision: Mapped["PromptRevision"] = relationship("PromptRevision", back_populates="samples", lazy="joined")

    @classmethod
    def create_if_unique(cls, dataset: "DatasetDatabase", title: str, prompt_revision: PromptRevision, group_path: str | None = None) -> "Sample | None":
        """
        Create new Sample instance if there's no existing sample for same prompt.
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        
        existing = dataset.session.query(cls).filter_by(prompt_revision=prompt_revision).first()
        if existing:
            return None
        
        new_sample = cls(
            title=title,
            group_path=group_path,
            date_created=datetime.datetime.now(),
            prompt_revision=prompt_revision
        )
        dataset.session.add(new_sample)
        dataset.session.commit()
        return new_sample
    
    @classmethod
    def fetch_with_filter(cls, dataset: "DatasetDatabase", data_filter: "DataFilter | None" = None) -> list["Sample"]:
        """
        Fetch samples from the database, optionally applying a DataFilter.
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        
        query = dataset.session.query(Sample)
        if data_filter:
            query = data_filter.apply_to_query(query)
        
        return query.all()
    

    def new_copy(self) -> "Sample":
        """
        Create a new unsaved copy of this sample with the same prompt revision and title appended with ' (Copy)'.
        """
        return self.__class__(
            title=f"{self.title} (Copy)",
            group_path=self.group_path,
            date_created=datetime.datetime.now(),
            prompt_revision=self.prompt_revision
        )
    
    @classmethod
    def from_prompt_revision(cls, dataset: "DatasetDatabase", prompt_revision: PromptRevision) -> "Sample":
        """
        If there's sample for the given prompt revision, return it. Otherwise,
        Create a new unsaved Sample instance from a given PromptRevision.
        """
        if not dataset.session:
            raise RuntimeError("Dataset session is not initialized. Call dataset.initialize() first.")
        existing = dataset.session.query(cls).filter_by(prompt_revision=prompt_revision).first()
        if existing:
            return existing
        return cls(
            title="New Sample",
            group_path=None,
            date_created=datetime.datetime.now(),
            prompt_revision=prompt_revision
        )