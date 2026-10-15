from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from evidence_defeat.preprocessing import (
    MISSING_CATEGORY,
    CovariateSchema,
    fit_preprocessor,
    observed_covariate_mask,
)


@pytest.fixture
def schema() -> CovariateSchema:
    return CovariateSchema(
        continuous=("age", "severity"),
        categorical=("sex", "site"),
    )


@pytest.fixture
def training_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "age": [10.0, 20.0, np.nan, 40.0],
            "severity": [1.0, 2.0, 3.0, 4.0],
            "sex": ["F", "M", None, "F"],
            "site": ["A", "A", "B", "B"],
            "treatment": [0, 1, 0, 1],
            "outcome": [1, 0, 1, 1],
        }
    )


def test_preprocessor_produces_finite_stable_mixed_type_matrix(
    schema: CovariateSchema,
    training_frame: pd.DataFrame,
) -> None:
    fitted = fit_preprocessor(training_frame, schema)
    train_matrix = fitted.transform(training_frame)
    heldout = pd.DataFrame(
        {
            "age": [np.nan, 1000.0],
            "severity": [2.5, 8.0],
            "sex": ["F", "UNSEEN"],
            "site": ["UNSEEN", "A"],
        }
    )
    heldout_matrix = fitted.transform(heldout)

    assert np.isfinite(train_matrix).all()
    assert np.isfinite(heldout_matrix).all()
    assert train_matrix.shape[1] == heldout_matrix.shape[1]
    assert any(MISSING_CATEGORY in name for name in fitted.feature_names())


def test_imputation_and_scaling_are_unchanged_by_heldout_rows(
    schema: CovariateSchema,
    training_frame: pd.DataFrame,
) -> None:
    fitted = fit_preprocessor(training_frame, schema)
    common = pd.DataFrame(
        {"age": [np.nan], "severity": [2.5], "sex": ["F"], "site": ["A"]}
    )
    combined = pd.concat(
        [
            common,
            pd.DataFrame(
                {
                    "age": [1_000_000.0],
                    "severity": [-1_000_000.0],
                    "sex": ["UNSEEN"],
                    "site": ["UNSEEN"],
                }
            ),
        ],
        ignore_index=True,
    )

    transformed_alone = fitted.transform(common)[0]
    transformed_with_extreme_row = fitted.transform(combined)[0]

    np.testing.assert_array_equal(transformed_alone, transformed_with_extreme_row)
    names = fitted.feature_names()
    age_position = names.index("numeric__age")
    age_missing_position = names.index("numeric_missing__missingindicator_age")
    assert transformed_alone[age_position] == pytest.approx(0.0)
    assert transformed_alone[age_missing_position] == pytest.approx(1.0)


def test_treatment_and_outcome_columns_are_not_transformed(
    schema: CovariateSchema,
    training_frame: pd.DataFrame,
) -> None:
    full = fit_preprocessor(training_frame, schema)
    covariates_only = fit_preprocessor(training_frame[list(schema.columns)], schema)

    np.testing.assert_array_equal(
        full.transform(training_frame),
        covariates_only.transform(training_frame[list(schema.columns)]),
    )
    assert all("treatment" not in name for name in full.feature_names())
    assert all("outcome" not in name for name in full.feature_names())


def test_observed_mask_is_preimputation_and_in_schema_order(
    schema: CovariateSchema,
    training_frame: pd.DataFrame,
) -> None:
    observed = observed_covariate_mask(training_frame, schema)

    assert observed.shape == (4, 4)
    np.testing.assert_array_equal(observed[2], [False, True, False, True])


def test_preprocessor_rejects_infinite_continuous_values(
    schema: CovariateSchema,
    training_frame: pd.DataFrame,
) -> None:
    invalid = training_frame.copy()
    invalid.loc[0, "age"] = np.inf

    with pytest.raises(ValueError, match="contains infinity"):
        fit_preprocessor(invalid, schema)


def test_schema_rejects_overlap_between_covariate_types() -> None:
    with pytest.raises(ValueError, match="must be unique"):
        CovariateSchema(continuous=("age",), categorical=("age",))
