"""Predictions ko drift-detector tak bhejo (background thread, best-effort).

API kabhi block/fail nahi hoti: queue bhar gayi ya detector down hai to records drop ho jate hain.
"""
import json
import queue
import threading
import time
import urllib.request

from prometheus_client import Counter

SENT = Counter("churn_ingest_sent_total", "Records drift-detector ko bheje gaye")
FAILED = Counter("churn_ingest_failed_total", "Records jo bheje nahi ja sake")


class IngestClient:
    def __init__(self, url: str, batch_size: int = 50, flush_seconds: float = 2.0):
        self.url = url
        self.batch_size = batch_size
        self.flush_seconds = flush_seconds
        self._q: queue.Queue = queue.Queue(maxsize=5000)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()

    def submit(self, record: dict):
        try:
            self._q.put_nowait(record)
        except queue.Full:
            FAILED.inc()

    def _run(self):
        while not self._stop.is_set():
            batch, deadline = [], time.monotonic() + self.flush_seconds
            while len(batch) < self.batch_size and time.monotonic() < deadline:
                try:
                    batch.append(self._q.get(timeout=0.2))
                except queue.Empty:
                    pass
            if batch:
                self._post(batch)

    def _post(self, batch: list):
        try:
            req = urllib.request.Request(
                self.url, data=json.dumps({"records": batch}).encode(), headers={"Content-Type": "application/json"}
            )
            urllib.request.urlopen(req, timeout=3).read()
            SENT.inc(len(batch))
        except Exception:
            FAILED.inc(len(batch))
