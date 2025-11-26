# DChat RAFT Client

You can use simple HTTP tools (curl, Postman, Python requests, etc.) to interact
with the backend nodes.

## Examples

Send a chat message:

```bash
curl -X POST http://127.0.0.1:9000/chat \
  -H "Content-Type: application/json" \
  -d '{"user": "nooa", "text": "hello from client"}'
```

Fetch all messages:

```bash
curl http://127.0.0.1:9000/messages
```

Check health:

```bash
curl http://127.0.0.1:9000/health
```
