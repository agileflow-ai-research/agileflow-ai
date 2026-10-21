from concurrent.futures import ThreadPoolExecutor


AGENT4_N2_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="agent4-n2",
)


AGENT4_N3_EXECUTOR = ThreadPoolExecutor(
    max_workers=1,
    thread_name_prefix="agent4-n3",
)


AGENT4_N4_EXECUTOR = ThreadPoolExecutor(
    max_workers=2,
    thread_name_prefix="agent4-n4",
)
