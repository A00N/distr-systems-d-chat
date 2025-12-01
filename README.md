
# DChat (RAFT-based Distributed Chat)  

A simple distributed chat system built on top of a RAFT-style consensus algorithm.  
It supports:

- **3-node RAFT cluster** (leader election + log replication)
- **HTTP API** with RAFT-aware `302` redirects
- **ALB-compatible redirects** (Location header always points to ALB hostname in prod)
- **Safe behavior during elections** (302 without Location while there is no leader)
- **Tkinter GUI client** with:
  - Username selection
  - Multiple rooms (synced between clients via RAFT)
  - Message “sending…” gray echo that disappears when committed
  - “Active users” sidebar (recently active users)


---

## 1. Project Structure

```text
distr-systems-d-chat/
├── .dockerignore
├── .gitignore
├── Dockerfile
├── README.md
├── requirements.txt
├── user-data.sh
├── .github/
│   └── workflows/
│       └── push-image.yml
├── server/
│   ├── discovery.py          
│   ├── message_protocol.py          
│   ├── node.py 
│   ├── raft.py
│   └── state_machine.py
└── client/
    ├── chat_client.py   
    ├── client.py
    ├── gui.py
    └── README.md
````

---

## 2. Concept Overview

### 2.1 RAFT

All 3 nodes run identical code:

* One node becomes **leader** (via RAFT election).
* Others are **followers**.
* When a client sends a chat message to the leader:

  * Leader appends to its log.
  * Replicates the entry to followers.
  * Once a majority (2 of 3) have stored it, the entry is **committed**.
  * The `ChatState` applies the command → chat log.

If the leader dies:

* Followers eventually notice the lack of heartbeat.
* One of them starts an election and becomes the new leader.
* As long as a **majority of nodes are up**, the cluster can elect a leader and accept writes.

### 2.2 HTTP API + Redirects

Each node exposes a small HTTP API:

* `GET /health` → `200 OK`, body `OK`
* `GET /messages` → `200 OK`, JSON list of all committed messages
* `POST /chat` → RAFT-aware behavior (see below)

For `/chat`:

* **On the leader**:

  * `POST /chat` returns:
    `HTTP/1.1 200 OK`
    Body: `{"status": "ok", "index": ...}`

* **On a follower with known leader**:

  * Returns `HTTP/1.1 302 Found`
  * In **local dev**:

    * `Location: http://127.0.0.1:<leader_http_port>/chat`
  * In **AWS / ALB mode** (see section 6):

    * `Location: https://<ALB_HOST>/chat`

* **During election (no known leader)**:

  * Returns `HTTP/1.1 302 Found` **without** `Location`
  * This tells clients: "no leader yet, wait/retry"


---

## 3. Local Setup

### 3.1 Requirements

* Python 3.10+ recommended
* On Windows:

  * PowerShell
  * Tkinter is usually included in standard Python builds

### 3.2 Create & Activate Virtual Environment

From the `dchat_raft` directory:

```bash
python -m venv venv

# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Linux/macOS
source venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

`requirements.txt` mainly includes:

* `requests` (used by the client for HTTP)

The server itself uses only the standard library.

---

## 4. Running the 3-Node Cluster Locally

In **three separate terminals** (all with the venv activated), run:

### Terminal 1 – node0

```bash
python server/node.py --id node0 --http-port 9000 --raft-port 10000 \
  --peers 127.0.0.1:10001,127.0.0.1:10002
```

### Terminal 2 – node1

```bash
python server/node.py --id node1 --http-port 9001 --raft-port 10001 \
  --peers 127.0.0.1:10000,127.0.0.1:10002
```

### Terminal 3 – node2

```bash
python server/node.py --id node2 --http-port 9002 --raft-port 10002 \
  --peers 127.0.0.1:10000,127.0.0.1:10001
```

You should see log lines like:

* `nodeX RAFT listening on 0.0.0.0:<port> (follower)`
* Then eventually: `nodeX became LEADER for term Y`

Only one node is leader at any time.

---

## 5. Testing the HTTP Behavior (Windows-friendly)

### 5.1 Basic health check

```powershell
Invoke-WebRequest -Uri "http://127.0.0.1:9000/health"
```

Expected: body `OK`, status code 200.

### 5.2 Testing `/chat` with PowerShell

To send a message to a specific node **without** following redirects:

```powershell
$resp0 = Invoke-WebRequest `
  -Uri "http://127.0.0.1:9000/chat" `
  -Method POST `
  -Headers @{ "Content-Type" = "application/json" } `
  -Body '{"type":"chat","user":"tester","text":"hello","room":"general","id":"test1"}' `
  -MaximumRedirection 0

$resp0.StatusCode
$resp0.Headers.Location
$resp0.Content
```

