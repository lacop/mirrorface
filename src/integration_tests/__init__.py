import contextlib
import os
import time
from typing import List, Optional, Tuple

import docker
from termcolor import colored


@contextlib.contextmanager
def test_step(name: str):
    step = colored(f"[{name}]", "blue")
    print(step, "Starting")
    t0 = time.monotonic()
    try:
        yield
    except Exception as e:
        print(step, colored(f"Failed after {time.monotonic() - t0:.3f}s", "red"))
        raise e
    print(step, colored(f"Completed in {time.monotonic() - t0:.3f}s", "green"))


def integration_tests_dir() -> str:
    return os.path.dirname(os.path.realpath(__file__))


def build_test_client_image(docker_client) -> str:
    image, logs = docker_client.images.build(
        path=os.path.join(integration_tests_dir(), "test_client"),
        rm=True,
        forcerm=True,
    )
    return image.id


def run_test_client(
    docker_client, test_client_image, network: Optional[str] = None
) -> Tuple[List[str], int]:
    container = docker_client.containers.run(
        image=test_client_image,
        command="python client.py",
        detach=True,
        network=network,
    )

    output_prefix = colored("Container output:", "yellow")
    logs = container.logs(stream=True)
    log_lines = []
    for log in logs:
        line = log.decode("utf-8").strip()
        log_lines.append(line)
        print(f"  {output_prefix}", line)

    exit_code = container.wait().get("StatusCode")
    container.remove()

    return log_lines, exit_code


@contextlib.contextmanager
def test_network(docker_client, internal: bool):
    network = docker_client.networks.create(
        name="mirrorface-integration-tests-internal", internal=internal
    )
    try:
        yield network.id
    finally:
        network.remove()


def run():
    print("Running integration tests")

    docker_client = docker.from_env()
    with test_step("Build test client Docker image"):
        test_client_image = build_test_client_image(docker_client)

    # First run the test client without network restrictions
    # to make sure the baseline is working and upstream is reachable.
    with test_step("Run normally"):
        logs, exit_code = run_test_client(docker_client, test_client_image)
        assert exit_code == 0, "Test client failed"
        assert logs[-1] == "MIRRORFACE-TEST-CLIENT:PASS"

    # Next run with internal network, the client must fail. This ensures
    # it doesn't always trivially pass and that there isn't any state leak.
    with test_network(docker_client, internal=True) as internal_network:
        with test_step("Run in internal network"):
            logs, exit_code = run_test_client(
                docker_client, test_client_image, network=internal_network
            )
        assert exit_code != 0, "Test client should have failed"
        assert any("Failed to resolve" in log for log in logs), (
            "Test client should have failed due to connection refused"
        )
        assert not any("MIRRORFACE-TEST-CLIENT:PASS" in log for log in logs), (
            "Test client should not have passed"
        )

    # Start the mirrorface container which has network access, and
    # the test client with only access to the mirrorface container.
    # It should pass thanks to the fallback proxying.
    # TODO: Implement this test.

    print("All tests passed")
