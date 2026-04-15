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

"""CLI entry point for running BIRD Mini-Interact benchmark against askRITA.

Usage:
    # Run full benchmark (300 tasks)
    python -m benchmarks.bird_interact --provider openai --model gpt-4o

    # Limit to N tasks for cost control
    python -m benchmarks.bird_interact --provider openai --model gpt-4o --limit 10

    # Filter by database
    python -m benchmarks.bird_interact --provider openai --model gpt-4o --db-filter financial

    # Specify user simulator model
    python -m benchmarks.bird_interact --provider openai --model gpt-4o --user-sim-model gpt-4o-mini

    # With ground-truth file for evaluation
    python -m benchmarks.bird_interact --provider openai --model gpt-4o --gt-path ./gt.jsonl

    # Evaluate existing results
    python -m benchmarks.bird_interact --evaluate-only --results ./output/detailed_results.jsonl
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

project_root = str(Path(__file__).resolve().parent.parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from benchmarks.bird_interact.evaluate import MiniInteractEvaluator
from benchmarks.bird_interact.runner import ConversationResult, MiniInteractRunner
from benchmarks.bird_interact.setup_data import MiniInteractDataManager
from benchmarks.bird_interact.user_simulator import UserSimulator, UserSimulatorConfig


class SafeLogFormatter(logging.Formatter):
    """Formatter that sanitizes log messages to prevent log injection (CRLF)."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        return msg.replace("\n", "\\n").replace("\r", "\\r")


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(
        SafeLogFormatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%H:%M:%S",
        )
    )
    logging.basicConfig(level=level, handlers=[handler])

    for name in ("httpx", "httpcore", "openai", "langchain", "urllib3"):
        logging.getLogger(name).setLevel(logging.WARNING)


def progress_printer(current: int, total: int, result: ConversationResult) -> None:
    status = "OK" if result.success else "FAIL"
    print(
        f"  [{current:>4}/{total}] {status} | {result.selected_database:<25} | "
        f"{result.num_turns:>2} turns | {result.latency_seconds:>6.1f}s | "
        f"{result.amb_user_query[:55]}..."
    )


def _collect_llm_overrides(args: argparse.Namespace) -> Dict[str, Any]:
    """Build the LLM config-overrides dict from CLI args."""
    overrides: Dict[str, Any] = {}
    if args.api_key:
        overrides["api_key"] = args.api_key
    if args.api_base:
        if args.provider == "azure_openai":
            overrides["azure_endpoint"] = args.api_base
        else:
            overrides["openai_api_base"] = args.api_base
    if args.api_version:
        overrides["api_version"] = args.api_version
    if args.deployment_name:
        overrides["deployment_name"] = args.deployment_name
    if args.ca_bundle:
        overrides["ca_bundle_path"] = str(Path(args.ca_bundle).resolve())
    return overrides


