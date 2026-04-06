#!/usr/bin/env python3
"""
MathSpatial Benchmark Result Analyzer

Analyzes model evaluation results on MathSpatial-Bench, reporting accuracy
breakdowns by category, subcategory, and model.

Usage:
    python analyze_results.py --benchmark_dir ../benchmark
"""

import json
import os
import argparse
from collections import defaultdict


def load_question_data(question_dir):
    """Load data.json from a question directory."""
    data_path = os.path.join(question_dir, 'data.json')
    if os.path.exists(data_path):
        try:
            with open(data_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def load_result_data(question_dir, model_name):
    """Load a model's result file from a question directory."""
    result_path = os.path.join(question_dir, f'result_{model_name}.json')
    if os.path.exists(result_path):
        try:
            with open(result_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return None
    return None


def discover_models(benchmark_dir):
    """Auto-discover available models from result files."""
    models = set()
    for qdir in os.listdir(benchmark_dir):
        if not qdir.startswith('question'):
            continue
        qpath = os.path.join(benchmark_dir, qdir)
        for f in os.listdir(qpath):
            if f.startswith('result_') and f.endswith('.json'):
                model_name = f[len('result_'):-len('.json')]
                models.add(model_name)
    return sorted(models)


def analyze_benchmark(benchmark_dir, models=None):
    """Analyze benchmark results for specified models."""
    if models is None:
        models = discover_models(benchmark_dir)
        print(f"Discovered models: {models}")

    stats = {}
    for model in models:
        stats[model] = {
            'total_correct': 0,
            'total_questions': 0,
            'main_category_stats': defaultdict(lambda: {'correct': 0, 'total': 0}),
            'sub_category_stats': defaultdict(lambda: {'correct': 0, 'total': 0})
        }

    question_dirs = sorted([d for d in os.listdir(benchmark_dir) if d.startswith('question')])
    print(f"Found {len(question_dirs)} questions")

    for question_dir_name in question_dirs:
        question_dir_path = os.path.join(benchmark_dir, question_dir_name)
        question_data = load_question_data(question_dir_path)
        if not question_data:
            continue

        main_category = question_data.get('main_category', 'Unknown')
        sub_category = question_data.get('sub_category', 'Unknown')

        for model in models:
            result_data = load_result_data(question_dir_path, model)
            if result_data is not None:
                is_correct = result_data.get('is_correct', False)
                stats[model]['total_questions'] += 1
                if is_correct:
                    stats[model]['total_correct'] += 1
                stats[model]['main_category_stats'][main_category]['total'] += 1
                if is_correct:
                    stats[model]['main_category_stats'][main_category]['correct'] += 1
                stats[model]['sub_category_stats'][sub_category]['total'] += 1
                if is_correct:
                    stats[model]['sub_category_stats'][sub_category]['correct'] += 1

    return stats


def print_results(stats):
    """Print formatted analysis results."""
    models = list(stats.keys())

    print("\n" + "=" * 80)
    print("MathSpatial-Bench Evaluation Results")
    print("=" * 80)

    print("\n[Overall]")
    print(f"{'Model':<35} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
    print("-" * 65)
    for model in models:
        tc = stats[model]['total_correct']
        tq = stats[model]['total_questions']
        acc = tc / tq * 100 if tq > 0 else 0
        print(f"{model:<35} {tc:>8} {tq:>8} {acc:>9.2f}%")

    print("\n[By Main Category]")
    all_main_categories = set()
    for model in models:
        all_main_categories.update(stats[model]['main_category_stats'].keys())

    for category in sorted(all_main_categories):
        print(f"\n  {category}:")
        print(f"  {'Model':<35} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
        print("  " + "-" * 65)
        for model in models:
            s = stats[model]['main_category_stats'][category]
            acc = s['correct'] / s['total'] * 100 if s['total'] > 0 else 0
            print(f"  {model:<35} {s['correct']:>8} {s['total']:>8} {acc:>9.2f}%")

    print("\n[By Sub Category]")
    all_sub_categories = set()
    for model in models:
        all_sub_categories.update(stats[model]['sub_category_stats'].keys())

    for category in sorted(all_sub_categories):
        print(f"\n  {category}:")
        print(f"  {'Model':<35} {'Correct':>8} {'Total':>8} {'Accuracy':>10}")
        print("  " + "-" * 65)
        for model in models:
            s = stats[model]['sub_category_stats'][category]
            acc = s['correct'] / s['total'] * 100 if s['total'] > 0 else 0
            print(f"  {model:<35} {s['correct']:>8} {s['total']:>8} {acc:>9.2f}%")


def main():
    parser = argparse.ArgumentParser(description='Analyze MathSpatial benchmark results')
    parser.add_argument('--benchmark_dir', type=str, default='../benchmark',
                        help='Path to benchmark directory')
    parser.add_argument('--models', type=str, nargs='+', default=None,
                        help='Models to analyze (auto-discovered if not specified)')
    args = parser.parse_args()

    stats = analyze_benchmark(args.benchmark_dir, args.models)
    print_results(stats)


if __name__ == "__main__":
    main()
