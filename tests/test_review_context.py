"""Tests for the ReviewHistoryContext and related utilities."""

import pytest
from grape_coder.agents.review.review_context import (
    ReviewHistoryContext,
    IterationResult,
    detect_regression,
    calculate_average_score,
    scores_improved,
)


class TestIterationResult:
    """Tests for IterationResult dataclass."""

    def test_basic_creation(self):
        result = IterationResult(
            iteration=1,
            scores={"code_validity": 15, "integration": 16},
            tasks_generated=["Fix bug", "Add feature"],
            fixes_applied=["Fixed bug in main.js"],
        )
        assert result.iteration == 1
        assert result.scores["code_validity"] == 15
        assert len(result.tasks_generated) == 2
        assert len(result.fixes_applied) == 1
        assert result.regression_detected is False

    def test_with_regression(self):
        result = IterationResult(
            iteration=2,
            scores={"code_validity": 12},
            tasks_generated=[],
            fixes_applied=[],
            regression_detected=True,
            regression_details="code_validity: 15 -> 12 (-3)",
        )
        assert result.regression_detected is True
        assert result.regression_details is not None
        assert "code_validity" in result.regression_details


class TestReviewHistoryContext:
    """Tests for ReviewHistoryContext class."""

    def test_default_creation(self):
        ctx = ReviewHistoryContext()
        assert ctx.max_iterations == 5
        assert ctx.current_iteration == 0
        assert len(ctx.iterations) == 0

    def test_custom_max_iterations(self):
        ctx = ReviewHistoryContext(max_iterations=3)
        assert ctx.max_iterations == 3

    def test_increment_iteration(self):
        ctx = ReviewHistoryContext(max_iterations=5)
        assert ctx.current_iteration == 0

        result = ctx.increment_iteration()
        assert result == 1
        assert ctx.current_iteration == 1

        result = ctx.increment_iteration()
        assert result == 2
        assert ctx.current_iteration == 2

    def test_should_continue_under_limit(self):
        ctx = ReviewHistoryContext(max_iterations=3)
        ctx.increment_iteration()
        ctx.increment_iteration()
        assert ctx.should_continue() is True

    def test_should_continue_at_limit(self):
        ctx = ReviewHistoryContext(max_iterations=3)
        ctx.increment_iteration()
        ctx.increment_iteration()
        ctx.increment_iteration()
        assert ctx.should_continue() is False

    def test_add_iteration_result(self):
        ctx = ReviewHistoryContext()
        ctx.increment_iteration()

        scores = {"code_validity": 15, "integration": 17}
        tasks = ["Fix layout", "Add alt text"]

        ctx.add_iteration_result(scores, tasks)

        assert len(ctx.iterations) == 1
        assert ctx.iterations[0].scores == scores
        assert ctx.iterations[0].tasks_generated == tasks

    def test_add_iteration_result_with_fixes(self):
        ctx = ReviewHistoryContext()
        ctx.increment_iteration()

        scores = {"code_validity": 15}
        tasks = ["Fix bug"]
        fixes = ["Fixed the bug in index.html"]

        ctx.add_iteration_result(scores, tasks, fixes)

        assert ctx.iterations[0].fixes_applied == fixes

    def test_regression_detection_on_add(self):
        ctx = ReviewHistoryContext()
        ctx.increment_iteration()

        # First iteration - baseline
        ctx.add_iteration_result({"code_validity": 15, "integration": 16}, ["Task 1"])

        ctx.increment_iteration()

        # Second iteration - regression in code_validity
        ctx.add_iteration_result({"code_validity": 12, "integration": 17}, ["Task 2"])

        assert ctx.iterations[1].regression_detected is True
        assert ctx.iterations[1].regression_details is not None
        assert "code_validity" in ctx.iterations[1].regression_details

    def test_no_regression_when_improving(self):
        ctx = ReviewHistoryContext()
        ctx.increment_iteration()

        ctx.add_iteration_result({"code_validity": 15}, ["Task 1"])

        ctx.increment_iteration()
        ctx.add_iteration_result({"code_validity": 17}, ["Task 2"])

        assert ctx.iterations[1].regression_detected is False

    def test_get_previous_scores_empty(self):
        ctx = ReviewHistoryContext()
        assert ctx.get_previous_scores() is None

    def test_get_previous_scores(self):
        ctx = ReviewHistoryContext()
        ctx.increment_iteration()
        ctx.add_iteration_result({"code_validity": 15}, [])

        scores = ctx.get_previous_scores()
        assert scores == {"code_validity": 15}

    def test_get_all_tasks_generated(self):
        ctx = ReviewHistoryContext()
        ctx.increment_iteration()
        ctx.add_iteration_result({}, ["Task 1", "Task 2"])
        ctx.increment_iteration()
        ctx.add_iteration_result({}, ["Task 3"])

        all_tasks = ctx.get_all_tasks_generated()
        assert len(all_tasks) == 3
        assert "Task 1" in all_tasks
        assert "Task 3" in all_tasks

    def test_get_all_fixes_applied(self):
        ctx = ReviewHistoryContext()
        ctx.increment_iteration()
        ctx.add_iteration_result({}, [], ["Fix 1"])
        ctx.increment_iteration()
        ctx.add_iteration_result({}, [], ["Fix 2", "Fix 3"])

        all_fixes = ctx.get_all_fixes_applied()
        assert len(all_fixes) == 3

    def test_had_regression(self):
        ctx = ReviewHistoryContext()
        ctx.increment_iteration()
        ctx.add_iteration_result({"code_validity": 15}, [])
        ctx.increment_iteration()
        ctx.add_iteration_result({"code_validity": 12}, [])  # Regression

        assert ctx.had_regression() is True

    def test_format_summary_for_reviewer_empty(self):
        ctx = ReviewHistoryContext()
        summary = ctx.format_summary_for_reviewer()
        assert summary == ""

    def test_format_summary_for_reviewer_with_context(self):
        ctx = ReviewHistoryContext(max_iterations=5)
        ctx.increment_iteration()
        ctx.add_iteration_result(
            {"code_validity": 14, "integration": 16},
            ["Fix layout issue", "Add hover states"],
            ["Fixed layout in index.html"],
        )
        ctx.increment_iteration()

        summary = ctx.format_summary_for_reviewer()

        assert "PREVIOUS REVIEW CONTEXT" in summary
        assert "code_validity" in summary.lower()
        assert "Fix layout issue" in summary
        assert "Fixed layout in index.html" in summary
        assert "Focus ONLY on issues that REMAIN" in summary

    def test_format_summary_for_task_generator(self):
        ctx = ReviewHistoryContext(max_iterations=5)
        ctx.increment_iteration()
        ctx.add_iteration_result({}, ["Task A", "Task B"])
        ctx.increment_iteration()

        summary = ctx.format_summary_for_task_generator()

        assert "ITERATION CONTEXT" in summary
        assert "PREVIOUSLY GENERATED TASKS" in summary
        assert "Task A" in summary
        assert "do not regenerate" in summary.lower()


