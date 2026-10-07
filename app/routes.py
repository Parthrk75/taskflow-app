import math
import os
import platform
import socket
import time
from datetime import date

from flask import (Blueprint, abort, current_app, flash, jsonify, redirect,
                   render_template, request, url_for)

from .db import get_cursor

bp = Blueprint("main", __name__)
START_TIME = time.time()

PRIORITIES = ("low", "medium", "high")
STATUSES = ("todo", "in_progress", "done")


# ---------- helpers ----------
def safe_next(default):
    target = request.form.get("next") or ""
    if target.startswith("/") and not target.startswith("//"):
        return target
    return default


def get_task_or_404(task_id):
    with get_cursor(commit=False) as cur:
        cur.execute("SELECT * FROM tasks WHERE id = %s", (task_id,))
        task = cur.fetchone()
    if task is None:
        abort(404)
    return task


def parse_form(form):
    data = {
        "title": form.get("title", "").strip(),
        "description": form.get("description", "").strip(),
        "priority": form.get("priority", "medium"),
        "status": form.get("status", "todo"),
    }
    errors = {}

    if not data["title"]:
        errors["title"] = "Title is required."
    elif len(data["title"]) > 200:
        errors["title"] = "Title must be 200 characters or fewer."
    if data["priority"] not in PRIORITIES:
        errors["priority"] = "Choose a valid priority."
    if data["status"] not in STATUSES:
        errors["status"] = "Choose a valid status."

    due_raw = form.get("due_date", "").strip()
    due = None
    if due_raw:
        try:
            due = date.fromisoformat(due_raw)
        except ValueError:
            errors["due_date"] = "Enter a valid date."
    data["due_date"] = due or due_raw
    return data, errors


# ---------- page 1: dashboard ----------
@bp.route("/")
def dashboard():
    with get_cursor(commit=False) as cur:
        cur.execute(
            """
            SELECT COUNT(*) AS total,
                   COALESCE(SUM(status = 'todo'), 0) AS todo,
                   COALESCE(SUM(status = 'in_progress'), 0) AS in_progress,
                   COALESCE(SUM(status = 'done'), 0) AS done,
                   COALESCE(SUM(status <> 'done' AND due_date < CURDATE()), 0) AS overdue
            FROM tasks
            """
        )
        stats = {k: int(v or 0) for k, v in cur.fetchone().items()}
        cur.execute("SELECT priority, COUNT(*) AS n FROM tasks WHERE status <> 'done' GROUP BY priority")
        prio = {r["priority"]: r["n"] for r in cur.fetchall()}
        cur.execute("SELECT * FROM tasks ORDER BY created_at DESC, id DESC LIMIT 5")
        recent = cur.fetchall()
        cur.execute(
            "SELECT * FROM tasks WHERE status <> 'done' AND due_date IS NOT NULL "
            "ORDER BY due_date ASC LIMIT 5"
        )
        upcoming = cur.fetchall()

    completion = round(stats["done"] * 100 / stats["total"]) if stats["total"] else 0
    chart = {
        "status": [stats["todo"], stats["in_progress"], stats["done"]],
        "priority": [prio.get("low", 0), prio.get("medium", 0), prio.get("high", 0)],
    }
    return render_template(
        "dashboard.html", stats=stats, recent=recent, upcoming=upcoming,
        completion=completion, chart=chart,
    )


# ---------- page 2: task list ----------
@bp.route("/tasks")
def tasks():
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "")
    priority = request.args.get("priority", "")
    page = max(request.args.get("page", 1, type=int), 1)
    per_page = current_app.config["PER_PAGE"]

    where, params = [], []
    if q:
        where.append("(title LIKE %s OR description LIKE %s)")
        params += [f"%{q}%", f"%{q}%"]
    if status in STATUSES:
        where.append("status = %s")
        params.append(status)
    if priority in PRIORITIES:
        where.append("priority = %s")
        params.append(priority)
    clause = ("WHERE " + " AND ".join(where)) if where else ""

    with get_cursor(commit=False) as cur:
        cur.execute(f"SELECT COUNT(*) AS n FROM tasks {clause}", params)
        total = cur.fetchone()["n"]
        pages = max(math.ceil(total / per_page), 1)
        page = min(page, pages)
        cur.execute(
            f"""
            SELECT * FROM tasks {clause}
            ORDER BY (status = 'done'),
                     FIELD(priority, 'high', 'medium', 'low'),
                     (due_date IS NULL), due_date, id DESC
            LIMIT %s OFFSET %s
            """,
            params + [per_page, (page - 1) * per_page],
        )
        rows = cur.fetchall()

    filters = {"q": q, "status": status, "priority": priority}
    return render_template(
        "tasks.html", tasks=rows, total=total, page=page, pages=pages, filters=filters,
    )


