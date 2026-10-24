"""Training-only preprocessing for mixed baseline covariates."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from numpy.typing import NDArray
from sklearn.compose import ColumnTransformer
from sklearn.impute import MissingIndicator, SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, RobustScaler

MISSING_CATEGORY = "__MISSING__"


@dataclass(frozen=True)
class CovariateSchema:
    """Prespecified continuous and categorical baseline covariates."""

    continuous: tuple[str, ...] = ()
    categorical: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "continuous", tuple(self.continuous))
        object.__setattr__(self, "categorical", tuple(self.categorical))
        columns = self.columns
        if not columns:
            raise ValueError("at least one covariate must be specified")
        if len(set(columns)) != len(columns):
            raise ValueError("continuous and categorical covariates must be unique")

    @property
    def columns(self) -> tuple[str, ...]:
        return self.continuous + self.categorical


@dataclass(frozen=True)
class FittedPreprocessor:
    """A transformer fitted exclusively on one outer training fold."""

    schema: CovariateSchema
    transformer: ColumnTransformer

    def transform(self, covariates: pd.DataFrame) -> NDArray[np.float64]:
        prepared = _prepare_frame(covariates, self.schema)
        transformed = np.asarray(self.transformer.transform(prepared), dtype=float)
        if transformed.ndim != 2 or transformed.shape[0] != len(covariates):
            raise RuntimeError("preprocessor returned an invalid matrix shape")
        if not np.isfinite(transformed).all():
            raise ValueError("preprocessed covariates contain non-finite values")
        return transformed

    def feature_names(self) -> tuple[str, ...]:
        return tuple(self.transformer.get_feature_names_out().astype(str))


def fit_preprocessor(
    training_covariates: pd.DataFrame,
    schema: CovariateSchema,
) -> FittedPreprocessor:
    """Fit imputation, missingness encoding and feature transformation."""

    prepared = _prepare_frame(training_covariates, schema)
    transformers = []
    if schema.continuous:
        numeric_values = Pipeline(
            [
                (
                    "imputer",
                    SimpleImputer(strategy="median", keep_empty_features=True),
                ),
                ("scaler", RobustScaler()),
            ]
        )
        numeric_missing = MissingIndicator(features="all", error_on_new=False)
        transformers.extend(
            [
                ("numeric", numeric_values, list(schema.continuous)),
                ("numeric_missing", numeric_missing, list(schema.continuous)),
            ]
        )
    if schema.categorical:
        categorical = Pipeline(
            [
                (
                    "imputer",
                    SimpleImputer(
                        strategy="constant",
                        fill_value=MISSING_CATEGORY,
                        keep_empty_features=True,
                    ),
                ),
                (
                    "encoder",
                    OneHotEncoder(
                        handle_unknown="ignore",
                        sparse_output=False,
                        dtype=np.float64,
                    ),
                ),
            ]
        )
        transformers.append(("categorical", categorical, list(schema.categorical)))

    transformer = ColumnTransformer(
        transformers=transformers,
        remainder="drop",
        sparse_threshold=0.0,
        verbose_feature_names_out=True,
    )
    transformer.fit(prepared)
    result = FittedPreprocessor(schema=schema, transformer=transformer)
    result.transform(training_covariates)
    return result


def observed_covariate_mask(
    covariates: pd.DataFrame,
    schema: CovariateSchema,
) -> NDArray[np.bool_]:
    """Return preimputation observedness in the prespecified column order."""

    _require_columns(covariates, schema)
    return covariates.loc[:, list(schema.columns)].notna().to_numpy(dtype=bool)


def _prepare_frame(
    covariates: pd.DataFrame,
    schema: CovariateSchema,
) -> pd.DataFrame:
    if not isinstance(covariates, pd.DataFrame):
        raise TypeError("covariates must be a pandas DataFrame")
    if covariates.shape[0] < 1:
        raise ValueError("covariates must contain at least one row")
    _require_columns(covariates, schema)

    prepared = pd.DataFrame(index=covariates.index)
    for column in schema.continuous:
        try:
            numeric = pd.to_numeric(covariates[column], errors="raise").astype(float)
        except (TypeError, ValueError) as error:
            raise ValueError(
                f"continuous covariate {column!r} is not numeric"
            ) from error
        finite_or_missing = np.isfinite(numeric.to_numpy()) | numeric.isna().to_numpy()
        if not finite_or_missing.all():
            raise ValueError(f"continuous covariate {column!r} contains infinity")
        prepared[column] = numeric

    for column in schema.categorical:
        values = covariates[column]
        prepared[column] = values.map(
            lambda value: np.nan if pd.isna(value) else str(value)
        ).astype(object)
    return prepared


def _require_columns(covariates: pd.DataFrame, schema: CovariateSchema) -> None:
    if covariates.columns.duplicated().any():
        raise ValueError("covariate DataFrame column names must be unique")
    missing = [column for column in schema.columns if column not in covariates.columns]
    if missing:
        raise ValueError(f"missing prespecified covariates: {missing}")