class TestDetectRegression:
    """Tests for detect_regression function."""

    def test_no_regression_when_improving(self):
        current = {"code_validity": 17, "integration": 18}
        previous = {"code_validity": 15, "integration": 16}

        result = detect_regression(current, previous)
        assert result is None

    def test_no_regression_when_same(self):
        current = {"code_validity": 15}
        previous = {"code_validity": 15}

        result = detect_regression(current, previous)
        assert result is None

    def test_regression_single_category(self):
        current = {"code_validity": 12}
        previous = {"code_validity": 15}

        result = detect_regression(current, previous)
        assert result is not None
        assert "code_validity" in result
        assert "15 -> 12" in result

    def test_regression_multiple_categories(self):
        current = {"code_validity": 12, "integration": 14}
        previous = {"code_validity": 15, "integration": 16}

        result = detect_regression(current, previous)
        assert result is not None
        assert "code_validity" in result
        assert "integration" in result

    def test_mixed_improvement_and_regression(self):
        current = {"code_validity": 17, "integration": 14}
        previous = {"code_validity": 15, "integration": 16}

        result = detect_regression(current, previous)
        assert result is not None
        assert "integration" in result
        assert "code_validity" not in result


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_calculate_average_score_empty(self):
        assert calculate_average_score({}) == 0.0

    def test_calculate_average_score(self):
        scores = {"a": 10, "b": 20, "c": 30}
        assert calculate_average_score(scores) == 20.0

    def test_scores_improved_true(self):
        current = {"a": 15, "b": 18}
        previous = {"a": 12, "b": 14}
        assert scores_improved(current, previous) is True

    def test_scores_improved_false(self):
        current = {"a": 10, "b": 12}
        previous = {"a": 15, "b": 18}
        assert scores_improved(current, previous) is False
