"""Deployment must migrate successfully before starting a new application image."""

import json
import os
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

WORKFLOW = Path(__file__).resolve().parents[4] / ".github/workflows/deploy-hetzner.yml"


def test_migration_job_finishes_before_application_images_change() -> None:
    workflow = WORKFLOW.read_text()
    image_update = workflow.index("kubectl set image deployment/backend")
    migration = workflow.index("uv run alembic")
    assert migration < image_update
    assert "--for=condition=complete" in workflow[migration:image_update]


def test_migration_job_adopts_legacy_database_only_in_maintenance() -> None:
    workflow = WORKFLOW.read_text()
    migration = workflow[workflow.index('container["command"]') : workflow.index('for key in ("args"')]
    assert "prepare --database" in migration
    assert "inputs.maintenance_mode" in migration
    assert "ADOPT=" in migration
    assert "--apply" in migration
    assert workflow.index("baseline_tools prepare") < workflow.index("uv run alembic upgrade head")


def test_maintenance_stops_writers_before_migration() -> None:
    workflow = WORKFLOW.read_text()
    assert "maintenance_mode" in workflow
    assert workflow.index("--replicas=0") < workflow.index("uv run alembic")


def test_maintenance_migration_waits_for_protected_environment() -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]

    assert jobs["migrate"]["needs"] == "prepare"
    assert jobs["migrate"]["environment"]["name"] == (
        "${{ inputs.maintenance_mode && 'production-migration' || 'production-deploy' }}"
    )
    assert jobs["deploy"]["needs"] == ["prepare", "migrate"]
    assert "needs.migrate.result == 'success'" in jobs["deploy"]["if"]
    assert jobs["cleanup"]["needs"] == ["prepare", "migrate"]
    assert "needs.migrate.result == 'failure'" in jobs["cleanup"]["if"]
    assert "needs.migrate.result == 'skipped'" in jobs["cleanup"]["if"]
    assert "migration-started" in jobs["cleanup"]["steps"][-1]["run"]


@pytest.mark.skipif(not shutil.which("bash"), reason="Requires bash")
def test_cleanup_keeps_ingress_closed_after_migration_started(tmp_path: Path) -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    step = next(step for step in jobs["cleanup"]["steps"] if step["name"] == "Restore writers and public ingress")
    script = step["run"]
    for expression, value in {
        "secrets.HETZNER_USER": "test-user",
        "secrets.HETZNER_HOST": "test-host",
        "github.run_id": "885",
        "github.run_attempt": "1",
        "inputs.public_traffic_gate": "true",
    }.items():
        script = script.replace("${{ " + expression + " }}", value)

    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "ssh.log"
    ssh = tools / "ssh"
    ssh.write_text(
        f"#!{sys.executable}\n"
        "import os, sys\n"
        "from pathlib import Path\n"
        'Path(os.environ["SSH_TEST_LOG"]).open("a").write(" ".join(sys.argv[1:]) + "\\n")\n'
        "sys.exit(0)\n"
    )
    ssh.chmod(0o755)

    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - checked-in workflow
        [shutil.which("bash") or "bash", "-s"],
        input=script,
        text=True,
        capture_output=True,
        timeout=5,
        check=False,
        env=os.environ
        | {
            "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
            "SSH_TEST_LOG": str(log),
        },
    )

    assert result.returncode == 0, result.stderr
    calls = log.read_text()
    assert "test -e" in calls
    assert "kubectl apply" not in calls


