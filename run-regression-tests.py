import subprocess
import pathlib
import filecmp
import sys
import argparse
import shutil
import os
import fnmatch

def run_tests(program, test_root_dir, pattern=None, baseline_mode=False):
    program_path = pathlib.Path(program)
    if not program_path.exists():
        print(f"ERROR: Program {program} not found.")
        sys.exit(1)

    program_stem = program_path.stem  # e.g. fhir_llm_extract
    records_dir = pathlib.Path(test_root_dir)
    
    if not records_dir.exists():
        print(f"ERROR: Test root directory {test_root_dir} not found.")
        sys.exit(1)

    all_passed = True

    # Get all .txt files in the test directory
    all_txt_files = list(records_dir.rglob("*.txt"))
    
    # Filter files based on pattern if provided
    if pattern:
        filtered_files = []
        for infile in all_txt_files:
            # Get relative path from test_root_dir
            relative_path = infile.relative_to(records_dir)
            relative_path_str = str(relative_path).replace('\\', '/')  # Normalize path separators
            
            # Check if pattern contains wildcards
            if '*' in pattern or '?' in pattern:
                # Use fnmatch for wildcard patterns
                if fnmatch.fnmatch(relative_path_str, pattern):
                    filtered_files.append(infile)
            else:
                # Exact match for non-wildcard patterns
                if relative_path_str == pattern or relative_path_str == pattern.replace('\\', '/'):
                    filtered_files.append(infile)
        
        if not filtered_files:
            print(f"No files found matching pattern: {pattern}")
            return
        
        test_files = filtered_files
    else:
        test_files = all_txt_files

    for infile in test_files:
        # Build output/baseline filenames
        base = infile.with_suffix("")  # strip .txt
        outfile = pathlib.Path(str(base) + f"-{program_stem}.json")  # Programs always create this format
        baseline_file = pathlib.Path(str(base) + f"-{program_stem}-baseline.json")

        # Run program under test
        cmd = f"python {program} {infile}"
        print(f"\n> Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)

        if baseline_mode:
            # In baseline mode, copy the generated output to baseline file
            if outfile.exists():
                shutil.copy2(outfile, baseline_file)
                print(f"BASELINE: Created {baseline_file}")
            else:
                print(f"ERROR: Expected output file {outfile} not found")
            continue

        # In normal mode: compare against baseline if it exists
        if not baseline_file.exists():
            print(f"PASS (no baseline) for {infile.name}")
            continue

        if not filecmp.cmp(outfile, baseline_file, shallow=False):
            print(f"FAIL: {infile.name} differs from baseline")
            all_passed = False
        else:
            print(f"PASS: {infile.name}")

    if not baseline_mode:
        if all_passed:
            print("\nALL TESTS PASSED")
        else:
            print("\nSome tests FAILED. See messages above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regression test harness for FHIR extractors")
    parser.add_argument("program", help="Test program to run (e.g. fhir_regex_extract.py)")
    parser.add_argument("test_root_dir", help="Root directory containing test input *.txt files (e.g. records)")
    parser.add_argument("pattern", nargs="?", help="Optional pattern to filter test files (e.g. 'user-1/*.txt' or 'user-1/input-1-1.txt')")
    parser.add_argument("--baseline", action="store_true", help="Create/refresh baseline instead of normal output")
    args = parser.parse_args()

    run_tests(args.program, args.test_root_dir, args.pattern, baseline_mode=args.baseline)
