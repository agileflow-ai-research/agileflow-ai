from concurrent.futures import ThreadPoolExecutor


AGENT1_N2_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="agent1-n2",
)

AGENT1_N3_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="agent1-n3",
)
