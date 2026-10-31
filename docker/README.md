# Docker target (Proposal A)

## Quick start

```bash
# Build
docker build -f docker/Dockerfile -t inferkern:dev .

# Run with bundled mock web-server goal (no API key needed)
docker run --rm -p 8080:80 inferkern:dev

# Verify from another terminal
curl http://localhost:8080/

# Run with a custom goal mounted from host
docker run --rm -p 8080:80 \
  -v $(pwd)/examples/goals/web-server/goal.llm.yaml:/etc/inferkern/goal.yaml:ro \
  -e LLM_ENDPOINT -e LLM_API_KEY \
  inferkern:dev

# Dry-run (validate goal parsing only)
docker run --rm inferkern:dev --dry-run --goal /app/examples/goals/web-server/goal.yaml

# Check convergence without LLM (run acceptance checks once)
docker run --rm inferkern:dev --once --goal /app/examples/goals/web-server/goal.yaml
```
