#!/usr/bin/env python3
"""
Script to fix common pylint issues in test files.
"""
import re
import os
import sys
from pathlib import Path


def fix_file_issues(file_path):
    """Fix common issues in a test file."""
    print(f"Processing {file_path}")
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Fix trailing whitespace
    lines = content.split('\n')
    lines = [line.rstrip() for line in lines]
    
    # Ensure final newline
    if lines and lines[-1].strip():
        lines.append('')
    
    content = '\n'.join(lines)
    
    # Add module docstring if missing (for files without it)
    if not content.lstrip().startswith('"""') and not content.lstrip().startswith("'''"):
        # Find the import section to add docstring before it
        first_import = re.search(r'^(from __future__|import)', content, re.MULTILINE)
        if first_import:
            insert_pos = first_import.start()
            filename = os.path.basename(file_path)
            module_name = filename.replace('.py', '').replace('_', ' ').title()
            docstring = f'"""\n{module_name} test module.\n"""\n'
            content = content[:insert_pos] + docstring + content[insert_pos:]
    
    # Only write if there were changes
    if content != original_content:
        with open(file_path, 'w') as f:
            f.write(content)
        print(f"  Fixed trailing whitespace and newlines in {file_path}")
    
    return content != original_content


def main():
    test_dir = Path(__file__).parent
    
    changed_files = []
    for test_file in test_dir.glob('test_*.py'):
        if fix_file_issues(test_file):
            changed_files.append(test_file)
    
    if changed_files:
        print(f"\nFixed issues in {len(changed_files)} files:")
        for file in changed_files:
            print(f"  - {file}")
    else:
        print("\nNo changes needed.")


if __name__ == '__main__':
    main()