# ---------- page 3: create / edit form ----------
@bp.route("/tasks/new", methods=["GET", "POST"])
def new_task():
    task = {"title": "", "description": "", "priority": "medium", "status": "todo", "due_date": ""}
    errors = {}
    if request.method == "POST":
        task, errors = parse_form(request.form)
        if not errors:
            with get_cursor() as cur:
                cur.execute(
                    "INSERT INTO tasks (title, description, priority, status, due_date) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (task["title"], task["description"], task["priority"], task["status"],
                     task["due_date"] or None),
                )
            flash("Task created.", "success")
            return redirect(url_for("main.tasks"))
    return render_template("task_form.html", task=task, errors=errors, mode="create")


@bp.route("/tasks/<int:task_id>/edit", methods=["GET", "POST"])
def edit_task(task_id):
    task = get_task_or_404(task_id)
    errors = {}
    if request.method == "POST":
        task, errors = parse_form(request.form)
        task["id"] = task_id
        if not errors:
            with get_cursor() as cur:
                cur.execute(
                    "UPDATE tasks SET title=%s, description=%s, priority=%s, status=%s, "
                    "due_date=%s, updated_at=NOW() WHERE id=%s",
                    (task["title"], task["description"], task["priority"], task["status"],
                     task["due_date"] or None, task_id),
                )
            flash("Task updated.", "success")
            return redirect(url_for("main.tasks"))
    return render_template("task_form.html", task=task, errors=errors, mode="edit")


@bp.post("/tasks/<int:task_id>/status")
def set_status(task_id):
    status = request.form.get("status")
    if status not in STATUSES:
        abort(400)
    with get_cursor() as cur:
        cur.execute("UPDATE tasks SET status=%s, updated_at=NOW() WHERE id=%s", (status, task_id))
    return redirect(safe_next(url_for("main.tasks")))


@bp.post("/tasks/<int:task_id>/delete")
def delete_task(task_id):
    with get_cursor() as cur:
        cur.execute("DELETE FROM tasks WHERE id = %s", (task_id,))
    flash("Task deleted.", "warning")
    return redirect(safe_next(url_for("main.tasks")))


# ---------- page 4: system status ----------
@bp.route("/status")
def system_status():
    db = {"ok": False}
    try:
        with get_cursor(commit=False) as cur:
            t0 = time.perf_counter()
            cur.execute("SELECT VERSION() AS version, DATABASE() AS name")
            row = cur.fetchone()
            latency = round((time.perf_counter() - t0) * 1000, 1)
            cur.execute("SELECT COUNT(*) AS n FROM tasks")
            count = cur.fetchone()["n"]
            cur.execute(
                "SELECT COALESCE(SUM(data_length + index_length), 0) AS b "
                "FROM information_schema.tables WHERE table_schema = DATABASE()"
            )
            size_kb = int(cur.fetchone()["b"]) / 1024
        db.update(
            ok=True, latency_ms=latency, tasks=count, name=row["name"],
            version=f"MySQL {row['version']}", size=f"{size_kb:.0f} KB",
        )
    except Exception as exc:  # noqa: BLE001
        db["error"] = str(exc).strip()

    uptime = int(time.time() - START_TIME)
    info = {
        "Pod / host": os.getenv("POD_NAME") or socket.gethostname(),
        "Node": os.getenv("NODE_NAME", "n/a (not running in Kubernetes)"),
        "Environment": current_app.config["APP_ENV"],
        "App version": current_app.config["APP_VERSION"],
        "Python": platform.python_version(),
        "Uptime": f"{uptime // 3600}h {(uptime % 3600) // 60}m {uptime % 60}s",
        "DB host": current_app.config["DB_HOST"],
    }
    return render_template("status.html", info=info, db=db)


# ---------- JSON / probe endpoints ----------
@bp.route("/live")
def live():
    """Liveness probe: process is up (does not touch the DB)."""
    return jsonify(status="alive")


@bp.route("/health")
def health():
    """Readiness probe: the app can reach the database."""
    try:
        with get_cursor(commit=False) as cur:
            cur.execute("SELECT 1")
        return jsonify(status="ok"), 200
    except Exception:  # noqa: BLE001
        return jsonify(status="db-unavailable"), 503


@bp.route("/api/tasks")
def api_tasks():
    with get_cursor(commit=False) as cur:
        cur.execute("SELECT id, title, description, priority, status, due_date FROM tasks ORDER BY id")
        rows = cur.fetchall()
    return jsonify([{**r, "due_date": r["due_date"].isoformat() if r["due_date"] else None} for r in rows])
