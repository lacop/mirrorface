import contextlib
import os
import time
from typing import Dict, List, Optional, Tuple

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


def repo_root_dir() -> str:
    return os.path.dirname(os.path.dirname(integration_tests_dir()))


def build_docker_image(docker_client, path) -> str:
    image, logs = docker_client.images.build(
        path=path,
        rm=True,
        forcerm=True,
    )
    return image.id


def run_test_client(
    docker_client,
    test_client_image,
    network: Optional[str] = None,
    environment: Optional[Dict[str, str]] = None,
) -> Tuple[List[str], int]:
    container = docker_client.containers.run(
        image=test_client_image,
        command="python client.py",
        detach=True,
        network=network,
        environment=environment,
    )

    output_prefix = colored("Client output:", "yellow")
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
    # TODO: Run prune? Or unique network name? Or try to delete the name first.
    network = docker_client.networks.create(
        name="mirrorface-integration-tests-internal", internal=internal
    )
    try:
        yield network.id
    finally:
        network.remove()


def run_mirrorface(
    docker_client,
    mirrorface_image,
    network: Optional[str] = None,
    environment: Optional[Dict[str, str]] = None,
):
    container = docker_client.containers.run(
        image=mirrorface_image,
        detach=True,
        network=network,
        environment=environment,
    )

    output_prefix = colored("Mirrorface output:", "cyan")
    logs = container.logs(stream=True)
    log_lines = []
    for log in logs:
        line = log.decode("utf-8").strip()
        log_lines.append(line)
        print(f"  {output_prefix}", line)

    exit_code = container.wait().get("StatusCode")
    container.remove()

    return log_lines, exit_code


def run():
    print("Running integration tests")

    docker_client = docker.from_env()
    with test_step("Build test client Docker image"):
        test_client_image = build_docker_image(
            docker_client, os.path.join(integration_tests_dir(), "test_client")
        )
    # with test_step("Build mirrorface Docker image"):
    #     # TODO: docker-py doesn't support buildkit which we need for the main Dockerfile caching.
    #     # Options:
    #     #  - Use subprocess.run() to call docker build directly, can use the API for
    #     #    the other operations but just for this build we bypass it.
    #     #  - Build that image externally (CI step) and pass it in (less convenient for local testing)
    #     #  - Create a separate Dockerfile for the server which doesn't need buildkit.
    #     # Leaning towards the last option for now but let's see.
    #     # mirrorface_image = build_docker_image(docker_client, repo_root_dir())
    #     mirrorface_image = "mirrorface-server"

    # First run the test client without network restrictions
    # to make sure the baseline is working and upstream is reachable.
    with test_step("Run normally"):
        logs, exit_code = run_test_client(docker_client, test_client_image)
        assert exit_code == 0, "Test client failed"
        assert logs[-1] == "MIRRORFACE-TEST-CLIENT:PASS"

    # Make sure the HF_ENDPOINT environment variable is respected.
    # If we point to proxy that isn't running the client should fail.
    with test_step("Run with invalid HF_ENDPOINT"):
        logs, exit_code = run_test_client(
            docker_client,
            test_client_image,
            environment={"HF_ENDPOINT": "http://localhost:1234"},
        )
        assert exit_code != 0, "Test client should have failed"
        assert any("Connection refused" in log for log in logs), (
            "Test client should have failed due to connection refused"
        )
        assert not any("MIRRORFACE-TEST-CLIENT:PASS" in log for log in logs), (
            "Test client should not have passed"
        )

    # Next run with internal network, the client must fail. This ensures
    # it doesn't always trivially pass and that there isn't any state leak.
    with test_step("Run in internal network"):
        with test_network(docker_client, internal=True) as internal_network:
            logs, exit_code = run_test_client(
                docker_client, test_client_image, network=internal_network
            )
        assert exit_code != 0, "Test client should have failed"
        assert any("Failed to resolve" in log for log in logs), (
            "Test client should have failed due to network error"
        )
        assert not any("MIRRORFACE-TEST-CLIENT:PASS" in log for log in logs), (
            "Test client should not have passed"
        )

    # Start the mirrorface container which has network access, and
    # the test client with only access to the mirrorface container.
    # It should pass thanks to the fallback proxying.
    # TODO: Implement this test.
    # with test_step("Run with mirrorface"):
    #     with test_network(docker_client, internal=False) as open_network:
    #         logs, exit_code = run_mirrorface(
    #             docker_client, mirrorface_image, network=open_network,
    #             environment={"MIRRORFACE_LOCAL_DIRECTORY": "/tmp/mirrorface"}
    #         )
    #         # TODO: Need to run it in the background (continue streaming logs)
    #         # so we can start client here and then stop the server gracefully.
    #         # TODO: Create separate internal network, add second network to
    #         # the server container.

    print("All tests passed")
