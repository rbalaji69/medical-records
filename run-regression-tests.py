import subprocess
import pathlib
import filecmp
import sys
import argparse
import shutil
import os

def run_tests(program, baseline_mode=False):
    program_path = pathlib.Path(program)
    if not program_path.exists():
        print(f"❌ Program {program} not found.")
        sys.exit(1)

    program_stem = program_path.stem  # e.g. fhir_llm_extract
    records_dir = pathlib.Path("records")

    all_passed = True

    for infile in records_dir.rglob("*.txt"):
        # Build output/baseline filenames
        base = infile.with_suffix("")  # strip .txt
        if baseline_mode:
            outfile = pathlib.Path(str(base) + f"-{program_stem}-baseline.json")
        else:
            outfile = pathlib.Path(str(base) + f"-{program_stem}.json")
        baseline_file = pathlib.Path(str(base) + f"-{program_stem}-baseline.json")

        # Run program under test
        cmd = f"python {program} {infile}"
        print(f"\n▶ Running: {cmd}")
        subprocess.run(cmd, shell=True, check=True)

        if baseline_mode:
            # In baseline mode, refresh baseline file
            if outfile.exists() and outfile != baseline_file:
                shutil.move(outfile, baseline_file)
                print(f"📌 Baseline refreshed: {baseline_file}")
            elif outfile == baseline_file:
                print(f"📌 Baseline created: {baseline_file}")
            continue

        # In normal mode: compare against baseline if it exists
        if not baseline_file.exists():
            print(f"✅ PASS (no baseline) for {infile.name}")
            continue

        if not filecmp.cmp(outfile, baseline_file, shallow=False):
            print(f"❌ FAIL: {infile.name} differs from baseline")
            all_passed = False
        else:
            print(f"✅ PASS: {infile.name}")

    if not baseline_mode:
        if all_passed:
            print("\n🎉 ALL TESTS PASSED")
        else:
            print("\n⚠️ Some tests FAILED. See messages above.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Regression test harness for FHIR extractors")
    parser.add_argument("program", help="Test program to run (e.g. fhir_regex_extract.py)")
    parser.add_argument("--baseline", action="store_true", help="Create/refresh baseline instead of normal output")
    args = parser.parse_args()

    run_tests(args.program, baseline_mode=args.baseline)
