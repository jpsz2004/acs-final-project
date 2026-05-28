"""
Concurrency primitives for Historia 8.

ReadWriteLock — writer-priority read/write lock
================================================
Allows multiple concurrent readers OR a single exclusive writer.

Writer-priority semantics
--------------------------
When at least one writer is waiting, new readers block even if the
lock is currently free.  This prevents writer starvation: readers
cannot "flood" the lock indefinitely while writers keep queuing.

Internal state
--------------
- _readers_active  : number of threads currently reading.
- _writer_active   : True while a writer holds the lock.
- _writers_waiting : number of threads waiting to write.

All state is guarded by a single threading.Condition whose internal
Lock serialises every state mutation.

Protocol
--------
Reader thread:
    lock.acquire_read()
    try:
        ... read shared data ...
    finally:
        lock.release_read()

Writer thread:
    lock.acquire_write()
    try:
        ... mutate shared data ...
    finally:
        lock.release_write()
"""

from __future__ import annotations

import threading


class ReadWriteLock:
    """
    Reader-writer lock with writer priority.

    Multiple readers may hold the lock simultaneously.
    A writer requires exclusive access: no readers, no other writers.
    New readers are blocked while any writer is waiting or active.
    """

    def __init__(self) -> None:
        self._condition = threading.Condition(threading.Lock())
        self._readers_active: int = 0
        self._writer_active: bool = False
        self._writers_waiting: int = 0

    # ------------------------------------------------------------------
    # Read side
    # ------------------------------------------------------------------

    def acquire_read(self) -> None:
        """
        Block until a read lock can be acquired.

        Blocked when: a writer is active OR writers are waiting.
        This is the writer-priority invariant.
        """
        with self._condition:
            # Wait while any writer has priority (waiting or active).
            while self._writer_active or self._writers_waiting > 0:
                self._condition.wait()
            self._readers_active += 1

    def release_read(self) -> None:
        """
        Release a previously acquired read lock.

        If this was the last active reader, notify waiting writers.
        """
        with self._condition:
            self._readers_active -= 1
            if self._readers_active == 0:
                # Wake waiting writers (and readers, though they will
                # re-check the predicate and go back to sleep if a
                # writer is still waiting).
                self._condition.notify_all()

    # ------------------------------------------------------------------
    # Write side
    # ------------------------------------------------------------------

    def acquire_write(self) -> None:
        """
        Block until an exclusive write lock can be acquired.

        Registers as a waiting writer first so that new readers are
        blocked immediately (writer-priority), then waits until both
        active readers and any active writer finish.
        """
        with self._condition:
            self._writers_waiting += 1
            try:
                while self._readers_active > 0 or self._writer_active:
                    self._condition.wait()
                self._writer_active = True
            finally:
                self._writers_waiting -= 1

    def release_write(self) -> None:
        """
        Release a previously acquired write lock.

        Notifies ALL waiting threads so readers can run concurrently
        once no more writers are waiting.
        """
        with self._condition:
            self._writer_active = False
            self._condition.notify_all()
