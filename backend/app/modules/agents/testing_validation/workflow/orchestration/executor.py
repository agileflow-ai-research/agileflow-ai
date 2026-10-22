from concurrent.futures import ThreadPoolExecutor


AGENT4_N2_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="agent4-n2",
)


# Keep one orchestration lane available while another execution is inside the
# serialized model stages. ZERO_SHOT_LOCK and SEMANTIC_FACT_LOCK still prevent
# duplicate concurrent inference within each model stage.
AGENT4_N3_MAX_WORKERS = 2
AGENT4_N3_EXECUTOR = ThreadPoolExecutor(
    max_workers=AGENT4_N3_MAX_WORKERS,
    thread_name_prefix="agent4-n3",
)

# Semantic extraction is intentionally serialized because the local Qwen
# runtime is memory intensive. Keeping its queue separate prevents projects
# waiting for Qwen from occupying every general N3 orchestration worker.
AGENT4_N3_SEMANTIC_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="agent4-n3-semantic",
)


AGENT4_N4_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="agent4-n4",
)