Do the same for nodes 9001 and 9002 to observe leader/follower behavior:

* Leader returns:

  * `StatusCode = 200`
  * No `Location` header
* Followers return (normal conditions):

  * `StatusCode = 302`
  * `Location` header pointing to the leader’s HTTP port in local dev

### 5.3 Election behavior

1. Identify the current leader (the node whose `/chat` returns 200).
2. Kill the leader (`Ctrl+C` in that terminal).
3. Immediately send `/chat` to a follower:

   ```powershell
   $resp = Invoke-WebRequest `
     -Uri "http://127.0.0.1:9001/chat" `
     -Method POST `
     -Headers @{ "Content-Type" = "application/json" } `
     -Body '{"type":"chat","user":"tester","text":"during election","room":"general","id":"test2"}' `
     -MaximumRedirection 0

   $resp.StatusCode
   $resp.Headers.Location
   ```

During the brief election window, you should see:

* `StatusCode = 302`
* **No** `Location` header

Once a new leader is elected, followers start returning 302 with `Location` again.

---

## 6. GUI Client (Tkinter)

### 6.1 Starting the GUI Client

From `dchat_raft` (venv activated):

```bash
python client/chat_client.py
```

On startup, the client:

1. Asks for a **username** in a small dialog.
2. Opens the main window with:

   * Left sidebar:

     * **Rooms** list (with `+` and `-` buttons)
     * **Users** list (“recently active” users)
   * Right side:

     * Chat area
     * Input box + Send button
     * Status line (`Connected` / `Disconnected`)

### 6.2 Rooms

* Initially, there is a single room: `general`.
* Click `+` to create a new room:

  * You’ll be prompted for a room name.

  * The GUI sends a RAFT command:

    ```json
    {"type": "room_add", "room": "<name>", "user": "<you>"}
    ```

  * Once committed, **all clients** see the new room appear.
* Click `-` to delete the selected room:

  * Sends `{"type": "room_delete", "room": "<name>", "user": "<you>"}`.
  * Room is removed from all clients’ UI when the command is committed.
  * The special room `"general"` cannot be deleted.

Internally:

* The server just stores these commands in the log.
* The client’s polling loop inspects `type`:

  * `room_add` → update local room set → update UI.
  * `room_delete` → remove from local room set → update UI, move users back to `general` if needed.

### 6.3 Messages & Gray “Sending…” Echo

When you type a message and press Enter / Send:

1. Client generates a message ID (UUID).

2. It immediately shows a **gray** “pending” line:

   ```text
   HH:MM  <username>: <message>    (in gray)
   ```

3. It sends a payload like:

   ```json
   {
     "type": "chat",
     "user": "<username>",
     "text": "<message>",
     "room": "<current_room>",
     "id": "<uuid>"
   }
   ```

4. When the entry is committed and appears in `/messages`:

   * Polling loop sees it.
   * If `id` matches one of our pending messages:

     * The gray line is removed.
   * A **normal (black)** line is rendered from the committed entry.

5. Other clients see only the black (committed) line, never the gray.

This ensures:

* You get instant feedback that your message is being sent.
* The chat log eventually reflects the authoritative RAFT log.

### 6.4 Active Users

The Users list shows **recently active** users:

* Every time a message (chat or room command) with a `user` field arrives:

  * That username is added to a local active set.
  * They appear in the Users list.
  * Their “last seen” timestamp is updated.
* Periodically, users with no activity for more than **5 minutes** are removed from the list.


---

## 7. RAFT & Client Redirect Logic

### 7.1 RAFT leader tracking

`server/raft.py` tracks a `leader_id`:

* Updated when AppendEntries (heartbeats) arrive from a leader.
* Set to self when the node wins an election.

`handle_client_command` returns:

* On leader:

  ```json
  {"status": "ok", "index": N}
  ```

* On follower:

  ```json
  {"status": "not_leader", "leader": "<known_leader_id or null>"}
  ```

### 7.2 HTTP redirect behavior in `server/node.py`

When `/chat` calls `raft.handle_client_command`:

* If `status == "ok"`:

  * Return `200 OK` with JSON body.
* If `status == "not_leader"`:

  * If `leader` is known:

    * Local dev:

      * Map `leader_id` → HTTP port (`node0→9000`, `node1→9001`, `node2→9002`).
      * `Location: http://127.0.0.1:<leader_port>/chat`
    * AWS / ALB:

      * Uses env vars:

        ```bash
        DCHAT_PUBLIC_HOST="<your-alb-dns>"
        DCHAT_PUBLIC_SCHEME="https"
        ```

      * `Location: https://<your-alb-dns>/chat`
  * If `leader` is **not** known:

    * `302 Found` with **no** `Location` header.

