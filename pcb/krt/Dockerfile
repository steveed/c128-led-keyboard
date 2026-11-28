# KiCadRoutingTools (github.com/drandyhaas/KiCadRoutingTools), for placing the rev 3 board's
# electronics.  Built native for the host (arm64 on Apple silicon: an amd64 image ran the
# placer ~10x slower under emulation) with the tools baked in at a pinned commit and their
# Rust router compiled here, so nothing is mounted from, or built into, a checkout.
#   docker compose build krt                       (KRT_COMMIT in docker-compose.yml to update)
#   docker compose run --rm krt py_placer/place_simple.py /repo/build/placement/fixed.kicad_pcb ...
ARG KRT_COMMIT=be713c55eb8698bf056c9b64a0827528268bca5f

FROM rust:1.83-slim-bookworm AS router
ARG KRT_COMMIT
RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates python3 \
    && rm -rf /var/lib/apt/lists/*
RUN git clone --filter=blob:none https://github.com/drandyhaas/KiCadRoutingTools.git /krt \
    && git -C /krt checkout --quiet "$KRT_COMMIT" \
    && rm -rf /krt/.git
WORKDIR /krt/rust_router
# what build_router.py --from-source does on Linux: cargo, then the library beside the crate
RUN cargo build --release \
    && cp target/release/libgrid_router.so grid_router.so \
    && rm -rf target

FROM python:3.12.7-slim-bookworm
RUN pip install --no-cache-dir numpy==2.1.3 scipy==1.14.1 shapely==2.0.6 Pillow==11.0.0 ortools==9.15.6755
COPY --from=router /krt /krt
ENV PYTHONUTF8=1
WORKDIR /krt
ENTRYPOINT ["python3", "-X", "utf8"]
