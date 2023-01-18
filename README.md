# GCP Logs Correlator

## Development Environment Setup

```sh
./scripts/venv create
./scripts/venv install-deps -r requirements.txt
./scripts/venv install-deps -r requirements_dev.txt
```

NOTE: `scripts/test`, `scripts/dev`, `scripts/deploy`, and `correlate_logs` are all venv-aware.

### create .env file

```sh
GOOGLE_CLOUD_PROJECT="gen-prod"
COLOREDLOGS_AUTO_INSTALL="True"
```

## Testing

```sh
./scripts/test -glv
```

## Local Dev Server

```sh
./scripts/dev
```

## Deployment

```sh
./scripts/deploy
```

## Development Environment Teardown

```sh
./scripts/venv destroy
```

---

## CLI usage

NOTE: requires `jq` (`brew install jq`)

### Find all log entries (via wrapper script)

Works similarly to the Web UI, iterating until complete.

```sh
./correlate_logs ~/Desktop/downloaded-logs.json
```

Show help via `./correlate_logs -h`.

### Find log entries manually

Run a single query:

```sh
# initial step uses a single log entry as the "seed" and outputs a "search state"
./.venv3/bin/python ./correlate_logs.py -l -f ~/Desktop/downloaded-logs.json > ~/Desktop/downloaded-logs.step1.json

# further steps start from previous state
./.venv3/bin/python ./correlate_logs.py -s -f ~/Desktop/downloaded-logs.step1.json > ~/Desktop/downloaded-logs.step2.json
```

Use `stdin` to accept search state:

```sh
# pipe results to another query
./.venv3/bin/python ./correlate_logs.py -l -f ~/Desktop/downloaded-logs.json | ./.venv3/bin/python ./correlate_logs.py -s -i

# read in state from earlier run
./.venv3/bin/python ./correlate_logs.py -s -i < ~/Desktop/downloaded-logs.step1.json
```

Show help via `./.venv3/bin/python ./correlate_logs.py -h`.

NOTE: `correlate_logs.py` is not venv-aware, so explicitly use the venv python or use `source .venv3/bin/activate`)

## Test `jq` programs

```sh
jq -f ./lib/gcp_logs_find.jq < ~/Desktop/downloaded-logs.json
jq -f ./lib/gcp_logs_find.jq < ~/Desktop/downloaded-logs.json | jq -f ./lib/gcp_logs_filter.jq
```
