# whisper.cpp for MinusPod — AMD/ROCm (optional, upstream-only)

## Positioning (post advisor verdict 01.11.2026)

- **S0 execution path = CPU.** `fed` has 32 cores; MinusPod's bundled CPU whisper
  (`WHISPER_BACKEND=local`, image `ttlequals0/minuspod:cpu`) transcribes the two
  overnight feeds within the window. No ROCm image to build or maintain, and the
  7900 XTX stays exclusively with fed's always-on local LLM stack.
- **AMD/ROCm here = an upstream PR + an optional late accelerator.** `fed` ships an
  **AMD Radeon RX 7900 XTX (gfx1100)**, which MinusPod's CUDA-only whisper images can't
  drive. The ROCm build therefore lives here two ways: (a) an upstream PR so ttlequals0/MinusPod's
  CUDA-only whisper compose gets an AMD sibling; (b) an optional accelerator on fed — adopted
  **only if a CPU benchmark shows wall-clock actually hurting**. It is **not** the production
  execution path.
- **Why not a shared-GPU daemon on fed:** fed is the bare-metal **cornerstone** (PostgreSQL,
  the on-machine orchestrator, and the always-on local LLM stack all share the one 7900 XTX). A
  persistent whisper daemon wedging HIP could trigger a GPU reset that takes down production with
  no on-call. So the design is: **scheduled worker, CPU-first, GPU optional.**

## Files
- `Dockerfile.amd` — whisper.cpp built with `-DGGML_HIP=1 -DAMDGPU_TARGETS=gfx1100`.
- `docker-compose.whisper.amd.yml` — podman ROCm whisper server (shared `podcast-net`).

## S0 (CPU) deploy on fed
```bash
cd /srv/personal/minuspod            # git clone of this fork
mkdir -p /mnt/raid10/podcast         # audio + models here, off the PG host dirs
# MinusPod's own CPU compose — bundled CPU whisper, no external server needed:
podman compose -f docker-compose.cpu.yml up -d
# .env keeps WHISPER_BACKEND=local (the image bundles CPU whisper). No GPU, no ROCm image.
```

## Adopt ROCm only later (optional) — when a CPU benchmark hurts
Fed is bare-metal, so `/dev/kfd` is directly mountable.
```bash
cd /srv/personal/minuspod
podman compose -f docker-compose.whisper.amd.yml build      # ~15-25 min, rocm base ~3GB
mkdir -p models && cd models && curl -LO \
  https://huggingface.co/ggml-org/whisper/resolve/main/ggml-large-v3-turbo.bin && cd ..
podman compose -f docker-compose.whisper.amd.yml up -d        # mounts /dev/kfd + /dev/dri
```

## Wire MinusPod for the external whisper server (ROCm or CPU whisper.cpp)
```
WHISPER_BACKEND=openai-api
WHISPER_API_BASE_URL=http://whisper-server:8765/v1
WHISPER_DEVICE=cpu          # GPU work happens inside the whisper container
```
Both MinusPod and whisper-server must resolve each other: add
`networks: [podcast-net]` to the minuspod service in `docker-compose.cpu.yml`
and share the same `podcast-net` both stacks declare (see the note at the top of
`docker-compose.whisper.yml`). MinusPod's own compose files have no shared-net
block, so this join is a manual step.

## Notes
- ROCm 7 supports gfx1100 natively; set `HSA_OVERRIDE_GFX_VERSION=11.0.0` only if
  the server fails to see the card.
- Larger throughput than CPU *if* the GPU is worth the maintenance + shared-host risk.
- CPU execution for MinusPod stays `docker-compose.cpu.yml` (`WHISPER_BACKEND=local`).
