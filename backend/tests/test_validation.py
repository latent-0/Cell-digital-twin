"""Validation tests: the calibrated model must match literature IC50s."""

from celltwin.validation.reference import load_references
from celltwin.validation.validate import validate_model


def test_reference_set_loads():
    refs = load_references()
    assert len(refs) >= 10
    assert all(r.ic50_uM > 0 for r in refs)


def test_calibrated_model_matches_literature():
    """After calibration, every anchored toxin sits within 1 log of literature."""
    report = validate_model()
    offenders = [e.toxin for e in report.entries if not e.within_1_log]
    assert not offenders, f"toxins off by >1 log: {offenders}"


def test_rank_order_correlation_strong():
    """Cross-toxin potency ordering must track the literature (Spearman)."""
    report = validate_model()
    assert report.spearman is not None
    assert report.spearman > 0.8, f"weak rank-order correlation: {report.spearman}"


def test_median_fold_error_small():
    report = validate_model()
    assert report.median_fold_error is not None
    assert report.median_fold_error < 2.0
