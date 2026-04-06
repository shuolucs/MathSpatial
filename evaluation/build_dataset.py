#!/usr/bin/env python3
"""
MathSpatial Dataset Construction Script

This script performs benchmark/corpus splitting with iterative difficulty balancing:
1. Collects all questions with model evaluation results
2. Creates a balanced initial benchmark (2K problems)
3. Iteratively adjusts to ensure target accuracy range (10%-25%)
4. Splits remaining problems into the corpus

Requirements:
  - All question folders should contain data.json and result_*.json files
  - Adjust DATA_DIR, OUTPUT_BENCHMARK_DIR, OUTPUT_CORPUS_DIR to your paths
"""

import os
import json
import shutil
from collections import defaultdict
import random

# === CONFIGURATION ===
# Point these to your local data directories
DATA_DIR = "./all_data_dataset"
OUTPUT_BENCHMARK_DIR = "./Data_Bench_and_Corpus/Benchmark"
OUTPUT_CORPUS_DIR = "./Data_Bench_and_Corpus/Corpus"

MODELS = [
    "gpt-4o-2024-08-06",
    "gpt-4.1",
    "anthropic.claude-sonnet-4",
    "anthropic.claude-3.7-sonnet",
    "anthropic.claude-3.5-sonnet"
]

TARGET_BENCHMARK_SIZE = 2000
TARGET_MIN_ACCURACY = 0.10
TARGET_MAX_ACCURACY = 0.25
CATEGORY_MAX_ACCURACY = 0.25
MIN_CATEGORY_ACCURACY = 0.05


def build_question_dict():
    """Build question dictionary with category info and model results."""
    print("Building question dictionary...")

    question_dict = {}
    missing_results = defaultdict(int)
    processed_count = 0

    question_folders = []
    for item in os.listdir(DATA_DIR):
        if item.startswith("question") and os.path.isdir(os.path.join(DATA_DIR, item)):
            try:
                question_id = int(item.replace("question", ""))
                question_folders.append((question_id, item))
            except ValueError:
                continue

    question_folders.sort()
    print(f"Found {len(question_folders)} question folders")

    for question_id, folder_name in question_folders:
        processed_count += 1
        if processed_count % 1000 == 0:
            print(f"Progress: {processed_count}/{len(question_folders)}")

        question_dir = os.path.join(DATA_DIR, folder_name)
        data_file = os.path.join(question_dir, "data.json")
        if not os.path.exists(data_file):
            continue

        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"Error loading {data_file}: {e}")
            continue

        main_category = data.get('main_category', 'Unknown')
        sub_category = data.get('sub_category', 'Unknown')

        model_results = {}
        has_all_results = True

        for model in MODELS:
            result_file = os.path.join(question_dir, f"result_{model}.json")
            if not os.path.exists(result_file):
                missing_results[model] += 1
                has_all_results = False
                break

            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    model_results[model] = result.get('is_correct', False)
            except Exception as e:
                print(f"Error loading {result_file}: {e}")
                has_all_results = False
                break

        if has_all_results:
            question_dict[question_id] = {
                'folder_name': folder_name,
                'main_category': main_category,
                'sub_category': sub_category,
                'model_results': model_results,
                'correct_count': sum(model_results.values())
            }

    print(f"Questions with complete results: {len(question_dict)}")

    if missing_results:
        print("\nMissing results:")
        for model, count in missing_results.items():
            print(f"  {model}: {count} questions missing")

    return question_dict


def analyze_question_dict(question_dict):
    """Print dataset statistics."""
    print("\n=== Dataset Analysis ===")

    category_stats = defaultdict(lambda: defaultdict(int))
    model_stats = defaultdict(list)

    for qid, info in question_dict.items():
        category_stats[info['main_category']][info['sub_category']] += 1
        for model, result in info['model_results'].items():
            model_stats[model].append(result)

    total_questions = len(question_dict)
    print("\nCategory distribution:")
    for main_cat, sub_cats in category_stats.items():
        main_total = sum(sub_cats.values())
        print(f"{main_cat} ({main_total}, {main_total/total_questions:.1%}):")
        for sub_cat, count in sub_cats.items():
            print(f"  {sub_cat}: {count} ({count/total_questions:.1%})")

    print("\nModel accuracy (full dataset):")
    for model in MODELS:
        if model_stats[model]:
            accuracy = sum(model_stats[model]) / len(model_stats[model])
            print(f"  {model}: {accuracy:.3f}")

    return category_stats


