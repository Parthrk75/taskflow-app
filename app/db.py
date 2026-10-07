import contextlib
import time

import pymysql
from flask import current_app, g
from pymysql.cursors import DictCursor

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id          INT AUTO_INCREMENT PRIMARY KEY,
    title       VARCHAR(200) NOT NULL,
    description TEXT NOT NULL,
    priority    ENUM('low', 'medium', 'high') NOT NULL DEFAULT 'medium',
    status      ENUM('todo', 'in_progress', 'done') NOT NULL DEFAULT 'todo',
    due_date    DATE NULL,
    created_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_tasks_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
"""

SEED = """
INSERT INTO tasks (title, description, priority, status, due_date) VALUES
 ('Set up CI/CD pipeline', 'Build the Docker image and push it on every merge to main.', 'high', 'in_progress', DATE_ADD(CURDATE(), INTERVAL 2 DAY)),
 ('Write Helm chart', 'Package the app and database as a reusable chart.', 'high', 'done', DATE_SUB(CURDATE(), INTERVAL 1 DAY)),
 ('Add monitoring', 'Expose metrics and wire up dashboards.', 'medium', 'todo', DATE_ADD(CURDATE(), INTERVAL 7 DAY)),
 ('Rotate database password', 'Move the password to an external secret store.', 'medium', 'todo', DATE_SUB(CURDATE(), INTERVAL 3 DAY)),
 ('Update documentation', 'Document deployment steps in the README.', 'low', 'todo', NULL),
 ('Load test the service', 'Run a quick load test with 2 replicas.', 'low', 'done', DATE_SUB(CURDATE(), INTERVAL 5 DAY))
"""


def get_conn():
    """One connection per request, stored on flask.g and closed automatically."""
    if "db" not in g:
        cfg = current_app.config
        g.db = pymysql.connect(
            host=cfg["DB_HOST"],
            port=cfg["DB_PORT"],
            user=cfg["DB_USER"],
            password=cfg["DB_PASSWORD"],
            database=cfg["DB_NAME"],
            charset="utf8mb4",
            cursorclass=DictCursor,
            connect_timeout=5,
            autocommit=False,
        )
    return g.db


def close_db(_exc=None):
    conn = g.pop("db", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:  # noqa: BLE001
            pass


@contextlib.contextmanager
def get_cursor(commit=True):
    conn = get_conn()
    try:
        with conn.cursor() as cur:
            yield cur
        if commit:
            conn.commit()
        else:
            conn.rollback()
    except Exception:
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        raise


def init_db(app, retries=30, delay=3):
    """Create the table (and demo rows). Retries while MySQL is still starting."""
    for attempt in range(1, retries + 1):
        try:
            with app.app_context():
                with get_cursor() as cur:
                    # named lock so only one gunicorn worker / pod initialises at a time
                    cur.execute("SELECT GET_LOCK('taskflow_init', 60) AS got")
                    try:
                        cur.execute(SCHEMA)
                        if app.config["SEED_DATA"]:
                            cur.execute("SELECT COUNT(*) AS n FROM tasks")
                            if cur.fetchone()["n"] == 0:
                                cur.execute(SEED)
                        cur.connection.commit()
                    finally:
                        cur.execute("SELECT RELEASE_LOCK('taskflow_init')")
            app.logger.info("Database ready")
            return
        except pymysql.MySQLError as exc:
            app.logger.warning("DB not ready (%s/%s): %s", attempt, retries, exc)
            time.sleep(delay)
    raise RuntimeError("Could not connect to the database")
