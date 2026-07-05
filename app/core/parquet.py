from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from app.filters.models import dump_filter_configs

if TYPE_CHECKING:
    from app.core.session import WizardSession


def save_parquet_with_metadata(df: pd.DataFrame, session: WizardSession, path: Path | str) -> None:
    """Save a DataFrame to a Parquet file with ExPyRi session metadata."""
    # 1. Prepare metadata dict
    metadata_dict = {
        "dataset": session.dataset_id,
        "timestamp": datetime.now(UTC).isoformat(),
        "selected_statistical_methods": {
            "continuous": session.selected_method,
            "discrete": session.selected_discrete_method,
        },
        "statistic_results": session.stat_results,
        "plots_selected": session.selected_plots,
        # basically all choices and info from expyri:
        "session_id": session.session_id,
        "group_column": session.group_column,
        "selected_value_columns": session.selected_value_columns,
        "selected_discrete_columns": session.selected_discrete_columns,
        "selected_groups": session.selected_groups,
        "filters_config": dump_filter_configs(session.filters_config),
        "selected_method": session.selected_method,
        "selected_discrete_method": session.selected_discrete_method,
        "plot_results": session.plot_results,
        "top_n_columns": session.top_n_columns,
        "hierarchy": session.hierarchy.model_dump() if session.hierarchy else None,
        "excluded_clusters": [c.model_dump() for c in session.excluded_clusters],
    }

    # 2. Convert dataframe to pyarrow table
    table = pa.Table.from_pandas(df)

    # 3. Encode metadata to json bytes
    custom_metadata = {}
    for k, v in metadata_dict.items():
        custom_metadata[k] = json.dumps(v).encode("utf-8")

    # 4. Combine with existing schema metadata (e.g. pandas schema info)
    existing_metadata = table.schema.metadata or {}
    combined_metadata = {**existing_metadata, **custom_metadata}

    # 5. Replace schema metadata on table
    table = table.replace_schema_metadata(combined_metadata)

    # 6. Write table to parquet path
    pq.write_table(table, str(path))  # type: ignore[no-untyped-call]