@pytest.mark.skipif(not shutil.which("bash") or not shutil.which("timeout"), reason="Requires bash and GNU timeout")
@pytest.mark.parametrize(
    "scenario",
    [
        "success",
        "invalid",
        "empty",
        pytest.param("hang_dump", marks=pytest.mark.slow),
        pytest.param("hang_restore", marks=pytest.mark.slow),
        pytest.param("hang_stream", marks=pytest.mark.slow),
    ],
)
def test_maintenance_backup_verification_and_failure_recovery(tmp_path: Path, scenario: str) -> None:
    """Run the real maintenance shell against fake cluster and PostgreSQL commands."""
    block = WORKFLOW.read_text().split("      - name: Prepare maintenance and database backup\n", 1)[1]
    script = textwrap.dedent(block.split("<< 'SHELL'\n", 1)[1].split("          SHELL\n", 1)[0])
    for expression, value in {
        "inputs.run_migrations": "true",
        "inputs.image_tag": "v1.2.3",
        "inputs.public_traffic_gate": "false",
        "github.run_id": "885",
        "github.run_attempt": "1",
    }.items():
        script = script.replace("${{ " + expression + " }}", value)
    script = script.replace("/tmp/fallout-deploy-", f"{tmp_path}/fallout-deploy-")

    tools = tmp_path / "bin"
    tools.mkdir()
    pod_tmp = tmp_path / "pod-tmp"
    pod_tmp.mkdir()
    log = tmp_path / "commands.jsonl"
    fake_tool = f"#!{sys.executable}\n" + textwrap.dedent("""\
        import json, os, subprocess, sys, time
        from pathlib import Path

        command = Path(sys.argv[0]).name
        args = sys.argv[1:]
        scenario = os.environ["BACKUP_TEST_SCENARIO"]
        with open(os.environ["BACKUP_TEST_LOG"], "a") as stream:
            stream.write(json.dumps([command, *args]) + "\\n")
        if command == "timeout":
            # Keep the real timeout/termination behavior, using a fast test deadline.
            os.execv(os.environ["BACKUP_TEST_TIMEOUT"], ["timeout", "--kill-after=0.1s", "1s", *args[2:]])
        if command == "pg_dump":
            if scenario == "hang_dump":
                time.sleep(2)
            data = b"" if scenario == "empty" else b"bad archive" if scenario == "invalid" else b"PGDMP verified fixture"
            if "-f" in args:
                Path(args[args.index("-f") + 1]).write_bytes(data)
            else:
                sys.stdout.buffer.write(data)
            sys.exit(0)
        if command == "pg_restore":
            if scenario == "hang_restore":
                time.sleep(2)
            data = sys.stdin.buffer.read() if args[-1] == "--list" else Path(args[-1]).read_bytes()
            sys.exit(0 if data.startswith(b"PGDMP") else 2)
        assert command == "kubectl", command
        assert args[:2] == ["-n", "fallout"], args
        args = args[2:]
        if args[:2] == ["get", "pvc"]:
            print("Bound")
        elif args[:2] == ["get", "deployment"]:
            if "backend" in args and "dramatiq-worker" in args:
                print(json.dumps({"items": [
                    {"metadata": {"name": "backend"}, "spec": {"replicas": 2}},
                    {"metadata": {"name": "dramatiq-worker"}, "spec": {"replicas": 1}},
                ]}))
            else:
                print(json.dumps({"spec": {"selector": {"matchLabels": {"app": args[2]}}}}))
        elif args[:2] == ["get", "service"]:
            print(json.dumps({"spec": {"selector": {"app": "postgres"}}}))
        elif args[:2] == ["get", "pods"]:
            if "app=postgres" in args:
                print(json.dumps({"items": [{"metadata": {"name": "postgres-0"}, "status": {"phase": "Running"}}]}))
        elif args[0] == "scale":
            pass
        elif args[0] == "exec":
            remote = args[args.index("--") + 1:]
            if remote[0] == "python3":
                print("fallout_db")
            else:
                result = subprocess.run(remote, check=False)
                if scenario == "hang_stream":
                    time.sleep(2)
                sys.exit(result.returncode)
        else:
            raise AssertionError(args)
        """)
    for command in ("kubectl", "pg_dump", "pg_restore", "timeout"):
        executable = tools / command
        executable.write_text(fake_tool)
        executable.chmod(0o755)

    bash = shutil.which("bash")
    assert bash is not None
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - checked-in workflow, isolated external-tool fakes
        [bash, "-s"],
        check=False,
        input=script,
        text=True,
        capture_output=True,
        timeout=5,
        env=os.environ
        | {
            "HOME": str(tmp_path),
            "TMPDIR": str(pod_tmp),
            "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
            "POSTGRES_USER": "postgres",
            "BACKUP_TEST_SCENARIO": scenario,
            "BACKUP_TEST_LOG": str(log),
            "BACKUP_TEST_TIMEOUT": shutil.which("timeout") or "timeout",
        },
    )
    commands = [json.loads(line) for line in log.read_text().splitlines()]
    scales = [args for args in commands if args[:4] == ["kubectl", "-n", "fallout", "scale"]]
    backup = tmp_path / "fallout-backups/pre-v1.2.3-885.dump"
    assert scales[0][-1] == "--replicas=0"
    assert any(args[0] == "pg_dump" for args in commands), result.stderr
    if scenario == "success":
        assert result.returncode == 0, result.stderr
        assert backup.read_bytes() == b"PGDMP verified fixture"
        assert "Database backup verified:" in result.stdout
        assert len(scales) == 1  # Writers stay stopped for the following migration step.
        assert not list(pod_tmp.iterdir())
    else:
        assert result.returncode != 0
        if scenario.startswith("hang_"):
            assert result.returncode == 124  # GNU timeout, rather than an unrelated shell failure.
        assert not backup.exists(), "An unsuccessful backup must not be published as a verified dump"
        assert "Database backup verified:" not in result.stdout
        assert scales[-2:] == [
            ["kubectl", "-n", "fallout", "scale", "deployment/backend", "--replicas=2"],
            ["kubectl", "-n", "fallout", "scale", "deployment/dramatiq-worker", "--replicas=1"],
        ]