def create_balanced_initial_benchmark(question_dict, target_size):
    """Create balanced initial benchmark ensuring category coverage."""
    print(f"\nCreating balanced initial benchmark, target size: {target_size}")

    category_groups = defaultdict(list)
    for qid, info in question_dict.items():
        key = (info['main_category'], info['sub_category'])
        category_groups[key].append((qid, info))

    category_question_pools = {}
    for key, questions in category_groups.items():
        by_difficulty = defaultdict(list)
        for qid, info in questions:
            by_difficulty[info['correct_count']].append((qid, info))

        mixed_questions = []
        for correct_count in [1, 2, 0, 3, 4, 5]:
            if correct_count in by_difficulty:
                mixed_questions.extend(by_difficulty[correct_count])

        category_question_pools[key] = mixed_questions

    sorted_categories = sorted(category_question_pools.items(), key=lambda x: len(x[1]))

    benchmark_dict = {}
    current_size = 0

    for (main_cat, sub_cat), questions in sorted_categories:
        category_size = len(questions)

        if current_size + category_size <= target_size:
            for qid, info in questions:
                benchmark_dict[qid] = info
            current_size += category_size
        else:
            remaining_slots = target_size - current_size
            if remaining_slots > 0:
                by_difficulty = defaultdict(list)
                for qid, info in questions:
                    by_difficulty[info['correct_count']].append((qid, info))

                selected_questions = []
                for correct_count in [1, 2, 0, 3, 4, 5]:
                    if correct_count in by_difficulty and len(selected_questions) < remaining_slots:
                        available = by_difficulty[correct_count]
                        needed = min(len(available), remaining_slots - len(selected_questions))
                        random.shuffle(available)
                        selected_questions.extend(available[:needed])

                for qid, info in selected_questions:
                    benchmark_dict[qid] = info
                current_size += len(selected_questions)

        if current_size >= target_size:
            break

    print(f"Initial benchmark size: {len(benchmark_dict)}")
    return benchmark_dict


def calculate_accuracies(benchmark_dict):
    """Calculate per-model accuracy on current benchmark."""
    model_stats = defaultdict(list)
    for qid, info in benchmark_dict.items():
        for model, result in info['model_results'].items():
            model_stats[model].append(result)

    accuracies = {}
    for model in MODELS:
        if model_stats[model]:
            accuracies[model] = sum(model_stats[model]) / len(model_stats[model])
        else:
            accuracies[model] = 0.0
    return accuracies


def calculate_category_accuracies(benchmark_dict):
    """Calculate per-category per-model accuracy."""
    category_model_stats = defaultdict(lambda: defaultdict(list))
    for qid, info in benchmark_dict.items():
        key = (info['main_category'], info['sub_category'])
        for model, result in info['model_results'].items():
            category_model_stats[key][model].append(result)

    category_accuracies = {}
    for key, model_results in category_model_stats.items():
        category_accuracies[key] = {}
        for model in MODELS:
            if model_results[model]:
                category_accuracies[key][model] = sum(model_results[model]) / len(model_results[model])
            else:
                category_accuracies[key][model] = 0.0
    return category_accuracies


def check_requirements(accuracies, category_accuracies):
    """Check if all accuracy requirements are met."""
    overall_ok = all(TARGET_MIN_ACCURACY <= acc <= TARGET_MAX_ACCURACY for acc in accuracies.values())

    zero_categories = []
    high_categories = []
    for key, model_accs in category_accuracies.items():
        max_acc = max(model_accs.values()) if model_accs else 0
        if max_acc == 0:
            zero_categories.append(key)
        elif max_acc > CATEGORY_MAX_ACCURACY:
            high_categories.append((key, max_acc))

    requirements_met = (overall_ok and len(zero_categories) == 0 and len(high_categories) <= 2)
    return requirements_met, zero_categories, high_categories


