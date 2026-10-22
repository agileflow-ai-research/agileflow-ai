from concurrent.futures import ThreadPoolExecutor


# One process-local queue serializes Agent 3's CPU-heavy model workloads.
AGENT3_PREPARATION_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="agent3-preparation",
)
