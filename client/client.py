import time
from urllib.parse import urljoin
import requests

MAX_REDIRECTS = 5
ELECTION_RETRY_DELAY = 0.5
MAX_ELECTION_WAIT = 10.0


def post_with_raft_redirects(base_url: str, payload: dict, timeout: float = 2.0) -> requests.Response:
    """
    Robust RAFT-aware POST:

      - Always *start* from base_url + /chat.
      - Follow 302 + Location (up to MAX_REDIRECTS).
      - 302 without Location -> no leader yet (election); retry same URL with backoff.
      - Connection errors or "bad" HTTP statuses (404, 5xx) -> reset to original URL and retry.
    """
    original_url = urljoin(base_url, "/chat")
    url = original_url
    session = requests.Session()

    redirects = 0
    election_wait = 0.0
    last_location = None

    while True:
        try:
            resp = session.post(url, json=payload, timeout=timeout, allow_redirects=False)
        except (requests.ConnectionError, requests.Timeout) as e:
            # Target might be down (e.g., old leader). Go back to the original cluster URL.
            url = original_url
            redirects += 1
            if redirects > MAX_REDIRECTS:
                raise RuntimeError(f"Too many redirects / retries due to connection errors: {e}")
            continue

        # 1) Happy path
        if resp.status_code == 200:
            return resp

        # 2) RAFT redirect semantics
        if resp.status_code == 302:
            location = resp.headers.get("Location")

            # 302 WITH Location -> leader known (or follower thinks so)
            if location:
                # Loop detection
                if location == last_location:
                    redirects += 1
                else:
                    redirects = 1
                    last_location = location

                if redirects > MAX_REDIRECTS:
                    raise RuntimeError("Too many redirects, possible loop")

                # absolute vs relative
                if location.startswith("http://") or location.startswith("https://"):
                    url = location
                else:
                    url = urljoin(url, location)
                continue

            # 302 WITHOUT Location -> no leader yet (election ongoing)
            time.sleep(ELECTION_RETRY_DELAY)
            election_wait += ELECTION_RETRY_DELAY
            if election_wait > MAX_ELECTION_WAIT:
                raise RuntimeError("Cluster has no leader (election taking too long)")
            # retry same URL
            continue

        # 3) Other HTTP codes - treat some as transient and retry via original URL
        if resp.status_code in (404, 500, 502, 503, 504):
            url = original_url
            redirects += 1
            if redirects > MAX_REDIRECTS:
                raise RuntimeError(f"Too many retries after HTTP {resp.status_code}")
            time.sleep(0.2)
            continue

        # 4) Anything else is treated as a hard error
        resp.raise_for_status()


def get_with_raft_redirects(base_url: str, path: str = "/messages", timeout: float = 2.0) -> requests.Response:
    """
    Same redirect semantics as post_with_raft_redirects, but for GET.
    Used for polling /messages so that we can always talk to the current leader
    (via redirect) without caring which node ALB / localhost sends us to.
    """
    url = urljoin(base_url, path)
    session = requests.Session()

    redirects = 0
    election_wait = 0.0
    last_location = None

    while True:
        resp = session.get(url, timeout=timeout, allow_redirects=False)

        if resp.status_code == 200:
            return resp

        if resp.status_code == 302:
            location = resp.headers.get("Location")

            if location:
                if location == last_location:
                    redirects += 1
                else:
                    redirects = 1
                    last_location = location

                if redirects > MAX_REDIRECTS:
                    raise RuntimeError("Too many redirects, possible loop (GET)")

                if location.startswith("http://") or location.startswith("https://"):
                    url = location
                else:
                    url = urljoin(url, location)
                continue

            time.sleep(ELECTION_RETRY_DELAY)
            election_wait += ELECTION_RETRY_DELAY
            if election_wait > MAX_ELECTION_WAIT:
                raise RuntimeError("Cluster has no leader (GET) – election too long")
            continue

        resp.raise_for_status()
