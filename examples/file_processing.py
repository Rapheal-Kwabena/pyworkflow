"""Example: File Processing workflow illustrating directory scanning, transformation, and output."""

import os
import pathlib
import shutil
import tempfile
from pyworkflow import workflow, task


@task
def scan_directory(directory: str) -> list[str]:
    """Scan a directory and return all text file paths."""
    print(f"Scanning directory: {directory}")
    files = [
        str(p)
        for p in pathlib.Path(directory).rglob("*.txt")
        if p.is_file()
    ]
    print(f"  Found {len(files)} .txt file(s)")
    return files


@task
def process_files(file_paths: list[str]) -> list[dict]:
    """Read each file and extract basic statistics."""
    print("Processing files...")
    results = []
    for path in file_paths:
        try:
            text = pathlib.Path(path).read_text(encoding="utf-8", errors="ignore")
            results.append({
                "path": path,
                "size_bytes": os.path.getsize(path),
                "lines": text.count("\n") + 1,
                "words": len(text.split()),
                "chars": len(text),
            })
            print(f"  Processed: {os.path.basename(path)} "
                  f"({results[-1]['words']} words)")
        except Exception as exc:
            print(f"  Skipped {path}: {exc}")
    return results


@task
def write_summary(processed_files: list[dict], output_dir: str) -> str:
    """Write a summary report to the output directory."""
    print(f"Writing summary to: {output_dir}")
    pathlib.Path(output_dir).mkdir(parents=True, exist_ok=True)
    summary_path = os.path.join(output_dir, "summary.txt")

    total_words = sum(f["words"] for f in processed_files)
    total_lines = sum(f["lines"] for f in processed_files)
    total_bytes = sum(f["size_bytes"] for f in processed_files)

    lines = [
        "FILE PROCESSING SUMMARY",
        "=" * 40,
        f"Files processed : {len(processed_files)}",
        f"Total words     : {total_words}",
        f"Total lines     : {total_lines}",
        f"Total bytes     : {total_bytes}",
        "",
        "Individual Files:",
    ]
    for f in processed_files:
        lines.append(
            f"  {os.path.basename(f['path'])}: "
            f"{f['words']} words, {f['lines']} lines"
        )

    pathlib.Path(summary_path).write_text("\n".join(lines))
    print(f"Summary written to: {summary_path}")
    return summary_path


def _create_sample_files(directory: str) -> None:
    """Helper: create sample .txt files for the demo."""
    pathlib.Path(directory).mkdir(parents=True, exist_ok=True)
    sample_texts = {
        "report_jan.txt": "January sales were up 12 percent.\nCustomer retention improved significantly.\n",
        "report_feb.txt": "February saw record web traffic.\nNew product launch was a success.\nReturns remained under 3 percent.\n",
        "notes.txt": "Meeting scheduled for Monday.\nReview Q1 roadmap.\nCheck with ops team on capacity.\n",
    }
    for name, content in sample_texts.items():
        pathlib.Path(os.path.join(directory, name)).write_text(content)


if __name__ == "__main__":
    # Create a temporary working environment
    tmp = tempfile.mkdtemp(prefix="pyworkflow_fileproc_")
    input_dir = os.path.join(tmp, "input")
    output_dir = os.path.join(tmp, "output")

    _create_sample_files(input_dir)

    # Build the workflow with static args
    from pyworkflow.core.task import Task

    flow = workflow("File Processing Workflow")

    t_scan = Task("scan_directory", scan_directory.fn, args=(input_dir,))
    t_process = Task("process_files", process_files.fn, depends_on=["scan_directory"])
    t_write = Task(
        "write_summary",
        write_summary.fn,
        depends_on=["process_files"],
        kwargs={"output_dir": output_dir},
    )

    flow.add_task(t_scan)
    flow.add_task(t_process)
    flow.add_task(t_write)

    print("Running File Processing Workflow...")
    report = flow.run()
    print(f"\nWorkflow success: {report.success}")

    if report.success:
        summary_path = report.results.get("write_summary")
        if summary_path and os.path.exists(summary_path):
            print("\n--- Summary Output ---")
            print(pathlib.Path(summary_path).read_text())

    # Cleanup temp directory
    shutil.rmtree(tmp, ignore_errors=True)
