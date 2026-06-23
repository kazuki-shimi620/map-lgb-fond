from __future__ import annotations

import sqlite3
from pathlib import Path


SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS datasets (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    source_url TEXT NOT NULL,
    region TEXT NOT NULL,
    record_count INTEGER NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS features (
    id INTEGER PRIMARY KEY,
    feature_name TEXT NOT NULL UNIQUE,
    description TEXT NOT NULL,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS experiments (
    id INTEGER PRIMARY KEY,
    experiment_name TEXT NOT NULL,
    dataset_id INTEGER NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('running', 'success', 'failed')),
    mae REAL,
    rmse REAL,
    mape REAL,
    train_time_seconds REAL,
    prediction_time_ms REAL,
    started_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dataset_id) REFERENCES datasets(id)
);

CREATE TABLE IF NOT EXISTS experiment_features (
    experiment_id INTEGER NOT NULL,
    feature_id INTEGER NOT NULL,
    PRIMARY KEY (experiment_id, feature_id),
    FOREIGN KEY (experiment_id) REFERENCES experiments(id),
    FOREIGN KEY (feature_id) REFERENCES features(id)
);

CREATE TABLE IF NOT EXISTS models (
    id INTEGER PRIMARY KEY,
    experiment_id INTEGER NOT NULL,
    model_type TEXT NOT NULL,
    region TEXT NOT NULL,
    model_path TEXT NOT NULL,
    onnx_path TEXT,
    is_latest INTEGER NOT NULL CHECK (is_latest IN (0, 1)),
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (experiment_id) REFERENCES experiments(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_models_latest_region
ON models(region)
WHERE is_latest = 1;
"""


def connect(db_path: str | Path) -> sqlite3.Connection:
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


def initialize_database(db_path: str | Path) -> None:
    with connect(db_path) as connection:
        connection.executescript(SCHEMA)


def upsert_features(connection: sqlite3.Connection, features: list[str]) -> None:
    connection.executemany(
        "INSERT OR IGNORE INTO features(feature_name, description) VALUES (?, ?)",
        [(feature, feature) for feature in features],
    )


def link_experiment_features(connection: sqlite3.Connection, experiment_id: int, features: list[str]) -> None:
    rows = connection.execute(
        "SELECT id, feature_name FROM features WHERE feature_name IN ({})".format(
            ",".join("?" for _ in features)
        ),
        features,
    ).fetchall()
    connection.executemany(
        "INSERT OR IGNORE INTO experiment_features(experiment_id, feature_id) VALUES (?, ?)",
        [(experiment_id, feature_id) for feature_id, _feature_name in rows],
    )


def create_dataset(connection: sqlite3.Connection, *, name: str, source_url: str, region: str, record_count: int) -> int:
    cursor = connection.execute(
        "INSERT INTO datasets(name, source_url, region, record_count) VALUES (?, ?, ?, ?)",
        (name, source_url, region, record_count),
    )
    return int(cursor.lastrowid)


def create_experiment(connection: sqlite3.Connection, *, name: str, dataset_id: int) -> int:
    cursor = connection.execute(
        "INSERT INTO experiments(experiment_name, dataset_id, status) VALUES (?, ?, 'running')",
        (name, dataset_id),
    )
    return int(cursor.lastrowid)


def complete_experiment(connection: sqlite3.Connection, experiment_id: int, metrics: dict[str, float]) -> None:
    connection.execute(
        """
        UPDATE experiments
        SET status = 'success',
            mae = ?,
            rmse = ?,
            mape = ?,
            completed_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (metrics["mae"], metrics["rmse"], metrics["mape"], experiment_id),
    )


def fail_experiment(connection: sqlite3.Connection, experiment_id: int) -> None:
    connection.execute(
        "UPDATE experiments SET status = 'failed', completed_at = CURRENT_TIMESTAMP WHERE id = ?",
        (experiment_id,),
    )


def register_model_if_best(
    connection: sqlite3.Connection,
    *,
    experiment_id: int,
    model_type: str,
    region: str,
    model_path: str,
    onnx_path: str | None,
    mae: float,
) -> bool:
    current = connection.execute(
        """
        SELECT experiments.mae
        FROM models
        JOIN experiments ON experiments.id = models.experiment_id
        WHERE models.region = ? AND models.is_latest = 1
        """,
        (region,),
    ).fetchone()
    should_update_latest = current is None or current[0] is None or mae < float(current[0])

    if should_update_latest:
        connection.execute("UPDATE models SET is_latest = 0 WHERE region = ? AND is_latest = 1", (region,))

    connection.execute(
        """
        INSERT INTO models(experiment_id, model_type, region, model_path, onnx_path, is_latest)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (experiment_id, model_type, region, model_path, onnx_path, 1 if should_update_latest else 0),
    )
    return should_update_latest
