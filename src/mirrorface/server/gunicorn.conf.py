import os
import shutil

from prometheus_client import REGISTRY, multiprocess, start_http_server

worker_class = "uvicorn.workers.UvicornWorker"

bind = "0.0.0.0:8000"

# TODO: Options from env vars?
#   - worker count
#   - bind address/port


# Prometheus multiprocess mode is pretty crap, need this to make it work.
# https://prometheus.github.io/client_python/multiprocess/
def on_starting(server):
    multiproc_dir = os.getenv("PROMETHEUS_MULTIPROC_DIR")
    if not multiproc_dir:
        return
    # Wipe between restarts, otherwise old metrics will persist.
    shutil.rmtree(multiproc_dir, ignore_errors=True)
    os.makedirs(multiproc_dir, exist_ok=True)
    multiprocess.MultiProcessCollector(REGISTRY)
    start_http_server(int(os.getenv("PROMETHEUS_MULTIPROC_PORT", 9000)))


def child_exit(server, worker):
    multiprocess.mark_process_dead(worker.pid)
