# AMD/ROCm whisper.cpp for MinusPod (fed)

MinusPod ships CUDA-only whisper images. `fed` has an **AMD Radeon RX 7900 XTX
(gfx1100)**, so we run whisper.cpp built against HIP/ROCm and point MinusPod's
`openai-api` whisper backend at it.

## Files
- `Dockerfile.amd` — whisper.cpp built with `-DGGML_HIP=1 -DAMDGPU_TARGETS=gfx1100`.
- `docker-compose.whisper.amd.yml` — podman ROCm server on shared `podcast-net`.

## Deploy on fed (bare-metal, so `/dev/kfd` is directly mountable)
```bash
cd /srv/personal/minuspod            # git clone of this fork
podman compose -f docker-compose.whisper.amd.yml build      # ~15-25 min, rocm base ~3GB
# download the model once:
mkdir -p models && cd models && curl -LO \
  https://huggingface.co/ggml-org/whisper/resolve/main/ggml-large-v3-turbo.bin && cd ..
podman compose -f docker-compose.whisper.amd.yml up -d
```

## Wire MinusPod (.env)
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
- Faster whisper throughput than CPU; model = large-v3-turbo (adjust in Dockerfile CMD).
- CPU fallback for MinusPod stays as-is (`docker-compose.cpu.yml`).
