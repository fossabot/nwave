# Performance Profiling Tests
from __future__ import annotations
from joblib import Parallel, delayed, parallel_backend
import os
import time
from tqdm.auto import tqdm
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
from concurrent import futures
from nwave import audio as pa
# from tests_profile.resources import profile_audio as pa
from nwave import Task, Config
from tests_profile import data


class CleanUp:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Search all files in directory with 'out' in the name
        count = 0
        for file in os.listdir(data.DATA_PATH):
            if "out" in file:
                os.remove(os.path.join(data.DATA_PATH, file))
                count += 1
        if count:
            print(f"[Clean-up] Removed {count} output files")


class Time:
    def __init__(self, verbose=False):
        self.start = None
        self.end = None
        self.verbose = verbose

    def delta(self) -> float:
        return self.end - self.start

    @staticmethod
    def t_format(val: float) -> str:
        # Formats time to μs, ms, or s depending on the value
        if val >= 1:
            return f"{val:.2f} s"
        elif val >= 1e-3:
            val *= 1e3
            return f"{val:.2f} ms"
        else:
            val *= 1e6
            return f"{val:.2f} μs"

    def __enter__(self) -> Time:
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end = time.perf_counter()
        if self.verbose:
            print(f"Elapsed: {self.t_format(self.delta())}")


def profile_audio(n_files: int, cfg: Config, batch_num: int = 1):
    # Get a list of files
    total = data.enum_batch(n_files, batch_num)
    with Time(verbose=True):
        for batch in tqdm(total):
            for in_f, out_f in batch:
                task = Task(in_f, out_f, cfg, overwrite=True)
                pa.process_file(task)


def profile_audio_parallel(n_files: int, cfg: Config, threads: int, batch_num: int = 1):
    total = data.enum_batch(n_files, batch_num)
    with Time(verbose=True):
        with Parallel(n_jobs=threads, backend='threading') as thread_pool:
            for batch in total:
                thread_pool(delayed(pa.process_file)(
                    Task(in_f, out_f, cfg, overwrite=True)
                ) for in_f, out_f in batch)


def profile_audio_threadpool(n_files: int, cfg: Config, threads: int, batch_num: int = 1):
    total = data.enum_batch(n_files, batch_num)
    with Time(verbose=True):
        with ThreadPoolExecutor(max_workers=threads) as executor:
            for batch in total:
                tasks = {executor.submit(
                    pa.process_file, Task(in_f, out_f, cfg, overwrite=True)
                ): (in_f, out_f) for (in_f, out_f) in batch}
            # Wait for all tasks to complete
            for future in tqdm(futures.as_completed(tasks)):
                if future.done():
                    pass
                    # print(future.result())
                if future.exception():
                    print(future.exception())


def profile_audio_thread_map(n_files: int, cfg: Config, threads: int, batch_num: int = 1):
    total = data.enum_batch(n_files, batch_num)
    with Time(verbose=True):
        with ThreadPoolExecutor(max_workers=threads) as thread_pool:
            for batch in total:
                jobs = [Task(in_f, out_f, cfg, overwrite=True) for in_f, out_f in batch]
                results = thread_pool.map(pa.process_file, jobs)


def clean_up():
    print("Cleaning up")
    # Search all files in directory with 'out' in the name
    count = 0
    for file in os.listdir(data.DATA_PATH):
        if "out" in file:
            os.remove(os.path.join(data.DATA_PATH, file))
            count += 1
    if count:
        print(f"Removed {count} files")


def main():
    cfg = Config(
        sample_rate=44100,
        resample_quality='HQ',
        silence_padding=(950, 950),
    )

    n_files = 64
    runs = 1
    threads = 20
    print(f'{n_files} files, {runs} batches')

    print('[Single]')
    profile_audio(n_files, cfg, batch_num=runs)
    print('-' * 3)
    clean_up()
    time.sleep(1)

    print('-' * 5)
    print(f'[Parallel] {threads} threads')
    profile_audio_parallel(n_files, cfg, threads, batch_num=runs)
    print('-' * 3)
    clean_up()
    time.sleep(1)

    print('-' * 5)
    print(f'[Parallel (Threadpool)] {threads} threads')
    profile_audio_threadpool(n_files, cfg, threads, batch_num=runs)
    print('-' * 3)
    clean_up()
    time.sleep(1)

    print('-' * 5)
    print(f'[Parallel (Thread Map)] {threads} threads')
    profile_audio_thread_map(n_files, cfg, threads, batch_num=runs)
    print('-' * 3)
    clean_up()
    time.sleep(1)


def load_main():
    from cpu_load_generator import load_all_cores
    from multiprocessing import Process
    import psutil

    print('-' * 5)
    print('Starting Load tests...')
    print('Loading 16 logical cores')
    p = Process(target=load_all_cores, args=(30, 0.99))
    p.start()
    time.sleep(3)  # Wait for load
    cur_load = psutil.cpu_percent(1)
    print(f'Load reached, current load: {cur_load:.4f} %')

    print('-' * 5)
    print('(With load) [Single]')
    profile_audio(n_files, batch_num=runs)
    print('-' * 5)
    print(f'(With load) [Parallel] {threads} threads')
    profile_audio_parallel(n_files, threads, batch_num=runs)
    p.terminate()


if __name__ == '__main__':
    # clean_up()
    main()