### 7.3 Client redirect helper (`client/client.py`)

`client/client.py` implements:

* `post_with_raft_redirects(base_url, payload, timeout=2.0)` – for `/chat`
* `get_with_raft_redirects(base_url, path="/messages", timeout=2.0)` – for `/messages`

Behavior:

* Always starts from `base_url` (e.g. `http://127.0.0.1:9000` or `https://your-alb`).
* Handles:

  * `200 OK` → success.
  * `302` with Location → follows redirect (absolute or relative), up to `MAX_REDIRECTS`.
  * `302` without Location → treat as “election in progress”; retry same URL with small backoff until `MAX_ELECTION_WAIT`.
  * Connection errors or transient `4xx/5xx` (e.g., 404, 500, 502, 503, 504) → reset back to the original `base_url` and retry.

This makes the client resilient to:

* Leader changes.
* Nodes going up/down.
* Stale or temporarily wrong leader hints.

---

## 8. AWS Deployment (High-Level)


### 8.1 EC2 Nodes

For each node:

* Run `server/node.py` with appropriate IDs and ports, e.g.:

  ```bash
  python server/node.py \
    --id node-a \
    --http-port 5000 \
    --raft-port 6000 \
    --peers 10.0.1.11:6000,10.0.2.10:6000
  ```

* Security groups:

  * Allow inbound **HTTP port** (e.g. 5000) from the ALB SG.
  * Allow inbound **RAFT port** (e.g. 6000) from the *other nodes only* (within VPC).

### 8.2 ALB (Application Load Balancer)

* Target group → points to the nodes’ HTTP port (e.g. 5000).
* Health check path: `/health`
* ALB listeners:

  * `HTTP :80` or `HTTPS :443` → forward to target group.

### 8.3 Environment variables for public hostname

On each node, set:

```bash
export DCHAT_PUBLIC_HOST="my-dchat-alb-123456.eu-north-1.elb.amazonaws.com"
export DCHAT_PUBLIC_SCHEME="https"
```

This ensures:

* Any `302` produced by followers will have:

  ```http
  Location: https://my-dchat-alb-123456.eu-north-1.elb.amazonaws.com/chat
  ```

* The client always follows redirects back to the ALB (never to private IPs).

### 8.4 Client configuration for AWS

On your laptop / workstation, change in `client/chat_client.py`:

```python
CLUSTER_URL = "https://my-dchat-alb-123456.eu-north-1.elb.amazonaws.com"
```

Then run:

```bash
python client/chat_client.py
```


---

## 9. Limitations & Notes

* **Not production-grade RAFT**:

  * No disk persistence of terms/votes/log across restarts.
  * No log compaction/snapshotting.
  * Very simple timeout and retry behavior.

* **Users list is heuristic**:

  * It shows users who have produced messages recently.
  * Users are removed after 5 minutes of inactivity.
  * There’s no explicit “disconnect” event in HTTP mode.

* **Elections & temporary failures**:

  * During elections or just after node restarts, you may see transient errors:

    * Redirect loops
    * 404/5xx from nodes that are not fully ready yet
  * The client is designed to handle most of this gracefully by retrying and returning to the cluster URL.

* **Single-node writes**:

  * If only one node is alive in a 3-node cluster, RAFT will **refuse to commit new messages** (no majority).
  * This is by design to preserve safety.

---

## 10. Quick Troubleshooting

* **GUI says “Disconnected”**:

  * Check `/health` via curl or browser.
  * Make sure at least 2 of 3 nodes are running.
  * Check node logs for repeated “failed to win election” messages.

* **Messages do not sync between clients**:

  * Confirm `/messages` returns the same log from all nodes.
  * If yes → client poller or filter logic is the issue.
  * If no → RAFT replication isn’t working (check RAFT logs).

* **Redirect issues (too many redirects)**:

  * In local dev:

    * Make sure follower nodes’ `Location` headers point to **the actual leader HTTP port**.
  * In AWS:

    * Confirm `DCHAT_PUBLIC_HOST` is set correctly.
    * Verify ALB health checks and target status.



