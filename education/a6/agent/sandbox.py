# ======================================================================
# 1. SETUP
# ======================================================================
import io
import tarfile
import docker

SANDBOX_IMAGE = "python:3.12-slim"
DEFAULT_TIMEOUT_S = 10
_client = docker.from_env()


# ======================================================================
# 2. FUNCTIONS
# ======================================================================
# Pulls the sandbox image once if it is missing on the host.
def _ensure_image() -> None:
    try:
        _client.images.get(SANDBOX_IMAGE)
    except docker.errors.ImageNotFound:
        _client.images.pull(SANDBOX_IMAGE)


# Packs the code string into a tar stream for put_archive.
def _make_tar(filename: str, content: str) -> bytes:
    data = content.encode("utf-8")
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w") as tar:
        info = tarfile.TarInfo(name=filename)
        info.size = len(data)
        info.mode = 0o644
        tar.addfile(info, io.BytesIO(data))
    buf.seek(0)
    return buf.read()


# Runs 'code' in isolation and returns exit_code, stdout, stderr, timed_out.
# Does not raise exceptions to the caller - errors land in stderr so the agent
# can read them as an observation and correct itself.
def run_code(code: str, timeout_s: int = DEFAULT_TIMEOUT_S) -> dict:
    import base64

    _ensure_image()

    container = _client.containers.create(
        image=SANDBOX_IMAGE,
        command=["sleep", "infinity"],
        network_disabled=True,
        mem_limit="256m",
        memswap_limit="256m",
        nano_cpus=500_000_000,
        pids_limit=128,
        read_only=True,
        tmpfs={"/tmp": "rw,size=64m,mode=1777"},
        cap_drop=["ALL"],
        security_opt=["no-new-privileges"],
        user="nobody",
        environment={"PYTHONDONTWRITEBYTECODE": "1"},
        labels={"role": "code-sandbox"},
    )

    try:
        container.start()

        encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")
        script = (
            f"echo {encoded} | base64 -d > /tmp/script.py && "
            f"timeout --signal=KILL {timeout_s} python /tmp/script.py"
        )
        exit_code, output = container.exec_run(
            cmd=["sh", "-c", script],
            demux=True,
        )
        stdout, stderr = output if output else (b"", b"")
        return {
            "exit_code": exit_code,
            "stdout": (stdout or b"").decode("utf-8", "replace"),
            "stderr": (stderr or b"").decode("utf-8", "replace"),
            "timed_out": exit_code == 137,
        }
    except Exception as exc:
        return {
            "exit_code": -1,
            "stdout": "",
            "stderr": f"sandbox error: {exc}",
            "timed_out": False,
        }
    finally:
        try:
            container.remove(force=True)
        except docker.errors.NotFound:
            pass

# ======================================================================
# 3. TEST-EXECUTION
# ======================================================================
if __name__ == "__main__":
    print(run_code("print('hello from the sandbox'); print(2 + 2)"))