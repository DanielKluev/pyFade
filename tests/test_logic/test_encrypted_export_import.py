"""
Test encrypted export and import functionality.

Tests the new encrypted ZIP export/import features using pyzipper.
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import tempfile
import zipfile
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest
import pyzipper

from py_fade.controllers.export_controller import ExportController
from py_fade.controllers.import_controller import ImportController
from py_fade.dataset.export_template import ExportTemplate
from py_fade.dataset.facet import Facet
from py_fade.dataset.sample import Sample
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.completion import PromptCompletion
from py_fade.dataset.completion_rating import PromptCompletionRating
from py_fade.dataset.completion_logprobs import PromptCompletionLogprobs
from py_fade.data_formats.base_data_classes import CompletionTopLogprobs
from py_fade.data_formats.share_gpt_format import ShareGPTFormat

if TYPE_CHECKING:
    from py_fade.dataset.dataset import DatasetDatabase
    from py_fade.app import pyFadeApp


def create_test_sample_with_completion(dataset: "DatasetDatabase", facet: Facet, model_id: str = "test-model") -> Sample:
    """
    Create a test sample with a rated completion for testing export.
    """
    # Create a prompt revision
    prompt_rev = PromptRevision.get_or_create(dataset, "What is 2+2?", 2048, 512)

    # Create a sample
    sample = Sample.create_if_unique(dataset, "Test Sample", prompt_rev, "test")
    dataset.commit()

    # Create a completion
    completion_text = "The answer is 4."
    sha256 = hashlib.sha256(completion_text.encode("utf-8")).hexdigest()
    completion = PromptCompletion(sha256=sha256, prompt_revision_id=prompt_rev.id, model_id=model_id, temperature=0.7, top_k=40,
                                  completion_text=completion_text, tags={}, prefill=None, beam_token=None, is_truncated=False,
                                  context_length=2048, max_tokens=512)
    dataset.session.add(completion)
    dataset.commit()

    # Add rating
    PromptCompletionRating.set_rating(dataset, completion, facet, 10)
    dataset.commit()

    # Add logprobs - construct manually with very permissive values
    alternative_logprobs_bin = PromptCompletionLogprobs.compress_alternative_logprobs(CompletionTopLogprobs())
    # pylint: disable=unexpected-keyword-arg,no-value-for-parameter
    # SQLAlchemy ORM constructor accepts mapped columns as keyword arguments
    logprobs = PromptCompletionLogprobs(prompt_completion_id=completion.id, logprobs_model_id=model_id, sampled_logprobs=None,
                                        sampled_logprobs_json=None, alternative_logprobs=None,
                                        alternative_logprobs_bin=alternative_logprobs_bin, min_logprob=0.0, avg_logprob=0.0)
    # pylint: enable=unexpected-keyword-arg,no-value-for-parameter
    dataset.session.add(logprobs)
    dataset.commit()

    return sample


class TestEncryptedExport:
    """
    Test encrypted export functionality.
    """

    def test_export_encrypted_with_password_jsonl(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that export with encryption enabled creates an encrypted ZIP file.
        
        Flow:
        1. Create facet and sample with completion
        2. Create export template with encryption enabled and password
        3. Run export
        4. Verify encrypted ZIP file is created
        5. Verify plaintext file was not created
        6. Verify ZIP can be decrypted with correct password
        """
        # Create facet and sample
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet", min_rating=5, min_logprob_threshold=-1.0, avg_logprob_threshold=-1.0)
        temp_dataset.commit()

        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        _ = create_test_sample_with_completion(temp_dataset, facet, mapped_model.model_id)

        # Create export template with encryption
        template = ExportTemplate.create(temp_dataset, name="Encrypted Test", description="Test encrypted export", training_type="SFT",
                                         output_format="JSONL-ShareGPT", model_families=["Llama3"], filename_template="export_{name}.jsonl",
                                         normalize_style=False, encrypt=True, encryption_password="testpassword123", facets=[{
                                             "facet_id": facet.id,
                                             "order": "random",
                                             "limit_type": "percentage",
                                             "limit_value": 100
                                         }])
        temp_dataset.commit()

        # Create export controller
        controller = ExportController(app_with_dataset, temp_dataset, template)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = pathlib.Path(tmpdir) / "test_export.jsonl"
            controller.set_output_path(output_path)

            # Run export
            exported_count = controller.run_export()

            assert exported_count == 1

            # Check that encrypted ZIP was created (controller may have added .zip extension)
            expected_zip_path = pathlib.Path(tmpdir) / "test_export.jsonl.zip"
            assert expected_zip_path.exists(), f"Encrypted ZIP not found at {expected_zip_path}"

            # Check that plaintext JSONL was NOT created
            assert not output_path.exists(), "Plaintext file should not exist when encryption is enabled"

            # Verify we can decrypt with correct password
            with pyzipper.AESZipFile(expected_zip_path, 'r') as zf:
                zf.setpassword(b'testpassword123')
                file_list = zf.namelist()
                assert len(file_list) == 1
                assert file_list[0].endswith('.jsonl')

                # Decrypt and verify content
                decrypted_data = zf.read(file_list[0])
                assert b'Test Sample' in decrypted_data or b'What is 2+2?' in decrypted_data

    def test_export_encrypted_with_password_json(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test encrypted export with JSON format.
        """
        # Create facet and sample
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet", min_rating=5, min_logprob_threshold=-1.0, avg_logprob_threshold=-1.0)
        temp_dataset.commit()

        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        _ = create_test_sample_with_completion(temp_dataset, facet, mapped_model.model_id)

        # Create export template with encryption (JSON format)
        template = ExportTemplate.create(temp_dataset, name="Encrypted JSON Test", description="Test encrypted JSON export",
                                         training_type="SFT", output_format="JSON", model_families=["Llama3"],
                                         filename_template="export_{name}.json", normalize_style=False, encrypt=True,
                                         encryption_password="jsonpassword", facets=[{
                                             "facet_id": facet.id,
                                             "order": "random",
                                             "limit_type": "percentage",
                                             "limit_value": 100
                                         }])
        temp_dataset.commit()

        # Create export controller
        controller = ExportController(app_with_dataset, temp_dataset, template)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = pathlib.Path(tmpdir) / "test_export.json"
            controller.set_output_path(output_path)

            # Run export
            exported_count = controller.run_export()

            assert exported_count == 1

            # Check that encrypted ZIP was created
            expected_zip_path = pathlib.Path(tmpdir) / "test_export.json.zip"
            assert expected_zip_path.exists()

            # Check that plaintext JSON was NOT created
            assert not output_path.exists()

            # Verify decryption
            with pyzipper.AESZipFile(expected_zip_path, 'r') as zf:
                zf.setpassword(b'jsonpassword')
                file_list = zf.namelist()
                assert len(file_list) == 1
                assert file_list[0].endswith('.json')

    def test_export_encrypted_wrong_password_fails(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that encrypted export cannot be decrypted with wrong password.
        """
        # Create facet and sample
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet", min_rating=5, min_logprob_threshold=-1.0, avg_logprob_threshold=-1.0)
        temp_dataset.commit()

        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        _ = create_test_sample_with_completion(temp_dataset, facet, mapped_model.model_id)

        # Create export template with encryption
        template = ExportTemplate.create(temp_dataset, name="Encrypted Test", description="Test", training_type="SFT",
                                         output_format="JSONL-ShareGPT", model_families=["Llama3"], filename_template="export.jsonl",
                                         normalize_style=False, encrypt=True, encryption_password="correctpassword", facets=[{
                                             "facet_id": facet.id,
                                             "order": "random",
                                             "limit_type": "percentage",
                                             "limit_value": 100
                                         }])
        temp_dataset.commit()

        controller = ExportController(app_with_dataset, temp_dataset, template)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = pathlib.Path(tmpdir) / "test_export.jsonl"
            controller.set_output_path(output_path)
            controller.run_export()

            expected_zip_path = pathlib.Path(tmpdir) / "test_export.jsonl.zip"

            # Try to decrypt with wrong password
            with pytest.raises(RuntimeError, match="Bad password"):
                with pyzipper.AESZipFile(expected_zip_path, 'r') as zf:
                    zf.setpassword(b'wrongpassword')
                    zf.read(zf.namelist()[0])

    def test_export_unencrypted_still_works(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that export without encryption still works correctly.
        """
        # Create facet and sample
        facet = Facet.create(temp_dataset, "Test Facet", "Test facet", min_rating=5, min_logprob_threshold=-1.0, avg_logprob_threshold=-1.0)
        temp_dataset.commit()

        mapped_model = app_with_dataset.providers_manager.get_mock_model()
        _ = create_test_sample_with_completion(temp_dataset, facet, mapped_model.model_id)

        # Create export template WITHOUT encryption
        template = ExportTemplate.create(temp_dataset, name="Unencrypted Test", description="Test unencrypted export", training_type="SFT",
                                         output_format="JSONL-ShareGPT", model_families=["Llama3"], filename_template="export.jsonl",
                                         normalize_style=False, encrypt=False, encryption_password=None, facets=[{
                                             "facet_id": facet.id,
                                             "order": "random",
                                             "limit_type": "percentage",
                                             "limit_value": 100
                                         }])
        temp_dataset.commit()

        controller = ExportController(app_with_dataset, temp_dataset, template)

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = pathlib.Path(tmpdir) / "test_export.jsonl"
            controller.set_output_path(output_path)

            # Run export
            exported_count = controller.run_export()

            assert exported_count == 1

            # Check that plaintext file was created (not encrypted)
            assert output_path.exists()

            # Check that no ZIP file was created
            zip_path = pathlib.Path(tmpdir) / "test_export.jsonl.zip"
            assert not zip_path.exists()

            # Verify we can read the plaintext file
            sharegpt = ShareGPTFormat(output_path)
            count = sharegpt.load()
            assert count == 1


class TestEncryptedImport:
    """
    Test encrypted import functionality.
    """

    def test_import_encrypted_zip_with_correct_password(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that encrypted ZIP files can be imported with correct password.
        
        Flow:
        1. Create an encrypted ZIP file with test data
        2. Import the encrypted ZIP
        3. Verify data was imported correctly
        """
        # Create test data in memory
        test_data = {
            "pyfade_version": "0.0.1",
            "format_version": "1.0",
            "facet": {
                "name": "TestFacet",
                "description": "Test",
                "min_rating": 5,
                "min_logprob_threshold": -1.0,
                "avg_logprob_threshold": -1.0
            },
            "tags": [],
            "samples": [],
            "completions": [],
            "ratings": []
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create encrypted ZIP
            zip_path = pathlib.Path(tmpdir) / "encrypted_data.zip"
            with pyzipper.AESZipFile(zip_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(b'importpassword')
                zf.writestr('test_data.json', json.dumps(test_data))

            # Import the encrypted ZIP
            controller = ImportController(app_with_dataset, temp_dataset)

            # Mock the password input dialog
            with patch('PyQt6.QtWidgets.QInputDialog.getText', return_value=('importpassword', True)):
                _ = controller.add_source(zip_path)

            # Verify the source was added
            assert len(controller.sources) == 1

    def test_import_encrypted_zip_wrong_password_fails(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that importing encrypted ZIP with wrong password fails.
        """

        test_data = {
            "pyfade_version": "0.0.1",
            "format_version": "1.0",
            "facet": {
                "name": "Test",
                "description": "Test",
                "min_rating": 5,
                "min_logprob_threshold": -1.0,
                "avg_logprob_threshold": -1.0
            },
            "tags": [],
            "samples": [],
            "completions": [],
            "ratings": []
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            zip_path = pathlib.Path(tmpdir) / "encrypted_data.zip"
            with pyzipper.AESZipFile(zip_path, 'w', compression=pyzipper.ZIP_DEFLATED, encryption=pyzipper.WZ_AES) as zf:
                zf.setpassword(b'correctpassword')
                zf.writestr('test_data.json', json.dumps(test_data))

            controller = ImportController(app_with_dataset, temp_dataset)

            # Mock the password input dialog with wrong password
            with patch('PyQt6.QtWidgets.QInputDialog.getText', return_value=('wrongpassword', True)):
                with pytest.raises(ValueError, match="Incorrect password"):
                    controller.add_source(zip_path)

    def test_import_unencrypted_zip_still_works(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that unencrypted ZIP files can still be imported.
        """

        test_data = {
            "pyfade_version": "0.0.1",
            "format_version": "1.0",
            "facet": {
                "name": "Test",
                "description": "Test",
                "min_rating": 5,
                "min_logprob_threshold": -1.0,
                "avg_logprob_threshold": -1.0
            },
            "tags": [],
            "samples": [],
            "completions": [],
            "ratings": []
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create unencrypted ZIP
            zip_path = pathlib.Path(tmpdir) / "unencrypted_data.zip"
            with zipfile.ZipFile(zip_path, 'w') as zf:
                zf.writestr('test_data.json', json.dumps(test_data))

            controller = ImportController(app_with_dataset, temp_dataset)

            # Import unencrypted ZIP (should not prompt for password)
            _ = controller.add_source(zip_path)

            # Verify the source was added
            assert len(controller.sources) == 1

    def test_import_non_zip_file_still_works(self, temp_dataset: "DatasetDatabase", app_with_dataset: "pyFadeApp"):
        """
        Test that regular JSON files (non-ZIP) still work.
        """

        test_data = {
            "pyfade_version": "0.0.1",
            "format_version": "1.0",
            "facet": {
                "name": "Test",
                "description": "Test",
                "min_rating": 5,
                "min_logprob_threshold": -1.0,
                "avg_logprob_threshold": -1.0
            },
            "tags": [],
            "samples": [],
            "completions": [],
            "ratings": []
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create regular JSON file
            json_path = pathlib.Path(tmpdir) / "test_data.json"
            json_path.write_text(json.dumps(test_data))

            controller = ImportController(app_with_dataset, temp_dataset)

            # Import regular JSON file
            _ = controller.add_source(json_path)

            # Verify the source was added
            assert len(controller.sources) == 1
