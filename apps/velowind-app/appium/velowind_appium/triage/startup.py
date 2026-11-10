"""Start one detached queue watcher; its lifetime lock survives caller exit."""
import os
from pathlib import Path
import subprocess
import sys
import time

from .store import QueueBusyError, Store


def watching(queue):
    store = Store(queue)
    try:
        with store.lock('watch'):
            return False
    except QueueBusyError:
        return True
    finally:
        store.db.close()


def ensure_worker(repo, queue, config=None):
    repo, queue = Path(repo).resolve(), Path(queue).resolve()
    if watching(queue):
        return 'AI worker 已运行；队列：' + str(queue)
    config = Path(config or repo / '.tmp/appium-triage-config.json').resolve()
    if not config.is_file():
        return 'AI worker 未启动：配置不存在 ' + str(config)
    queue.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env['PYTHONPATH'] = str(repo / 'apps/velowind-app/appium')
    command = [sys.executable, '-m', 'velowind_appium.triage', '--repo', str(repo),
               '--queue', str(queue), '--config', str(config), 'watch']
    with (queue / 'worker-watch.log').open('a') as log:
        process = subprocess.Popen(command, cwd=repo, env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
    for _ in range(40):
        if watching(queue):
            return 'AI worker 已自动启动；队列：' + str(queue)
        if process.poll() is not None:
            # A concurrent starter may already own the lifetime lock.
            break
        time.sleep(0.05)
    if watching(queue):
        return 'AI worker 已运行；队列：' + str(queue)
    return 'AI worker 启动未就绪，请检查 ' + str(queue / 'worker-watch.log')
