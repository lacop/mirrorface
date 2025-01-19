# TODO: Some cleanups (type annotations mostly)
import contextlib
from typing import Dict, List, Optional, Tuple

import docker
from termcolor import colored


def build_docker_image(
    docker_client: docker.DockerClient, path: str, dockerfile: str = "Dockerfile"
) -> str:
    image, logs = docker_client.images.build(
        path=path,
        dockerfile=dockerfile,
        rm=True,
        forcerm=True,
    )
    if image.id is None:
        print("Build logs:")
        for log in logs:
            print(log)
        raise RuntimeError("Failed to build Docker image")
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
def test_network_internal(docker_client):
    # TODO: Run prune? Or unique network name? Or try to delete the name first.
    network = docker_client.networks.create(
        name="mirrorface-integration-tests-internal",
        internal=True,
    )
    try:
        yield network.id
    finally:
        network.remove()


@contextlib.contextmanager
def test_network_open(docker_client):
    # TODO: Run prune? Or unique network name? Or try to delete the name first.
    network = docker_client.networks.create(
        name="mirrorface-integration-tests-open",
        internal=False,
    )
    try:
        yield network.id
    finally:
        network.remove()


@contextlib.contextmanager
def run_mirrorface(
    docker_client,
    mirrorface_image,
    networks: List[str],
    environment: Optional[Dict[str, str]] = None,
    volumes: Optional[Dict[str, Dict[str, str]]] = None,
):
    assert len(networks) > 0
    container = docker_client.containers.create(
        image=mirrorface_image,
        detach=True,
        network=networks[0],
        environment=environment,
        volumes=volumes,
    )
    # We can only provide one network to create, so connect the rest.
    for network in networks[1:]:
        net = docker_client.networks.get(network)
        net.connect(container)

    container.start()
    # TODO: Start a background thread to print logs?

    try:
        yield container.name
    finally:
        output_prefix = colored("Mirrorface output:", "cyan")
        logs = container.logs().split(b"\n")
        for log in logs:
            line = log.decode("utf-8").strip()
            print(f"  {output_prefix}", line)
        # TODO: Graceful shutdown with SIGTERM, verify exit code.
        container.kill()
        container.wait()
        container.remove()
