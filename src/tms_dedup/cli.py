"""Typer CLI orchestrator."""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import typer
from rich.console import Console

from tms_dedup import (
    batch_pairs,
    candidates,
    classify_heuristic,
    classify_merge,
    cluster,
    config,
    features,
    io_utils,
    merge_verdicts,
    parse,
    report,
)

app = typer.Typer(add_completion=False, help="TMS test duplicate detector — qwen CLI skill")
console = Console()


@app.command(name="parse")
def cmd_parse(
    input_path: Path = typer.Option(config.INPUT_TSV, "--input", "-i"),
    section_sep: str = typer.Option(config.SECTION_SEP, "--section-sep"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Stage 1: read the TSV and produce canonical JSON artifacts."""
    config.seed_everything()
    config.ensure_dirs()
    parse.run(input_path=input_path, section_sep=section_sep, force=force)
    console.print(
        f"[green]Wrote[/green] {config.TESTS_JSON.relative_to(config.ROOT)} "
        f"and {config.SECTIONS_JSON.relative_to(config.ROOT)}"
    )


@app.command(name="classify-auto")
def cmd_classify_auto(force: bool = typer.Option(False, "--force")) -> None:
    """Stage 2a: heuristic section classification."""
    config.ensure_dirs()
    classify_heuristic.run(force=force)
    amb = io_utils.read_json(config.SECTIONS_AMBIGUOUS_JSON)
    clf = io_utils.read_json(config.SECTIONS_CLASSIFIED_JSON)
    console.print(
        f"[green]Classified[/green] {clf['count']} confidently, "
        f"[yellow]{amb['count']} ambiguous[/yellow] -> {config.SECTIONS_AMBIGUOUS_JSON.relative_to(config.ROOT)}"
    )
    if amb["count"] > 0:
        console.print(
            "[cyan]Next:[/cyan] the qwen agent should classify each ambiguous entry using "
            "prompts/classify_section.md and write the results to "
            f"{config.SECTIONS_LLM_JSON.relative_to(config.ROOT)}."
        )


@app.command(name="classify-merge")
def cmd_classify_merge(force: bool = typer.Option(False, "--force")) -> None:
    """Stage 2b merge: combine heuristic + LLM classifications into the final artifact."""
    config.ensure_dirs()
    classify_merge.run(force=force)
    console.print(
        f"[green]Merged[/green] -> {config.SECTIONS_FINAL_JSON.relative_to(config.ROOT)}"
    )


@app.command(name="features")
def cmd_features(force: bool = typer.Option(False, "--force")) -> None:
    """Stage 3: per-test feature extraction (normalized name + transfer_type_set)."""
    config.ensure_dirs()
    features.run(force=force)
    console.print(f"[green]Wrote[/green] {config.TEST_FEATURES_JSON.relative_to(config.ROOT)}")


@app.command(name="candidates")
def cmd_candidates(force: bool = typer.Option(False, "--force")) -> None:
    """Stage 4: candidate pair discovery."""
    config.seed_everything()
    config.ensure_dirs()
    candidates.run(force=force)
    data = io_utils.read_json(config.CANDIDATES_JSON)
    console.print(
        f"[green]Wrote[/green] {config.CANDIDATES_JSON.relative_to(config.ROOT)} — "
        f"{data['count']} candidate pairs"
    )


@app.command(name="batch-pairs")
def cmd_batch_pairs() -> None:
    """Stage 5 prep: split candidates into batches for the qwen agent."""
    config.ensure_dirs()
    batch_pairs.run()
    progress = io_utils.read_json(config.BATCHES_PROGRESS_JSON)
    console.print(
        f"[green]Created[/green] {progress['total_batches']} batch file(s) "
        f"in {config.BATCHES_DIR.relative_to(config.ROOT)}; the qwen agent must "
        f"write verdict JSONL files to {config.VERDICTS_DIR.relative_to(config.ROOT)}."
    )


@app.command(name="merge-verdicts")
def cmd_merge_verdicts() -> None:
    """Stage 5 merge: concatenate per-batch JSONL verdicts into the final verdicts artifact."""
    config.ensure_dirs()
    merge_verdicts.run()
    console.print(f"[green]Wrote[/green] {config.VERDICTS_JSON.relative_to(config.ROOT)}")


@app.command(name="cluster")
def cmd_cluster(force: bool = typer.Option(False, "--force")) -> None:
    """Stage 6a: cluster into duplicate groups."""
    config.ensure_dirs()
    cluster.run(force=force)
    console.print(f"[green]Wrote[/green] {config.CLUSTERS_JSON.relative_to(config.ROOT)}")


@app.command(name="report")
def cmd_report() -> None:
    """Stage 6b: render the final Markdown report."""
    config.ensure_dirs()
    report.run()
    console.print(f"[green]Wrote[/green] {config.REPORT_MD.relative_to(config.ROOT)}")


@app.command(name="run-all")
def cmd_run_all(
    input_path: Path = typer.Option(config.INPUT_TSV, "--input", "-i"),
    section_sep: str = typer.Option(config.SECTION_SEP, "--section-sep"),
    force: bool = typer.Option(False, "--force"),
) -> None:
    """Run every stage sequentially. Stops and prints agent instructions when LLM work is required."""
    config.seed_everything()
    config.ensure_dirs()
    parse.run(input_path=input_path, section_sep=section_sep, force=force)
    classify_heuristic.run(force=force)
    amb = io_utils.read_json(config.SECTIONS_AMBIGUOUS_JSON)
    if amb["count"] > 0 and not config.SECTIONS_LLM_JSON.exists():
        console.print(
            f"[yellow]Stop:[/yellow] {amb['count']} ambiguous section(s) need LLM classification. "
            f"Read {config.SECTIONS_AMBIGUOUS_JSON.relative_to(config.ROOT)}, apply "
            "prompts/classify_section.md, and write results to "
            f"{config.SECTIONS_LLM_JSON.relative_to(config.ROOT)}. Then rerun run-all."
        )
        raise typer.Exit(code=0)
    classify_merge.run(force=force)
    features.run(force=force)
    candidates.run(force=force)
    batch_pairs.run()
    progress = io_utils.read_json(config.BATCHES_PROGRESS_JSON)
    pending_batches = [
        b for b in progress["batches"] if not (config.ROOT / b["verdict_file"]).exists()
    ]
    if pending_batches:
        console.print(
            f"[yellow]Stop:[/yellow] {len(pending_batches)} batch(es) await LLM arbitration. "
            f"Process each {config.BATCHES_DIR.relative_to(config.ROOT)}/batch_NNNN.json "
            "using prompts/arbitrate_pair.md and write JSONL verdicts to "
            f"{config.VERDICTS_DIR.relative_to(config.ROOT)}/batch_NNNN.jsonl. Then rerun run-all."
        )
        raise typer.Exit(code=0)
    merge_verdicts.run()
    cluster.run(force=force)
    report.run()
    console.print(f"[green]Done.[/green] Report: {config.REPORT_MD.relative_to(config.ROOT)}")


@app.command(name="clean")
def cmd_clean(deep: bool = typer.Option(False, "--deep", help="Also drop the lemma cache.")) -> None:
    """Remove artifacts/ and the generated report; keep data/."""
    if config.ARTIFACTS_DIR.exists():
        if deep:
            shutil.rmtree(config.ARTIFACTS_DIR)
        else:
            # Preserve lemma_cache.json unless --deep.
            for p in config.ARTIFACTS_DIR.iterdir():
                if p.name == config.LEMMA_CACHE_JSON.name:
                    continue
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
    if config.REPORT_MD.exists():
        config.REPORT_MD.unlink()
    console.print("[green]Cleaned.[/green]")


if __name__ == "__main__":
    sys.exit(app())