@pytest.mark.skipif(not shutil.which("bash"), reason="Requires bash")
@pytest.mark.parametrize("migration_status", [0, 21])
def test_dev_backend_starts_only_after_successful_migration(tmp_path: Path, migration_status: int) -> None:
    tasks = json.loads((WORKFLOW.parents[2] / ".zed/tasks.json").read_text())
    command = next(task["command"] for task in tasks if task["label"] == "Fallout: Run backend server (Podman)")
    tools = tmp_path / "bin"
    tools.mkdir()
    podman = tools / "podman"
    podman.write_text("#!/bin/sh\nexit 0\n")
    podman.chmod(0o755)
    uv = tools / "uv"
    uv.write_text(
        "#!/bin/sh\n"
        'if [ "$2" = "alembic" ]; then\n'
        f'  if [ {migration_status} -ne 0 ]; then echo "migration failed" >&2; fi\n'
        f"  exit {migration_status}\n"
        "fi\n"
        'echo "backend started"\n'
    )
    uv.chmod(0o755)
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - checked-in task, isolated tool fakes
        [shutil.which("bash") or "bash", "-c", command],
        env=os.environ | {"PATH": f"{tools}{os.pathsep}{os.environ['PATH']}"},
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == migration_status
    if migration_status:
        assert "backend started" not in result.stdout
        assert "migration failed" in result.stderr
    else:
        assert "backend started" in result.stdout


@pytest.mark.skipif(not shutil.which("bash"), reason="Requires bash")
@pytest.mark.parametrize("maintenance", [False, True])
@pytest.mark.parametrize("fail_apply", [False, True])
def test_manifest_apply_pins_images_and_keeps_maintenance_writers_stopped(
    tmp_path: Path, maintenance: bool, fail_apply: bool
) -> None:
    """Capture actual apply payloads, including a late failure before image updates."""
    import yaml

    workflow = yaml.safe_load(WORKFLOW.read_text())
    step = next(step for step in workflow["jobs"]["deploy"]["steps"] if step["name"] == "Apply deployment manifests")
    script = step["run"]
    for expression, value in {
        "inputs.image_tag": "v2.289.1",
        "inputs.maintenance_mode": str(maintenance).lower(),
        "inputs.public_traffic_gate": "false",
        "secrets.DOCKER_USERNAME": "test-registry",
        "secrets.HETZNER_USER": "test-user",
        "secrets.HETZNER_HOST": "test-host",
    }.items():
        script = script.replace("${{ " + expression + " }}", value)
    tools = tmp_path / "bin"
    tools.mkdir()
    log = tmp_path / "applied.jsonl"
    fake = f"#!{sys.executable}\n" + textwrap.dedent("""\
        import json, os, sys
        from pathlib import Path
        import yaml

        args = sys.argv[1:]
        if Path(sys.argv[0]).name == "ssh":
            os.execv("/bin/bash", ["bash", "-c", args[-1]])
        documents = list(yaml.safe_load_all(sys.stdin.read()))
        document = documents[0]
        if args[:2] == ["set", "image"]:
            assert "--local" in args
            assignment = next(arg for arg in args if "=" in arg and not arg.startswith("-"))
            name, image = assignment.split("=", 1)
            container = next(c for c in document["spec"]["template"]["spec"]["containers"] if c["name"] == name)
            container["image"] = image
            print(json.dumps(document))
        elif args[0] == "patch":
            assert "--local" in args
            patch = json.loads(args[args.index("-p") + 1])
            document.setdefault("spec", {}).update(patch.get("spec", {}))
            print(json.dumps(document))
        else:
            assert args == ["apply", "-n", "fallout", "-f", "-"]
            with open(os.environ["MANIFEST_TEST_LOG"], "a") as stream:
                for item in documents:
                    stream.write(json.dumps(item) + "\\n")
            if os.environ["MANIFEST_TEST_FAIL"] == "true" and document["metadata"]["name"] == "dramatiq-worker":
                sys.exit(42)
        """)
    for name in ("ssh", "kubectl"):
        executable = tools / name
        executable.write_text(fake)
        executable.chmod(0o755)
    env = os.environ | {
        "PATH": f"{tools}{os.pathsep}{os.environ['PATH']}",
        "MANIFEST_TEST_LOG": str(log),
        "MANIFEST_TEST_FAIL": str(fail_apply).lower(),
        "IMAGE_TAG": "v2.289.1",
        "DOCKER_USERNAME": "test-registry",
        "MAINTENANCE_MODE": str(maintenance).lower(),
        "PUBLIC_TRAFFIC_GATE": "false",
    }
    result = subprocess.run(  # ruff: ignore[subprocess-without-shell-equals-true] - checked-in workflow, isolated tool fakes
        [shutil.which("bash") or "bash", "-c", script],
        cwd=WORKFLOW.parents[2],
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
        check=False,
    )
    applied = [json.loads(line) for line in log.read_text().splitlines()]
    deployments = {doc["metadata"]["name"]: doc for doc in applied if doc["kind"] == "Deployment"}
    assert set(deployments) == (
        {"backend", "dramatiq-worker"} if fail_apply else {"backend", "dramatiq-worker", "frontend"}
    )
    for name, document in deployments.items():
        image = "fo-shelter-fe" if name == "frontend" else "fo-shelter-be"
        assert document["spec"]["template"]["spec"]["containers"][0]["image"] == f"test-registry/{image}:v2.289.1"
        assert document["spec"]["replicas"] == (0 if maintenance and name != "frontend" else 1)
    assert result.returncode == (42 if fail_apply else 0), result.stderr
    if not fail_apply:
        assert {doc["kind"] for doc in applied} == {"Deployment", "Service", "Ingress"}
        assert all(doc["metadata"]["name"] != "postgres" for doc in applied)