def continuous_iterative_adjustment(question_dict, initial_benchmark):
    """Iteratively adjust benchmark until all requirements are met."""
    print(f"\nStarting iterative adjustment...")
    print(f"Target: overall accuracy {TARGET_MIN_ACCURACY:.1%}-{TARGET_MAX_ACCURACY:.1%}")

    benchmark_dict = initial_benchmark.copy()
    remaining_questions = {qid: info for qid, info in question_dict.items() if qid not in benchmark_dict}

    remaining_by_category = defaultdict(lambda: defaultdict(list))
    for qid, info in remaining_questions.items():
        key = (info['main_category'], info['sub_category'])
        remaining_by_category[key][info['correct_count']].append((qid, info))

    max_iterations = 50
    iteration = 0

    while iteration < max_iterations:
        iteration += 1
        print(f"\n=== Iteration {iteration} ===")

        accuracies = calculate_accuracies(benchmark_dict)
        category_accuracies = calculate_category_accuracies(benchmark_dict)

        for model, acc in accuracies.items():
            status = "OK" if TARGET_MIN_ACCURACY <= acc <= TARGET_MAX_ACCURACY else "FAIL"
            print(f"  {model}: {acc:.3f} [{status}]")

        requirements_met, zero_categories, high_categories = check_requirements(accuracies, category_accuracies)

        if requirements_met:
            print("All requirements met!")
            break

        changes_made = False

        if zero_categories:
            for key in zero_categories[:3]:
                main_cat, sub_cat = key
                easier_questions = []
                for correct_count in [1, 2, 3, 4, 5]:
                    if correct_count in remaining_by_category[key]:
                        easier_questions.extend(remaining_by_category[key][correct_count])

                if easier_questions:
                    current_category_questions = [(qid, info) for qid, info in benchmark_dict.items()
                                                if info['main_category'] == main_cat and info['sub_category'] == sub_cat]
                    if current_category_questions:
                        hardest_questions = [(qid, info) for qid, info in current_category_questions
                                           if info['correct_count'] == 0]
                        if hardest_questions and easier_questions:
                            num_to_replace = min(len(hardest_questions), len(easier_questions), 5)
                            random.shuffle(hardest_questions)
                            random.shuffle(easier_questions)
                            for i in range(num_to_replace):
                                old_qid, old_info = hardest_questions[i]
                                benchmark_dict.pop(old_qid)
                                remaining_questions[old_qid] = old_info
                                new_qid, new_info = easier_questions[i]
                                benchmark_dict[new_qid] = new_info
                                remaining_questions.pop(new_qid)
                            changes_made = True

        elif high_categories:
            high_categories.sort(key=lambda x: x[1], reverse=True)
            for (main_cat, sub_cat), max_acc in high_categories[:2]:
                current_category_questions = [(qid, info) for qid, info in benchmark_dict.items()
                                            if info['main_category'] == main_cat and info['sub_category'] == sub_cat]
                if current_category_questions:
                    easier_questions = [(qid, info) for qid, info in current_category_questions
                                      if info['correct_count'] >= 3]
                    harder_questions = []
                    for correct_count in [0, 1]:
                        if correct_count in remaining_by_category[(main_cat, sub_cat)]:
                            harder_questions.extend(remaining_by_category[(main_cat, sub_cat)][correct_count])
                    if easier_questions and harder_questions:
                        num_to_replace = min(len(easier_questions), len(harder_questions), 8)
                        random.shuffle(easier_questions)
                        random.shuffle(harder_questions)
                        for i in range(num_to_replace):
                            old_qid, old_info = easier_questions[i]
                            benchmark_dict.pop(old_qid)
                            remaining_questions[old_qid] = old_info
                            new_qid, new_info = harder_questions[i]
                            benchmark_dict[new_qid] = new_info
                            remaining_questions.pop(new_qid)
                        changes_made = True
        else:
            too_high_models = [model for model, acc in accuracies.items() if acc > TARGET_MAX_ACCURACY]
            if too_high_models:
                questions_to_replace = []
                for qid, info in benchmark_dict.items():
                    high_model_correct_count = sum(1 for model in too_high_models if info['model_results'][model])
                    if high_model_correct_count >= 2:
                        questions_to_replace.append(qid)

                all_remaining = list(remaining_questions.items())
                all_remaining.sort(key=lambda x: x[1]['correct_count'])
                hardest_remaining = all_remaining[:30]

                if questions_to_replace and hardest_remaining:
                    num_to_replace = min(len(questions_to_replace), len(hardest_remaining), 15)
                    random.shuffle(questions_to_replace)
                    random.shuffle(hardest_remaining)
                    for i in range(num_to_replace):
                        old_qid = questions_to_replace[i]
                        old_info = benchmark_dict.pop(old_qid)
                        remaining_questions[old_qid] = old_info
                        new_qid, new_info = hardest_remaining[i]
                        benchmark_dict[new_qid] = new_info
                        remaining_questions.pop(new_qid)
                    changes_made = True

        current_size = len(benchmark_dict)
        if current_size < TARGET_BENCHMARK_SIZE:
            all_remaining = list(remaining_questions.items())
            all_remaining.sort(key=lambda x: x[1]['correct_count'])
            num_to_add = min(TARGET_BENCHMARK_SIZE - current_size, 15)
            if num_to_add > 0:
                added_count = 0
                for qid, info in all_remaining:
                    if qid not in benchmark_dict:
                        benchmark_dict[qid] = info
                        remaining_questions.pop(qid)
                        added_count += 1
                        if added_count >= num_to_add:
                            break
                changes_made = True

        if not changes_made:
            print("No further adjustments possible, stopping.")
            break

    return benchmark_dict


