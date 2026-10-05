"""Lanzador persistente de etiquetado: desacoplado de la sesión interactiva.

Diseño mínimo Linux/WSL:
- doble fork + setsid (sesión nueva);
- stdout/stderr a archivos con línea buffering;
- estado/heartbeat JSON atómico;
- bloqueo flock + verificación de identidad del PID (no solo archivo);
- sin reinicio automático tras fallo.

No atribuye causas a Cursor/sandbox/OOM. Es protección operativa.
No ejecuta packing por sí solo: recibe un argv de trabajador.
"""

from __future__ import annotations

import argparse
import errno
import fcntl
import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

from labeling_io import atomic_write_json, read_json_strict  # noqa: E402


LOCK_NAME = "run.lock"
STATE_NAME = "run_state.json"
HEARTBEAT_NAME = "heartbeat.json"
PID_NAME = "worker.pid"


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except OSError as exc:
        if exc.errno == errno.ESRCH:
            return False
        if exc.errno == errno.EPERM:
            return True
        raise
    return True


def _read_cmdline(pid: int) -> str | None:
    path = Path(f"/proc/{pid}/cmdline")
    if not path.is_file():
        return None
    raw = path.read_bytes()
    return raw.replace(b"\x00", b" ").decode("utf-8", errors="replace").strip()


def _identity_matches(pid: int, expected_token: str) -> bool:
    cmd = _read_cmdline(pid)
    if cmd is None:
        return False
    return expected_token in cmd


def acquire_lock(run_dir: Path) -> Any:
    run_dir.mkdir(parents=True, exist_ok=True)
    lock_path = run_dir / LOCK_NAME
    handle = open(lock_path, "a+", encoding="utf-8")
    try:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:
        handle.close()
        raise RuntimeError(f"bloqueo activo: {lock_path}") from exc
    # Evitar que el trabajador herede el flock
    flags = fcntl.fcntl(handle.fileno(), fcntl.F_GETFD)
    fcntl.fcntl(handle.fileno(), fcntl.F_SETFD, flags | fcntl.FD_CLOEXEC)
    handle.seek(0)
    handle.truncate()
    handle.write(f"pid={os.getpid()} time={time.time()}\n")
    handle.flush()
    os.fsync(handle.fileno())
    return handle


