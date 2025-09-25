"""
Generator for mockup data used in tests and UI previews.
"""
import datetime, os, sys, pathlib, logging, hashlib, argparse
from py_fade.dataset.dataset import DatasetDatabase
from py_fade.dataset.prompt import PromptRevision
from py_fade.dataset.sample import Sample


lorem_ipsum_text = "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua. Ut enim ad minim veniam, quis nostrud exercitation ullamco laboris nisi ut aliquip ex ea commodo consequat. Duis aute irure dolor in reprehenderit in voluptate velit esse cillum dolore eu fugiat nulla pariatur. Excepteur sint occaecat cupidatat non proident, sunt in culpa qui officia deserunt mollit anim id est laborum."

class TestDatasetGenerator:
    """
    Generator for test datasets, providing clean, deterministic data.
    """
    def __init__(self, dataset: "DatasetDatabase"):
        self.log = logging.getLogger("TestDatasetGenerator")
        self.dataset = dataset

    def fill_dataset(self):
        self.log.info(f"Filling dataset {self.dataset} with mockup data.")


if __name__ == "__main__":
    # As a standalone script, create a test database with mockup data at specified path
    parser = argparse.ArgumentParser(description="Generate mockup test database for pyFade.")
    parser.add_argument("--db-path", type=str, required=True, help="Path to create the mockup test database.")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    parser.add_argument("--force", action="store_true", help="Force overwrite if database file exists.")

    logging.basicConfig(level=logging.DEBUG)

    args = parser.parse_args()

    test_db_path = pathlib.Path(args.db_path)
    if test_db_path.exists():
        if args.force:
            print(f"Force removing existing database at {test_db_path}.")
            os.remove(test_db_path)
        else:
            print(f"Database path {test_db_path} already exists!")
            sys.exit(1)
    dataset = DatasetDatabase(test_db_path)
    dataset.initialize()
    generator = TestDatasetGenerator(dataset)
    generator.fill_dataset()
    dataset.commit()
    dataset.session.close()
    print(f"Mockup test database created at {test_db_path}")