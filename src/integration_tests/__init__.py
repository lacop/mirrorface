import os
import tempfile
import time

import docker

from integration_tests.docker_utils import (
    build_docker_image,
    run_mirrorface,
    run_test_client,
    test_network_internal,
    test_network_open,
)
from integration_tests.test_utils import integration_tests_dir, repo_root_dir, test_step
from mirrorface.tools.mirror import Settings as MirrorSettings
from mirrorface.tools.mirror import main as mirror_main


def run():
    print("Running integration tests")

    docker_client = docker.from_env()
    with test_step("Build test client Docker image"):
        test_client_image = build_docker_image(
            docker_client, os.path.join(integration_tests_dir(), "test_client")
        )
    with test_step("Build mirrorface Docker image"):
        # docker-py doesn't support buildkit which we need for the main Dockerfile caching,
        # so we build a separate simpler Dockerfile for the integration tests.
        mirrorface_image = build_docker_image(
            docker_client, repo_root_dir(), dockerfile="integration_test.Dockerfile"
        )

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
        with test_network_internal(docker_client) as internal_network:
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
    with test_step("Run with mirrorface"):
        with test_network_open(docker_client) as open_network:
            with test_network_internal(docker_client) as internal_network:
                with run_mirrorface(
                    docker_client,
                    mirrorface_image,
                    [open_network, internal_network],
                    {"MIRRORFACE_LOCAL_DIRECTORY": "/tmp/mirrorface"},
                ) as mirrorface_container:
                    # TODO: Implement health check in mirrorface so we can wait for it to be ready.
                    # That will also be useful for k8s health checks.
                    time.sleep(5)

                    # Without HF_ENDPOINT the client should fail.
                    logs, exit_code = run_test_client(
                        docker_client, test_client_image, network=internal_network
                    )
                    assert exit_code != 0, "Test client should have failed"

                    # With HF_ENDPOINT pointing to the mirrorface container it should pass,
                    # since the mirrorface container has access to the internet and can proxy.
                    logs, exit_code = run_test_client(
                        docker_client,
                        test_client_image,
                        network=internal_network,
                        environment={
                            "HF_ENDPOINT": f"http://{mirrorface_container}:8000/mirror"
                        },
                    )
                    assert exit_code == 0, "Test client failed"
                    assert logs[-1] == "MIRRORFACE-TEST-CLIENT:PASS"

    # Start mirrorface without network access, but mount a directory with a
    # mirrored repository which it can serve.
    with test_step("Run with mirrorface without network"):
        with test_network_internal(docker_client) as internal_network:
            with tempfile.TemporaryDirectory() as temporary_dir:
                # Download the repository.
                mirror_main(
                    MirrorSettings(
                        repository="prajjwal1/bert-tiny",
                        revision="main",
                        local_directory=temporary_dir,
                    )
                )

                with run_mirrorface(
                    docker_client,
                    mirrorface_image,
                    [internal_network],
                    {"MIRRORFACE_LOCAL_DIRECTORY": "/tmp/mirrorface"},
                    {temporary_dir: {"bind": "/tmp/mirrorface", "mode": "ro"}},
                ) as mirrorface_container:
                    # TODO: See above.
                    time.sleep(5)

                    logs, exit_code = run_test_client(
                        docker_client,
                        test_client_image,
                        network=internal_network,
                        environment={
                            "HF_ENDPOINT": f"http://{mirrorface_container}:8000/mirror"
                        },
                    )
                    assert exit_code == 0, "Test client failed"
                    assert logs[-1] == "MIRRORFACE-TEST-CLIENT:PASS"

    print("All tests passed")
