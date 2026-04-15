#!/usr/bin/env python3
# Copyright 2026 CVS Health and/or one of its affiliates
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""CLI entry point for running BIRD benchmark evaluation against askRITA.

Usage:
    # Full benchmark (500 questions, Mini-Dev SQLite)
    python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o

    # Quick test on a single database (30 questions)
    python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --db-filter financial

    # Limit to N questions for cost control
    python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --limit 50

    # Without oracle knowledge (harder setting)
    python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --no-evidence

    # Evaluate existing predictions file
    python -m benchmarks.bird.run_benchmark --evaluate-only --predictions ./output/predictions.json

    # Resume from checkpoint
    python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --resume
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

# Ensure the project root is on the path
project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from benchmarks.bird.evaluate import BIRDEvaluator
from benchmarks.bird.runner import BenchmarkResult, BIRDBenchmarkRunner
from benchmarks.bird.setup_data import BIRDDatasetManager


class SafeLogFormatter(logging.Formatter):
    """Formatter that sanitizes log messages to prevent log injection (CRLF)."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return msg.replace("\n", "\\n").replace("\r", "\\r")


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO

    _handler = logging.StreamHandler(sys.stdout)
    _handler.setFormatter(
        SafeLogFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S"
        )
    )
    logging.basicConfig(level=level, handlers=[_handler])

    # Quiet down noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("langchain").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def progress_printer(current: int, total: int, result: BenchmarkResult):
    status = "OK" if result.success else "FAIL"
    print(
        f"  [{current:>4}/{total}] {status} | {result.db_id:<25} | "
        f"{result.difficulty:<12} | {result.latency_seconds:>6.1f}s | "
        f"{result.question[:60]}..."
    )


def _build_run_name(args, timestamp: str) -> str:
    """Derive a unique run name from args and timestamp."""
    if args.stratified:
        return f"{args.model}_stratified{args.stratified_size}_{timestamp}"
    if args.db_filter:
        return f"{args.model}_{args.db_filter}_{timestamp}"
    return f"{args.model}_{timestamp}"


def _collect_llm_overrides(args) -> dict:
    """Build the LLM config-overrides dict from CLI args."""
    overrides = {}
    if args.api_key:
        overrides["api_key"] = args.api_key
    if args.api_base:
        if args.provider == "azure_openai":
            overrides["azure_endpoint"] = args.api_base
        else:
            overrides["base_url"] = args.api_base
    if args.api_version:
        overrides["api_version"] = args.api_version
    if args.deployment_name:
        overrides["deployment_name"] = args.deployment_name
    if getattr(args, "project_id", None):
        overrides["project_id"] = args.project_id
    if getattr(args, "location", None):
        overrides["location"] = args.location
    if getattr(args, "credentials_path", None):
        overrides["credentials_path"] = args.credentials_path
    if getattr(args, "gcloud_cli_auth", False):
        overrides["gcloud_cli_auth"] = args.gcloud_cli_auth
    if args.ca_bundle:
        overrides["ca_bundle_path"] = str(Path(args.ca_bundle).resolve())
    return overrides


def _build_run_config(
    args, run_name, timestamp, generation_time, sampling_mode, questions_meta
) -> dict:
    """Build the run_config metadata dict written to the spreadsheet and summary JSON."""
    return {
        "Run Name": run_name,
        "Timestamp": timestamp,
        "Provider": args.provider,
        "Model": args.model,
        "Evidence (Oracle Knowledge)": "Yes" if not args.no_evidence else "No",
        "Database Filter": (
            "All (stratified)" if args.stratified else (args.db_filter or "All")
        ),
        "Sampling mode": sampling_mode,
        "Questions": questions_meta,
        "Total Time (s)": round(generation_time, 1),
    }


def _load_questions(args, dataset):
    """Load benchmark questions and return (questions, stratified_allocation).

    Prints progress to stdout. stratified_allocation is None for non-stratified runs.
    """
    stratified_allocation: Optional[Dict[str, int]] = None
    if args.stratified:
        questions, stratified_allocation = dataset.load_questions_stratified(
            total=args.stratified_size,
            seed=args.stratified_seed,
        )
        print(
            f"Loaded {len(questions)} stratified questions (seed={args.stratified_seed})"
        )
        print("Per-database allocation:")
        for db_id in sorted(stratified_allocation.keys()):
            print(f"  {db_id}: {stratified_allocation[db_id]}")
    else:
        questions = dataset.load_questions(db_filter=args.db_filter, limit=args.limit)
        print(f"Loaded {len(questions)} questions")
        if args.db_filter:
            print(f"Filtered to database: {args.db_filter}")
        if args.limit:
            print(f"Limited to {args.limit} questions")
    return questions, stratified_allocation


def _build_sampling_meta(args, stratified_allocation):
    """Return (sampling_mode_str, questions_meta_str) for display and logging."""
    if args.stratified:
        sampling_mode = (
            f"Stratified N={args.stratified_size}, seed={args.stratified_seed} "
            f"across {len(stratified_allocation or {})} databases"
        )
        return sampling_mode, sampling_mode
    sampling_mode = "Sequential from dataset"
    if args.limit:
        sampling_mode += f", limit {args.limit}"
    if args.db_filter:
        sampling_mode += f", db_filter={args.db_filter}"
    questions_meta = str(args.limit) if args.limit else "All (500)"
    return sampling_mode, questions_meta


def run_benchmark(args):
    """Run the full benchmark pipeline: setup -> generate -> evaluate."""
    # Set SSL env vars early — before any imports that open connections
    if args.ca_bundle:
        ca_path = str(Path(args.ca_bundle).resolve())
        os.environ["SSL_CERT_FILE"] = ca_path
        os.environ["REQUESTS_CA_BUNDLE"] = ca_path

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = _build_run_name(args, timestamp)

    output_dir = os.path.join(args.output_dir, run_name)
    os.makedirs(output_dir, exist_ok=True)

    # Phase 1: Dataset setup
    print("\n" + "=" * 70)
    print("Phase 1: Dataset Setup")
    print("=" * 70)

    dataset = BIRDDatasetManager(
        data_dir=args.data_dir,
        use_huggingface=not args.local_data,
    )

    if not dataset.setup():
        print(
            "\nDataset setup incomplete. The SQLite database files must be downloaded separately."
            "\nDownload from: https://drive.google.com/file/d/13VLWIwpw5E3d5DUkMvzw7hvHE67a4XkG/view"
            f"\nExtract dev_databases/ to: {dataset.db_dir}"
        )
        sys.exit(1)

    questions, stratified_allocation = _load_questions(args, dataset)

    # Phase 2: SQL Generation
    print("\n" + "=" * 70)
    print("Phase 2: SQL Generation via askRITA")
    print("=" * 70)
    print(f"Provider: {args.provider}")
    print(f"Model: {args.model}")
    print(f"Evidence (oracle knowledge): {'Yes' if not args.no_evidence else 'No'}")
    print(f"Output: {output_dir}")
    print()

    llm_overrides = _collect_llm_overrides(args)
    if args.ca_bundle:
        print(f"CA Bundle: {llm_overrides.get('ca_bundle_path', '')}")

    resume_path = None
    if args.resume:
        # Find the most recent directory matching this model
        base_run_name = _build_run_name(args, "").strip("_")
        existing_dirs = []
        if os.path.exists(args.output_dir):
            for d in os.listdir(args.output_dir):
                if d.startswith(base_run_name) and os.path.isdir(
                    os.path.join(args.output_dir, d)
                ):
                    existing_dirs.append(os.path.join(args.output_dir, d))

        if existing_dirs:
            latest_dir = sorted(existing_dirs)[-1]
            checkpoint = os.path.join(latest_dir, "predictions_checkpoint.json")
            if os.path.exists(checkpoint):
                resume_path = checkpoint
                print(f"Resuming from checkpoint: {checkpoint}")
                # Use the existing directory instead of creating a new one
                output_dir = latest_dir
                run_name = os.path.basename(latest_dir)

    runner = BIRDBenchmarkRunner(
        dataset_manager=dataset,
        llm_provider=args.provider,
        llm_model=args.model,
        llm_config_overrides=llm_overrides,
        output_dir=output_dir,
        include_evidence=not args.no_evidence,
        max_retries=args.max_retries,
        timeout_per_question=args.timeout,
        progress_callback=progress_printer,
    )

    start_time = time.time()
    results = runner.run(questions=questions, resume_from=resume_path)
    generation_time = time.time() - start_time

    summary = runner.get_results_summary()
    print(f"\nSQL Generation Summary:")
    print(f"  Total questions: {summary['total']}")
    print(
        f"  SQL generated:   {summary['success']} ({summary['sql_generation_rate']}%)"
    )
    print(f"  Failed:          {summary['failed']}")
    print(f"  Avg latency:     {summary['avg_latency_seconds']}s")
    print(f"  Total time:      {generation_time:.0f}s")

    # Phase 3: Evaluation
    print("\n" + "=" * 70)
    print("Phase 3: Execution Accuracy Evaluation")
    print("=" * 70)

    evaluator = BIRDEvaluator(
        db_root_path=dataset.db_dir,
        timeout=args.eval_timeout,
        num_workers=args.eval_workers,
    )

    report, eval_results = evaluator.evaluate_from_results(results, return_details=True)
    report.print_report()

    # Save everything
    report_path = os.path.join(output_dir, "evaluation_report.json")
    evaluator.save_report(report, report_path)

    sampling_mode, questions_meta = _build_sampling_meta(args, stratified_allocation)
    run_config = _build_run_config(
        args, run_name, timestamp, generation_time, sampling_mode, questions_meta
    )

    summary_path = os.path.join(output_dir, "run_summary.json")
    summary_payload: Dict[str, Any] = {
        "run_name": run_name,
        "timestamp": timestamp,
        "config": {
            "provider": args.provider,
            "model": args.model,
            "include_evidence": not args.no_evidence,
            "db_filter": args.db_filter,
            "limit": args.limit,
            "stratified": args.stratified,
            "stratified_size": args.stratified_size if args.stratified else None,
            "stratified_seed": args.stratified_seed if args.stratified else None,
            "max_retries": args.max_retries,
        },
        "generation_summary": summary,
        "evaluation": report.to_dict(),
        "total_time_seconds": round(generation_time, 1),
    }
    if args.stratified and stratified_allocation:
        summary_payload["stratified_allocation"] = stratified_allocation
    with open(summary_path, "w") as f:
        json.dump(summary_payload, f, indent=2)

    # Generate spreadsheet
    xlsx_path = os.path.join(output_dir, "benchmark_results.xlsx")
    evaluator.save_spreadsheet(eval_results, report, xlsx_path, run_config=run_config)

    print(f"\nAll results saved to: {output_dir}/")
    print(
        "  benchmark_results.xlsx - Spreadsheet: Summary, Per-Question, Per-DB, "
        "Baseline vs askRITA"
    )
    print(f"  predictions.json       - BIRD-format predictions (submit to leaderboard)")
    print(f"  detailed_results.json  - Per-question details with latency")
    print(f"  evaluation_report.json - EX and Soft F1 scores")
    print(f"  run_summary.json       - Complete run metadata")

    return report


def evaluate_only(args):
    """Evaluate an existing predictions file without running generation."""
    dataset = BIRDDatasetManager(data_dir=args.data_dir)

    if not os.path.exists(args.predictions):
        print(f"Predictions file not found: {args.predictions}")
        sys.exit(1)

    evaluator = BIRDEvaluator(
        db_root_path=dataset.db_dir,
        timeout=args.eval_timeout,
        num_workers=args.eval_workers,
    )

    report = evaluator.evaluate_from_predictions_file(
        predictions_path=args.predictions,
        gold_sql_path=dataset.gold_sql_file,
        difficulty_path=dataset.difficulty_file,
    )

    report.print_report()

    output_path = args.predictions.replace(".json", "_evaluation.json")
    evaluator.save_report(report, output_path)
    print(f"Report saved to: {output_path}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Run BIRD benchmark evaluation against askRITA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full Mini-Dev benchmark with GPT-4o
  python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o

  # Quick test on one database
  python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --db-filter financial

  # Azure OpenAI
  python -m benchmarks.bird.run_benchmark --provider azure_openai --model gpt-4o \\
    --api-base https://your-endpoint.openai.azure.com/ --deployment-name gpt-4o

  # Evaluate existing predictions
  python -m benchmarks.bird.run_benchmark --evaluate-only --predictions ./output/predictions.json

  # Cost-controlled run (10 questions)
  python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --limit 10

  # Stratified 100 questions across all 11 databases (Excel: Baseline vs askRITA sheet)
  python -m benchmarks.bird.run_benchmark --provider openai --model gpt-4o --stratified
""",
    )

    # Mode
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Only evaluate an existing predictions file (skip generation)",
    )

    # LLM configuration
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=["openai", "azure_openai", "vertex_ai", "bedrock"],
        help="LLM provider (default: openai)",
    )
    parser.add_argument(
        "--model", type=str, default="gpt-4o", help="LLM model name (default: gpt-4o)"
    )
    parser.add_argument(
        "--api-key", type=str, default=None, help="API key (defaults to env var)"
    )
    parser.add_argument(
        "--api-base", type=str, default=None, help="API base URL / Azure endpoint"
    )
    parser.add_argument(
        "--api-version", type=str, default=None, help="API version (Azure)"
    )
    parser.add_argument(
        "--deployment-name", type=str, default=None, help="Deployment name (Azure)"
    )
    parser.add_argument(
        "--project-id", type=str, default=None, help="GCP Project ID (Vertex AI)"
    )
    parser.add_argument(
        "--location", type=str, default="us-central1", help="GCP Location (Vertex AI)"
    )
    parser.add_argument(
        "--credentials-path",
        type=str,
        default=None,
        help="Path to GCP Service Account JSON (Vertex AI)",
    )
    parser.add_argument(
        "--gcloud-cli-auth", action="store_true", help="Use gcloud CLI auth (Vertex AI)"
    )
    parser.add_argument(
        "--ca-bundle",
        type=str,
        default=None,
        help="Path to CA bundle PEM file (e.g., Zscaler cert)",
    )

    # Benchmark scope
    parser.add_argument(
        "--db-filter",
        type=str,
        default=None,
        help="Only run questions for this database (e.g., 'financial')",
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Max number of questions to process"
    )
    parser.add_argument(
        "--stratified",
        action="store_true",
        help=(
            "Sample questions proportionally across every database (ignore --db-filter / --limit). "
            "Use with --stratified-size (default 100) for multi-schema coverage."
        ),
    )
    parser.add_argument(
        "--stratified-size",
        type=int,
        default=100,
        help="Total questions when --stratified (default: 100)",
    )
    parser.add_argument(
        "--stratified-seed",
        type=int,
        default=42,
        help="RNG seed for stratified sampling (default: 42)",
    )
    parser.add_argument(
        "--no-evidence",
        action="store_true",
        help="Don't include BIRD evidence/external knowledge in prompts",
    )

    # Execution settings
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Max SQL generation retries per question (default: 2)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Timeout per question in seconds (default: 120)",
    )
    parser.add_argument(
        "--resume", action="store_true", help="Resume from checkpoint if available"
    )

    # Evaluation settings
    parser.add_argument(
        "--eval-timeout",
        type=float,
        default=30.0,
        help="SQL execution timeout for evaluation (default: 30s)",
    )
    parser.add_argument(
        "--eval-workers",
        type=int,
        default=4,
        help="Parallel workers for evaluation (default: 4)",
    )

    # Paths
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./benchmarks/bird/data",
        help="BIRD dataset directory",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./benchmarks/bird/output",
        help="Output directory for results",
    )
    parser.add_argument(
        "--predictions",
        type=str,
        default=None,
        help="Path to predictions file (for --evaluate-only)",
    )
    parser.add_argument(
        "--local-data",
        action="store_true",
        help="Use local data only (don't download from HuggingFace)",
    )

    # General
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.stratified and args.db_filter:
        parser.error("--stratified cannot be combined with --db-filter")
    if args.stratified and args.limit is not None:
        parser.error(
            "--stratified cannot be combined with --limit (use --stratified-size)"
        )

    if args.evaluate_only:
        if not args.predictions:
            parser.error("--evaluate-only requires --predictions <path>")
        evaluate_only(args)
    else:
        run_benchmark(args)


if __name__ == "__main__":
    main()
