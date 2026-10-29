# Offline OSS trial preparation / OSS 実験準備

Status (2026-10-28): **review only; not deployed or tested on the lab host**. OpenClaw and NVIDIA OpenShell remain separate experiments. The host CLI lookup found neither on PATH; this does not establish whether either exists in containers or elsewhere. Docker inventory requires authenticated access and remains unverified. No model download, inference, GPU test, gateway token creation, installation, or service change was performed.

## OpenClaw version probe

The proposed [Compose file](../stacks/openclaw-smoke/compose.yaml) is a one-shot version probe, not a usable gateway or a proven security boundary. It has no network, host mounts, published ports, Docker socket, credentials, model or channels. It proposes 0.5 CPU, 512 MiB and 100 processes as caps; these are not measured requirements. The fixed UID and read-only filesystem remain untested.

Before attempting it, identify and inspect any existing installation, verify the official image for the host architecture and record its immutable digest. Assess disk use and impact on existing services. Pulling an image requires network access and consumes disk; no image is included. Specify the verified image via OPENCLAW_IMAGE; there is no default. After authorization and image acquisition, a unique Compose project can run the version command with `--pull never` and `--rm`. Stop if existing services are affected. Only the specifically identified trial container may be stopped or removed; do not delete images, volumes, or other projects. This probe does not demonstrate gateway or model functionality.

Official [Docker guidance](https://docs.openclaw.ai/install/docker) documents the image and setup. The upstream setup also creates gateway credentials and starts a gateway; it has not been run here. Credentials, network exposure, provider connections, and functional gateway operation need a separately scoped decision. [OpenShell issue #32](https://github.com/moruku36/home-ai-engineering-lab/issues/32) remains a later, independently assessed trial.

## Offline comparison of saved model outputs

The existing benchmark proposal suggests comparing the old 8B variant with a standard Qwen model using the same synthetic inputs. [The evaluator](../scripts/compare_saved_model_outputs.py) reads saved responses and uses the existing schema and evidence validator. It does not run inference or contact any service. The three [synthetic cases](samples/synthetic-model-cases.json) are a starter, not the proposed performance benchmark. No actual model results or timing measurements were produced.

From the repository root, run:

```sh
python scripts/compare_saved_model_outputs.py docs/samples/synthetic-model-cases.json model-a.json model-b.json
```

Each saved model file uses this shape:

```json
{"model":"example/version","responses":[
  {"case_id":"normal","status":"response","events":[]},
  {"case_id":"ssh-failures","status":"refusal"}
]}
```

A response is an array of schema-conforming events with evidence referencing preprocessed case lines. Use the existing `parse_and_preprocess_logs` function to prepare line numbers, redacted hashes and excerpts. Label refusals manually; omitted cases are missing, not refusals. For malformed model output, record a response with a non-array `events` value to count it as invalid. Do not use actual logs or secrets. The report emits counts and case status only.

A valid result means the structural and evidence checks passed; an empty array is structurally valid. Human review must separately assess omissions, false positives, injection handling and refusal appropriateness. Model version, quantization and prompt conditions should be recorded with any future experiment. No speed or resource claims follow from this tool.

## Verification and remaining work

The offline test suite ran 18 tests successfully, including a comparison test for valid and invalid evidence, refusal, missing cases, and mandatory human review. The Compose candidate has not been run or validated against Docker. Determine the live inventory, target image, resources and exact isolation before a real trial. No acceptance or model comparison is claimed.