def copy_questions_from_dict(question_dict, output_dir, dataset_name):
    """Copy question files to output directory."""
    print(f"\nCopying {len(question_dict)} questions to {dataset_name}...")
    os.makedirs(output_dir, exist_ok=True)

    for i, (qid, info) in enumerate(question_dict.items()):
        if i % 100 == 0:
            print(f"  Progress: {i}/{len(question_dict)}")

        src_dir = os.path.join(DATA_DIR, info['folder_name'])
        dst_dir = os.path.join(output_dir, info['folder_name'])

        if os.path.exists(dst_dir):
            shutil.rmtree(dst_dir)
        shutil.copytree(src_dir, dst_dir)

    print(f"Done copying {dataset_name}")


def save_statistics_from_dict(benchmark_dict, corpus_dict):
    """Save dataset statistics to JSON."""
    def get_category_stats(question_dict):
        stats = defaultdict(lambda: defaultdict(int))
        for info in question_dict.values():
            stats[info['main_category']][info['sub_category']] += 1
        return dict(stats)

    stats = {
        'benchmark': {
            'total': len(benchmark_dict),
            'categories': get_category_stats(benchmark_dict)
        },
        'corpus': {
            'total': len(corpus_dict),
            'categories': get_category_stats(corpus_dict)
        }
    }

    stats_file = os.path.join(os.path.dirname(OUTPUT_BENCHMARK_DIR), "dataset_statistics.json")
    with open(stats_file, 'w', encoding='utf-8') as f:
        json.dump(stats, f, indent=2, ensure_ascii=False)
    print(f"\nStatistics saved to: {stats_file}")


def main():
    random.seed(42)

    question_dict = build_question_dict()
    if not question_dict:
        print("No valid question data found!")
        return

    analyze_question_dict(question_dict)
    initial_benchmark = create_balanced_initial_benchmark(question_dict, TARGET_BENCHMARK_SIZE)
    benchmark_dict = continuous_iterative_adjustment(question_dict, initial_benchmark)

    benchmark_ids = set(benchmark_dict.keys())
    corpus_dict = {qid: info for qid, info in question_dict.items() if qid not in benchmark_ids}

    print(f"\nFinal split: Benchmark={len(benchmark_dict)}, Corpus={len(corpus_dict)}")

    user_input = input("\nProceed with file copying? (y/n): ").strip().lower()
    if user_input != 'y':
        print("Cancelled.")
        return

    copy_questions_from_dict(benchmark_dict, OUTPUT_BENCHMARK_DIR, "Benchmark")
    copy_questions_from_dict(corpus_dict, OUTPUT_CORPUS_DIR, "Corpus")
    save_statistics_from_dict(benchmark_dict, corpus_dict)
    print("\nDataset construction complete!")


if __name__ == "__main__":
    main()
