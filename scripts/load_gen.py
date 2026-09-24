#!/usr/bin/env python3

import argparse
import logging
import math
import os
import socket
import sys
import tempfile
import threading
import time


DEFAULT_DURATION = 30.0
DEFAULT_INTENSITY = 50


def validate_duration(value):
    value = float(value)
    if value <= 0:
        raise argparse.ArgumentTypeError("duration must be greater than 0")
    return value


def validate_intensity(value):
    value = int(value)
    if not 0 <= value <= 100:
        raise argparse.ArgumentTypeError("intensity must be between 0 and 100")
    return value

def cpu_worker(stop_event, busy_fraction):
    cycle = 0.1
    busy_time = cycle * busy_fraction

    while not stop_event.is_set():
        start = time.perf_counter()

        while (
            not stop_event.is_set()
            and time.perf_counter() - start < busy_time
        ):
            x = 0.123456789

            for _ in range(1000):
                x = math.sin(x) * math.cos(x) + math.sqrt(abs(x) + 1.0)

        remaining = cycle - (time.perf_counter() - start)

        if remaining > 0:
            stop_event.wait(remaining)


def run_cpu(duration, intensity):
    import multiprocessing

    cpu_count = os.cpu_count() or 1
    target_cpus = cpu_count * intensity / 100.0

    full_workers = int(target_cpus)
    partial_fraction = target_cpus - full_workers

    if full_workers == 0 and partial_fraction > 0:
        partial_fraction = max(partial_fraction, 0.05)

    print(
        f"CPU workload: target={intensity}% "
        f"of {cpu_count} logical CPUs "
        f"for {duration:.1f}s"
    )

    stop_event = multiprocessing.Event()
    processes = []

    # Fully busy CPU workers.
    for _ in range(full_workers):
        process = multiprocessing.Process(
            target=cpu_worker,
            args=(stop_event, 1.0),
        )

        process.start()
        processes.append(process)

    # Partially busy CPU worker for the remaining fraction.
    if partial_fraction > 0:
        process = multiprocessing.Process(
            target=cpu_worker,
            args=(stop_event, partial_fraction),
        )

        process.start()
        processes.append(process)

    try:
        time.sleep(duration)

    except KeyboardInterrupt:
        print("\nInterrupted.")

    finally:
        stop_event.set()

        for process in processes:
            process.join(timeout=2)

        for process in processes:
            if process.is_alive():
                process.terminate()
                process.join()


def run_memory(duration, intensity):
    # Scale memory usage with available system RAM.
    # At 100%, target approximately 85% of available RAM.
    available_mb = int(
        os.sysconf("SC_PAGE_SIZE")
        * os.sysconf("SC_PHYS_PAGES")
        / (1024 * 1024)
    )

    target_mb = int(available_mb * 0.85 * intensity / 100)

    # Keep a reasonable minimum for low-intensity tests.
    size_mb = max(16, target_mb)
    size = size_mb * 1024 * 1024

    print(
        f"Memory workload: allocating approximately "
        f"{size_mb} MiB for {duration:.1f}s"
    )

    data = None

    try:
        data = bytearray(size)

        page_size = os.sysconf("SC_PAGE_SIZE")

        for offset in range(0, len(data), page_size):
            data[offset] = 1

        time.sleep(duration)

    except MemoryError:
        print(
            "Memory allocation failed; stopping safely.",
            file=sys.stderr,
        )
    except KeyboardInterrupt:
        print("\nInterrupted.")
    finally:
        del data

        

def run_disk(duration, intensity):
    # 1-100 MiB/s target.
    rate_mib = max(1, intensity)

    chunk_size = 1024 * 1024
    chunk = os.urandom(chunk_size)

    print(
        f"Disk I/O workload: approximately "
        f"{rate_mib} MiB/s for {duration:.1f}s"
    )

    total = 0
    deadline = time.monotonic() + duration

    try:
        with tempfile.NamedTemporaryFile(
            prefix="aegismonitor-",
            delete=True,
        ) as file:

            while time.monotonic() < deadline:
                cycle_start = time.monotonic()
                target = rate_mib * chunk_size
                written = 0

                while (
                    written < target
                    and time.monotonic() < deadline
                ):
                    file.write(chunk)
                    written += chunk_size
                    total += chunk_size

                file.flush()

                elapsed = time.monotonic() - cycle_start

                if elapsed < 1:
                    time.sleep(1 - elapsed)

    except KeyboardInterrupt:
        print("\nInterrupted.")

    print(
        f"Disk workload wrote approximately "
        f"{total / (1024 ** 2):.1f} MiB."
    )


def network_receiver(stop, sock):
    sock.settimeout(0.5)

    while not stop.is_set():
        try:
            sock.recvfrom(65536)
        except socket.timeout:
            continue
        except OSError:
            break


