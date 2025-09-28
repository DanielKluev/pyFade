"""Tests for dataset encryption workflows built into :mod:`py_fade.dataset.dataset`."""
from __future__ import annotations

import logging
import pathlib

import pytest

## MUST keep it before any other py_fade imports, as they may rely on path changes.
from py_fade.features_checker import SUPPORTED_FEATURES

from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample


logger = logging.getLogger(__name__)


@pytest.mark.skipif(
    not SUPPORTED_FEATURES.get("sqlcipher3", False),
    reason="sqlcipher3 package is required for encryption tests",
)
@pytest.mark.usefixtures("ensure_google_icon_font")
def test_encrypt_decrypt_and_password_change(tmp_path: pathlib.Path) -> None:
    """Round-trip a dataset through encryption, decryption, and password change."""

    plain_path = tmp_path / "plain.db"
    dataset = DatasetDatabase(plain_path)
    dataset.initialize()

    prompt = PromptRevision.get_or_create(dataset, "Test prompt", 1024, 128)
    Sample.create_if_unique(dataset, "Sample 1", prompt)
    dataset.commit()

    encrypted_path = tmp_path / "encrypted-copy.db"
    logger.debug("Encrypting dataset copy to %s", encrypted_path)
    dataset.encrypt_copy(encrypted_path, "secret-pass")
    assert encrypted_path.exists()
    assert DatasetDatabase.check_db_type(encrypted_path) == "sqlcipher"

    dataset.dispose()

    encrypted_dataset = DatasetDatabase(encrypted_path, password="secret-pass")
    encrypted_dataset.initialize()
    prompts_after_encrypt = encrypted_dataset.get_prompts()
    assert prompts_after_encrypt, "Prompts should persist after encrypting"

    decrypted_path = tmp_path / "decrypted-copy.db"
    logger.debug("Saving unencrypted copy to %s", decrypted_path)
    encrypted_dataset.save_unencrypted_copy(decrypted_path)
    assert decrypted_path.exists()
    assert DatasetDatabase.check_db_type(decrypted_path) == "sqlite"

    logger.debug("Changing password for %s", encrypted_path)
    encrypted_dataset.change_password("new-secret")
    encrypted_dataset.dispose()

    reopened_dataset = DatasetDatabase(encrypted_path, password="new-secret")
    reopened_dataset.initialize()
    prompts_after_rekey = reopened_dataset.get_prompts()
    assert prompts_after_rekey, "Prompts should persist after password change"

    reopened_dataset.dispose()
