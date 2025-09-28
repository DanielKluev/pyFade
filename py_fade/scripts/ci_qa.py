"""
Unified CI command that runs pytest and pylint together.
"""

import subprocess
import sys
import os


def main():
    """
    Run unified CI quality assurance checks.

    Executes pytest followed by pylint on py_fade and tests packages.
    Returns non-zero exit code if any check fails.
    """
    print("Starting pyFade CI Quality Assurance checks...")

    # Change to the project root directory
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    os.chdir(project_root)

    exit_code = 0

    # Run pytest
    print("\n" + "=" * 60)
    print("Running pytest tests...")
    print("=" * 60)

    pytest_result = subprocess.run([sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"], check=False)

    if pytest_result.returncode != 0:
        print("❌ pytest failed!")
        exit_code = 1
    else:
        print("✅ pytest passed!")

    # Run pylint on main package
    print("\n" + "=" * 60)
    print("Running pylint on py_fade package...")
    print("=" * 60)

    pylint_main_result = subprocess.run([sys.executable, "-m", "pylint", "py_fade", "--score=yes"], check=False)

    if pylint_main_result.returncode != 0:
        print("❌ pylint failed on py_fade package!")
        exit_code = 1
    else:
        print("✅ pylint passed on py_fade package!")

    # Run pylint on tests
    print("\n" + "=" * 60)
    print("Running pylint on tests...")
    print("=" * 60)

    pylint_tests_result = subprocess.run([sys.executable, "-m", "pylint", "tests", "--score=yes"], check=False)

    if pylint_tests_result.returncode != 0:
        print("❌ pylint failed on tests!")
        exit_code = 1
    else:
        print("✅ pylint passed on tests!")

    # Summary
    print("\n" + "=" * 60)
    if exit_code == 0:
        print("🎉 All CI quality assurance checks passed!")
    else:
        print("❌ Some CI quality assurance checks failed!")
    print("=" * 60)

    sys.exit(exit_code)


if __name__ == "__main__":
    main()