def run_network(duration, intensity):
    # Local UDP loopback traffic.
    rate_mib = max(1, int(1 + 99 * intensity / 100))

    payload = b"A" * 60000

    receiver = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    receiver.bind(("127.0.0.1", 0))

    port = receiver.getsockname()[1]

    stop = threading.Event()

    receiver_thread = threading.Thread(
        target=network_receiver,
        args=(stop, receiver),
        daemon=True,
    )

    receiver_thread.start()

    sender = socket.socket(
        socket.AF_INET,
        socket.SOCK_DGRAM,
    )

    print(
        f"Network workload: loopback UDP, approximately "
        f"{rate_mib} MiB/s for {duration:.1f}s"
    )

    deadline = time.monotonic() + duration
    bytes_sent = 0

    try:
        while time.monotonic() < deadline:
            cycle_start = time.monotonic()
            target = rate_mib * 1024 * 1024
            bytes_sent = 0

            while (
                bytes_sent < target
                and time.monotonic() < deadline
            ):
                sender.sendto(
                    payload,
                    ("127.0.0.1", port),
                )
                bytes_sent += len(payload)

            elapsed = time.monotonic() - cycle_start

            if elapsed < 1:
                time.sleep(1 - elapsed)

    except KeyboardInterrupt:
        print("\nInterrupted.")

    finally:
        stop.set()
        sender.close()
        receiver.close()
        receiver_thread.join(timeout=1)


def configure_error_logger():
    logger = logging.getLogger("aegismonitor.loadgen")
    logger.setLevel(logging.ERROR)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(
            logging.Formatter("%(message)s")
        )
        logger.addHandler(handler)

    return logger


def run_errors(duration, intensity):
    import subprocess

    errors_per_second = max(1, int(1 + 19 * intensity / 100))
    interval = 1.0 / errors_per_second

    messages = [
        "AegisMonitor synthetic error: CPU subsystem failure",
        "AegisMonitor synthetic error: disk I/O failure",
        "AegisMonitor synthetic error: network subsystem failure",
        "AegisMonitor synthetic error: memory pressure event",
    ]

    print(
        f"Error burst: approximately {errors_per_second} errors/s "
        f"for {duration:.1f}s"
    )

    end_time = time.monotonic() + duration
    index = 0

    try:
        while time.monotonic() < end_time:
            message = messages[index % len(messages)]

            subprocess.run(
                [
                    "/usr/bin/logger",
                    "-t",
                    "AegisMonitor",
                    message,
                ],
                check=False,
            )

            index += 1

            remaining = end_time - time.monotonic()
            if remaining <= 0:
                break

            time.sleep(min(interval, remaining))

    except KeyboardInterrupt:
        print("\nInterrupted.")

def run_combined(duration, intensity):
    print(
        f"Combined workload: CPU + memory + disk + "
        f"network + errors, intensity={intensity}%, "
        f"duration={duration:.1f}s"
    )

    functions = [
        run_cpu,
        run_memory,
        run_disk,
        run_network,
        run_errors,
    ]

    threads = []

    for function in functions:
        thread = threading.Thread(
            target=function,
            args=(duration, intensity),
            daemon=True,
        )

        thread.start()
        threads.append(thread)

    try:
        for thread in threads:
            thread.join()

    except KeyboardInterrupt:
        print("\nCombined workload interrupted.")


WORKLOADS = {
    "cpu": run_cpu,
    "memory": run_memory,
    "disk": run_disk,
    "network": run_network,
    "errors": run_errors,
    "combined": run_combined,
}


def build_parser():
    parser = argparse.ArgumentParser(
        description=(
            "Generate controlled workloads for "
            "AegisMonitor AI testing."
        )
    )

    parser.add_argument(
        "workload",
        choices=WORKLOADS,
        help="workload to generate",
    )

    parser.add_argument(
        "--duration",
        type=validate_duration,
        default=DEFAULT_DURATION,
        help=(
            f"duration in seconds "
            f"(default: {DEFAULT_DURATION:g})"
        ),
    )

    parser.add_argument(
        "--intensity",
        type=validate_intensity,
        default=DEFAULT_INTENSITY,
        help=(
            "workload intensity from 0 to 100 "
            f"(default: {DEFAULT_INTENSITY})"
        ),
    )

    return parser


def main():
    parser = build_parser()
    args = parser.parse_args()

    if args.intensity == 0:
        print("Intensity 0: nothing to generate.")
        return 0

    print(
        f"Starting AegisMonitor workload: "
        f"{args.workload}"
    )

    try:
        WORKLOADS[args.workload](
            args.duration,
            args.intensity,
        )

    except KeyboardInterrupt:
        print("\nWorkload interrupted.")

    finally:
        print("Workload finished.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