def write_state(run_dir: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(run_dir / STATE_NAME, payload)


def write_heartbeat(run_dir: Path, payload: dict[str, Any]) -> None:
    atomic_write_json(run_dir / HEARTBEAT_NAME, payload)


def daemonize(*, stdout_path: Path, stderr_path: Path, workdir: Path) -> None:
    """Doble fork clásico; el nieto continúa."""

    if os.fork() > 0:
        # padre del primer fork
        raise SystemExit(0)
    os.setsid()
    if os.fork() > 0:
        raise SystemExit(0)
    os.chdir(str(workdir))
    os.umask(0o022)
    # redirigir stdio
    sys.stdout.flush()
    sys.stderr.flush()
    with open(stdout_path, "a", encoding="utf-8", buffering=1) as out, open(
        stderr_path, "a", encoding="utf-8", buffering=1
    ) as err:
        os.dup2(out.fileno(), 1)
        os.dup2(err.fileno(), 2)
    # stdin -> /dev/null
    with open(os.devnull, "rb") as devnull:
        os.dup2(devnull.fileno(), 0)


def start_worker(
    *,
    run_dir: Path,
    run_id: str,
    attempt_id: str,
    worker_argv: list[str],
    identity_token: str,
    workdir: Path | None = None,
) -> dict[str, Any]:
    """Arranca trabajador en sesión desacoplada. Devuelve metadatos del padre lanzador."""

    run_dir = run_dir.resolve()
    workdir = (workdir or run_dir).resolve()
    run_dir.mkdir(parents=True, exist_ok=True)
    # comprobar PID previo
    pid_path = run_dir / PID_NAME
    if pid_path.is_file():
        try:
            old = int(pid_path.read_text(encoding="utf-8").strip().split()[0])
        except ValueError:
            old = -1
        if old > 0 and _pid_alive(old) and _identity_matches(old, identity_token):
            raise RuntimeError(f"trabajador vivo pid={old} token={identity_token}")
    lock = acquire_lock(run_dir)
    stdout_path = run_dir / "stdout.log"
    stderr_path = run_dir / "stderr.log"
    started = time.time()
    write_state(
        run_dir,
        {
            "run_id": run_id,
            "attempt_id": attempt_id,
            "status": "starting",
            "identity_token": identity_token,
            "worker_argv": worker_argv,
            "started_unix": started,
            "pid": None,
        },
    )

    # Pipe para que el hijo informe PID tras daemonize
    r_fd, w_fd = os.pipe()
    launcher_pid = os.getpid()
    child = os.fork()
    if child == 0:
        os.close(r_fd)
        try:
            daemonize(stdout_path=stdout_path, stderr_path=stderr_path, workdir=workdir)
            worker_pid = os.getpid()
            os.write(w_fd, f"{worker_pid}\n".encode("utf-8"))
            os.close(w_fd)
            (run_dir / PID_NAME).write_text(f"{worker_pid}\n", encoding="utf-8")
            write_state(
                run_dir,
                {
                    "run_id": run_id,
                    "attempt_id": attempt_id,
                    "status": "running",
                    "identity_token": identity_token,
                    "worker_argv": worker_argv,
                    "started_unix": started,
                    "daemon_unix": time.time(),
                    "pid": worker_pid,
                    "launcher_pid": launcher_pid,
                    "pgid": os.getpgid(0),
                },
            )
            write_heartbeat(
                run_dir,
                {
                    "pid": worker_pid,
                    "unix": time.time(),
                    "phase": "exec_soon",
                    "current_order_id": None,
                },
            )
            env = os.environ.copy()
            env["PYTHONUNBUFFERED"] = "1"
            env["LABELING_RUN_DIR"] = str(run_dir.resolve())
            env["LABELING_RUN_ID"] = run_id
            env["LABELING_ATTEMPT_ID"] = attempt_id
            # argv[0]: absolute() sin resolve() para conservar identidad de la venv
            # (.venv/bin/python → symlink al base; resolve() perdería site-packages).
            fixed: list[str] = []
            for i, a in enumerate(worker_argv):
                if i == 0:
                    fixed.append(str(Path(a).absolute()))
                elif a.endswith(".py") and not a.startswith("-"):
                    fixed.append(str(Path(a).absolute()))
                else:
                    fixed.append(a)
            os.execvpe(fixed[0], fixed, env)
        except Exception as exc:  # noqa: BLE001
            try:
                write_state(
                    run_dir,
                    {
                        "run_id": run_id,
                        "attempt_id": attempt_id,
                        "status": "failed_to_start",
                        "error": f"{type(exc).__name__}: {exc}",
                    },
                )
            finally:
                os._exit(1)
        os._exit(127)

    os.close(w_fd)
    lock.close()  # el trabajador no hereda el flock del padre de forma útil tras exec; el lock file queda
    # Leer PID del daemon
    raw = b""
    while b"\n" not in raw:
        chunk = os.read(r_fd, 64)
        if not chunk:
            break
        raw += chunk
    os.close(r_fd)
    os.waitpid(child, 0)  # primer hijo intermedio / runner
    worker_pid = int(raw.decode().strip() or "0")
    return {
        "status": "launched",
        "run_dir": str(run_dir),
        "worker_pid": worker_pid,
        "stdout": str(stdout_path),
        "stderr": str(stderr_path),
    }


def status(run_dir: Path, *, identity_token: str | None = None) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    state_path = run_dir / STATE_NAME
    hb_path = run_dir / HEARTBEAT_NAME
    pid_path = run_dir / PID_NAME
    out: dict[str, Any] = {"run_dir": str(run_dir), "state": None, "heartbeat": None, "pid_file": None}
    if state_path.is_file() and state_path.stat().st_size > 0:
        out["state"] = read_json_strict(state_path)
        identity_token = identity_token or out["state"].get("identity_token")
    if hb_path.is_file() and hb_path.stat().st_size > 0:
        out["heartbeat"] = read_json_strict(hb_path)
    if pid_path.is_file():
        try:
            pid = int(pid_path.read_text(encoding="utf-8").strip().split()[0])
        except ValueError:
            pid = -1
        out["pid_file"] = pid
        alive = _pid_alive(pid)
        matches = _identity_matches(pid, identity_token) if (alive and identity_token) else False
        out["pid_alive"] = alive
        out["pid_identity_matches"] = matches
        if not alive:
            out["detected"] = "dead_without_clean_close" if out.get("state", {}).get("status") == "running" else "not_running"
        elif identity_token and not matches:
            out["detected"] = "pid_stale_or_wrong_identity"
        else:
            out["detected"] = "running"
    else:
        out["detected"] = "no_pid_file"
    return out


def request_stop(run_dir: Path, *, identity_token: str, grace_seconds: float = 5.0) -> dict[str, Any]:
    """SIGTERM al trabajador si identidad coincide. No usa kill genérico por nombre."""

    st = status(run_dir, identity_token=identity_token)
    pid = st.get("pid_file")
    if not pid or not st.get("pid_alive") or not st.get("pid_identity_matches"):
        return {"status": "not_stopped", "reason": st.get("detected"), "detail": st}
    os.kill(int(pid), signal.SIGTERM)
    deadline = time.time() + grace_seconds
    while time.time() < deadline:
        if not _pid_alive(int(pid)):
            write_state(
                run_dir,
                {
                    **(st.get("state") or {}),
                    "status": "stopped_by_signal",
                    "stop_signal": "SIGTERM",
                    "stopped_unix": time.time(),
                },
            )
            return {"status": "stopped", "pid": pid, "signal": "SIGTERM"}
        time.sleep(0.05)
    return {"status": "still_alive_after_sigterm", "pid": pid}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Control de ejecución persistente de etiquetado")
    sub = p.add_subparsers(dest="cmd", required=True)
    start = sub.add_parser("start")
    start.add_argument("--run-dir", type=Path, required=True)
    start.add_argument("--run-id", required=True)
    start.add_argument("--attempt-id", required=True)
    start.add_argument("--identity-token", required=True)
    start.add_argument("--workdir", type=Path, default=None)
    start.add_argument("worker", nargs=argparse.REMAINDER, help="comando trabajador tras --")
    st = sub.add_parser("status")
    st.add_argument("--run-dir", type=Path, required=True)
    st.add_argument("--identity-token", default=None)
    stop = sub.add_parser("stop")
    stop.add_argument("--run-dir", type=Path, required=True)
    stop.add_argument("--identity-token", required=True)
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        if args.cmd == "start":
            worker = list(args.worker)
            if worker and worker[0] == "--":
                worker = worker[1:]
            if not worker:
                print(json.dumps({"status": "refused", "reason": "missing_worker_argv"}))
                return 2
            info = start_worker(
                run_dir=args.run_dir,
                run_id=args.run_id,
                attempt_id=args.attempt_id,
                worker_argv=worker,
                identity_token=args.identity_token,
                workdir=args.workdir,
            )
            print(json.dumps(info, ensure_ascii=False))
            return 0
        if args.cmd == "status":
            print(json.dumps(status(args.run_dir, identity_token=args.identity_token), ensure_ascii=False))
            return 0
        if args.cmd == "stop":
            print(json.dumps(request_stop(args.run_dir, identity_token=args.identity_token), ensure_ascii=False))
            return 0
    except RuntimeError as exc:
        print(json.dumps({"status": "refused", "reason": str(exc)}, ensure_ascii=False))
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