def run_benchmark(args: argparse.Namespace) -> None:
    """Run the full benchmark pipeline: setup → generate → evaluate."""
    if args.ca_bundle:
        ca_path = str(Path(args.ca_bundle).resolve())
        os.environ["SSL_CERT_FILE"] = ca_path
        os.environ["REQUESTS_CA_BUNDLE"] = ca_path

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_name = f"{args.model}_interact_{timestamp}"
    if args.db_filter:
        run_name = f"{args.model}_{args.db_filter}_interact_{timestamp}"

    output_dir = os.path.join(args.output_dir, run_name)
    os.makedirs(output_dir, exist_ok=True)

    # Phase 1: Dataset setup
    print("\n" + "=" * 70)
    print("Phase 1: Mini-Interact Dataset Setup")
    print("=" * 70)

    dataset = MiniInteractDataManager(data_dir=args.data_dir)

    if not dataset.setup():
        print(
            "\nDataset setup incomplete. Please ensure git and git-lfs are installed.\n"
            "Alternatively, manually clone:\n"
            "  git clone https://huggingface.co/datasets/birdsql/mini-interact\n"
            f"  into: {dataset.data_dir}"
        )
        sys.exit(1)

    if args.gt_path:
        print(f"Merging ground-truth from: {args.gt_path}")
        dataset.merge_ground_truth(args.gt_path)

    tasks = dataset.load_tasks(limit=args.limit, db_filter=args.db_filter)
    print(f"Loaded {len(tasks)} tasks")
    if args.db_filter:
        print(f"Filtered to database: {args.db_filter}")
    if args.limit:
        print(f"Limited to {args.limit} tasks")

    # Phase 2: Multi-turn SQL Generation
    print("\n" + "=" * 70)
    print("Phase 2: Multi-Turn SQL Generation via askRITA")
    print("=" * 70)
    print(f"System Provider: {args.provider}")
    print(f"System Model:    {args.model}")
    print(f"User Sim Model:  {args.user_sim_model}")
    print(f"Patience:        {args.patience}")
    print(f"Output:          {output_dir}")
    print()

    llm_overrides = _collect_llm_overrides(args)

    user_sim_config = UserSimulatorConfig(
        model=args.user_sim_model,
        temperature=0.3,
    )
    if args.ca_bundle:
        user_sim_config.ca_bundle_path = str(Path(args.ca_bundle).resolve())

    user_simulator = UserSimulator(config=user_sim_config)

    resume_path = None
    if args.resume:
        checkpoint = os.path.join(output_dir, "results_checkpoint.jsonl")
        if os.path.exists(checkpoint):
            resume_path = checkpoint
            print(f"Resuming from checkpoint: {checkpoint}")

    runner = MiniInteractRunner(
        dataset_manager=dataset,
        user_simulator=user_simulator,
        llm_provider=args.provider,
        llm_model=args.model,
        llm_config_overrides=llm_overrides,
        output_dir=output_dir,
        patience=args.patience,
        max_retries=args.max_retries,
        timeout_per_task=args.timeout,
        progress_callback=progress_printer,
    )

    start_time = time.time()
    results = runner.run(tasks=tasks, resume_from=resume_path)
    generation_time = time.time() - start_time

    summary = runner.get_results_summary()
    print(f"\nSQL Generation Summary:")
    print(f"  Total tasks:     {summary['total']}")
    print(
        f"  SQL generated:   {summary['success']} ({summary['sql_generation_rate']}%)"
    )
    print(f"  Failed:          {summary['failed']}")
    print(f"  Avg turns:       {summary['avg_turns']}")
    print(f"  Avg latency:     {summary['avg_latency_seconds']}s")
    print(f"  Total time:      {generation_time:.0f}s")

    # Phase 3: Evaluation
    print("\n" + "=" * 70)
    print("Phase 3: Test-Case Evaluation")
    print("=" * 70)

    evaluator = MiniInteractEvaluator(
        dataset_manager=dataset,
        timeout=args.eval_timeout,
    )

    report, eval_results = evaluator.evaluate(results, tasks)
    report.print_report()

    # Save everything
    report_path = os.path.join(output_dir, "evaluation_report.json")
    evaluator.save_report(report, report_path)

    run_config: Dict[str, Any] = {
        "Run Name": run_name,
        "Timestamp": timestamp,
        "Provider": args.provider,
        "System Model": args.model,
        "User Sim Model": args.user_sim_model,
        "Patience": args.patience,
        "Database Filter": args.db_filter or "All",
        "Limit": args.limit or "All (300)",
        "GT Available": report.has_ground_truth,
        "Total Time (s)": round(generation_time, 1),
    }

    summary_path = os.path.join(output_dir, "run_summary.json")
    summary_payload: Dict[str, Any] = {
        "run_name": run_name,
        "timestamp": timestamp,
        "config": {
            "provider": args.provider,
            "model": args.model,
            "user_sim_model": args.user_sim_model,
            "patience": args.patience,
            "db_filter": args.db_filter,
            "limit": args.limit,
            "max_retries": args.max_retries,
        },
        "generation_summary": summary,
        "evaluation": report.to_dict(),
        "total_time_seconds": round(generation_time, 1),
    }
    with open(summary_path, "w") as f:
        json.dump(summary_payload, f, indent=2, ensure_ascii=False)

    xlsx_path = os.path.join(output_dir, "benchmark_results.xlsx")
    evaluator.save_spreadsheet(
        eval_results, results, report, xlsx_path, run_config=run_config
    )

    print(f"\nAll results saved to: {output_dir}/")
    print("  benchmark_results.xlsx  - Spreadsheet: Summary, Per-Task, Conversations")
    print("  predictions.json        - Predicted SQL per task")
    print("  detailed_results.jsonl  - Per-task details with conversation")
    print("  evaluation_report.json  - Reward scores and test-case results")
    print("  run_summary.json        - Complete run metadata")


