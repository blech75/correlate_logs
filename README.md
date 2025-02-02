# GCP Logs Correlator Service

A Google Cloud Function that powers [GCP Logs Correlator](https://apartmenttherapy.retool.com/apps/6c843eda-66c3-11ed-bb5d-b33e22b89336/GCP%20Logs%20Correlator), a Retool app.

Also includes a standalone CLI tool (`./correlate_logs.py`) w/ a wrapper script
(`./correlate_logs`) for usage without a web UI.

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

### create .env.test file

```sh
# test-specific env vars
# also see ./.buildkite/pipeline.yml
TARGET_DIR="lib"
TEST_FILE_PATTERN='*_test.py'
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

NOTE: requires [`jq`](https://stedolan.github.io/jq/) via [Homebrew](https://brew.sh) (`brew install jq`)

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

---

## TODO

- reorg code in ./lib/\*
- protect REST API w/ proper auth
- ...
