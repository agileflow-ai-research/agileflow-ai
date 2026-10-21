from concurrent.futures import ThreadPoolExecutor


AGENT4_N2_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="agent4-n2",
)