def evaluate_only(args: argparse.Namespace) -> None:
    """Evaluate existing results without running generation."""
    dataset = MiniInteractDataManager(data_dir=args.data_dir)

    if args.gt_path:
        dataset.merge_ground_truth(args.gt_path)

    tasks = dataset.load_tasks()

    if not os.path.exists(args.results):
        print(f"Results file not found: {args.results}")
        sys.exit(1)

    conversation_results: list[ConversationResult] = []
    with open(args.results, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            conversation_results.append(
                ConversationResult(
                    instance_id=entry["instance_id"],
                    selected_database=entry["selected_database"],
                    amb_user_query=entry.get("amb_user_query", ""),
                    predicted_sql=entry["predicted_sql"],
                    num_turns=entry.get("num_turns", 0),
                    debug_used=entry.get("debug_used", False),
                    latency_seconds=entry.get("latency_seconds", 0),
                    success=entry.get("success", False),
                )
            )

    evaluator = MiniInteractEvaluator(
        dataset_manager=dataset,
        timeout=args.eval_timeout,
    )

    report, eval_results = evaluator.evaluate(conversation_results, tasks)
    report.print_report()

    output_path = args.results.replace(".jsonl", "_evaluation.json")
    evaluator.save_report(report, output_path)
    print(f"Report saved to: {output_path}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run BIRD Mini-Interact benchmark against askRITA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full benchmark with GPT-4o
  python -m benchmarks.bird_interact --provider openai --model gpt-4o

  # Quick test (5 tasks)
  python -m benchmarks.bird_interact --provider openai --model gpt-4o --limit 5

  # Filter by database
  python -m benchmarks.bird_interact --provider openai --model gpt-4o --db-filter financial

  # With GT for evaluation
  python -m benchmarks.bird_interact --provider openai --model gpt-4o --gt-path ./gt.jsonl

  # Evaluate existing results
  python -m benchmarks.bird_interact --evaluate-only --results ./output/detailed_results.jsonl

  # Azure OpenAI
  python -m benchmarks.bird_interact --provider azure_openai --model gpt-4o \\
    --api-base https://your-endpoint.openai.azure.com/ --deployment-name gpt-4o
""",
    )

    # Mode
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="Only evaluate existing results (skip generation)",
    )

    # LLM configuration (system)
    parser.add_argument(
        "--provider",
        type=str,
        default="openai",
        choices=["openai", "azure_openai", "vertex_ai", "bedrock"],
        help="LLM provider for askRITA system (default: openai)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="gpt-4o",
        help="LLM model for askRITA system (default: gpt-4o)",
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
        "--ca-bundle",
        type=str,
        default=None,
        help="Path to CA bundle PEM file (e.g., Zscaler cert)",
    )

    # User simulator
    parser.add_argument(
        "--user-sim-model",
        type=str,
        default="gpt-4o",
        help="LLM model for user simulator (default: gpt-4o)",
    )

    # Benchmark scope
    parser.add_argument(
        "--limit", type=int, default=None, help="Max number of tasks to process"
    )
    parser.add_argument(
        "--db-filter", type=str, default=None, help="Only run tasks for this database"
    )
    parser.add_argument(
        "--patience",
        type=int,
        default=3,
        help="Extra turns beyond ambiguity count (default: 3)",
    )

    # Ground truth
    parser.add_argument(
        "--gt-path",
        type=str,
        default=None,
        help="Path to GT JSONL file (from BIRD team)",
    )

    # Execution settings
    parser.add_argument(
        "--max-retries",
        type=int,
        default=2,
        help="Max SQL generation retries (default: 2)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Timeout per task in seconds (default: 300)",
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

    # Paths
    parser.add_argument(
        "--data-dir",
        type=str,
        default="./benchmarks/bird_interact/data",
        help="Mini-Interact dataset directory",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="./benchmarks/bird_interact/output",
        help="Output directory for results",
    )
    parser.add_argument(
        "--results",
        type=str,
        default=None,
        help="Path to results JSONL file (for --evaluate-only)",
    )

    # General
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()
    setup_logging(args.verbose)

    if args.evaluate_only:
        if not args.results:
            parser.error("--evaluate-only requires --results <path>")
        evaluate_only(args)
    else:
        run_benchmark(args)


if __name__ == "__main__":
    main()
