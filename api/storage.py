"""
In-Memory Storage Layer for Delivery-Bot API.
This module provides a simple in-memory storage implementation for pipelines
and runs. It uses thread-safe operations to support concurrent access from
multiple request handlers and background tasks.
The storage layer provides:
- Thread-safe CRUD operations for pipelines and runs
- In-memory persistence for the application lifetime
- Simple key-value storage with automatic indexing
- Consistent data access patterns
Note:
    This is a development/demo implementation. In production, this should
    be replaced with a proper database (PostgreSQL, MongoDB, etc.) for
    persistence across restarts and better scalability.
Classes:
    InMemoryDB: Thread-safe in-memory storage for pipelines and runs
Author: Nosa Omorodion
Version: 0.1.0
"""
from __future__ import annotations
from datetime import datetime
from threading import RLock
from typing import Dict, List, Optional
from .models import Pipeline, Run
class InMemoryDB:
    """
    Thread-safe in-memory database for pipelines and runs.
    Provides a simple storage layer with CRUD operations for the main
    application entities. Uses a reentrant lock to ensure thread safety
    when accessed from multiple FastAPI request handlers and background tasks.
    The database maintains separate collections for pipelines and runs,
    indexed by their unique IDs for fast lookups.
    Attributes:
        _pipelines (Dict[str, Pipeline]): Pipeline storage indexed by ID
        _runs (Dict[str, Run]): Run storage indexed by ID
        _lock (RLock): Reentrant lock for thread safety
    Thread Safety:
        All public methods are thread-safe and can be called concurrently
        from multiple threads without data corruption or race conditions.
    Note:
        Data is only persisted in memory and will be lost when the
        application restarts. This is suitable for development and testing
        but not for production use.
    """
    def __init__(self) -> None:
        """
        Initialize the in-memory database.
        Creates empty storage dictionaries and initializes the thread lock.
        """
        self._pipelines: Dict[str, Pipeline] = {}
        self._runs: Dict[str, Run] = {}
        self._lock = RLock()
    def create_pipeline(self, pipeline: Pipeline) -> Pipeline:
        """
        Create a new pipeline in storage.
        Stores the pipeline and returns the same instance. The pipeline's
        ID should already be set before calling this method.
        Args:
            pipeline (Pipeline): The pipeline to store
        Returns:
            Pipeline: The stored pipeline (same instance as input)
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        """
        with self._lock:
            self._pipelines[pipeline.id] = pipeline
            return pipeline
    def list_pipelines(self) -> List[Pipeline]:
        """
        Retrieve all pipelines from storage.
        Returns a list of all stored pipelines. The order is not guaranteed
        and may vary between calls.
        Returns:
            List[Pipeline]: All stored pipelines
        Thread Safety:
            This method is thread-safe and returns a snapshot of the data.
        """
        with self._lock:
            return list(self._pipelines.values())
    def get_pipeline(self, pipeline_id: str) -> Optional[Pipeline]:
        """
        Retrieve a specific pipeline by ID.
        Args:
            pipeline_id (str): Unique identifier of the pipeline
        Returns:
            Optional[Pipeline]: The pipeline if found, None otherwise
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        """
        with self._lock:
            return self._pipelines.get(pipeline_id)
    def update_pipeline(
        self, pipeline_id: str, updated: Pipeline
    ) -> Optional[Pipeline]:
        """
        Update an existing pipeline in storage.
        Updates the pipeline's data and automatically sets the updated_at
        timestamp to the current time.
        Args:
            pipeline_id (str): ID of the pipeline to update
            updated (Pipeline): New pipeline data
        Returns:
            Optional[Pipeline]: The updated pipeline if found, None if not found
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        Note:
            The updated_at timestamp is automatically set to the current UTC time.
        """
        with self._lock:
            if pipeline_id not in self._pipelines:
                return None
            updated.updated_at = datetime.utcnow()
            self._pipelines[pipeline_id] = updated
            return updated
    def delete_pipeline(self, pipeline_id: str) -> bool:
        """
        Delete a pipeline from storage.
        Removes the pipeline with the specified ID from storage.
        Args:
            pipeline_id (str): ID of the pipeline to delete
        Returns:
            bool: True if pipeline was found and deleted, False if not found
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        Note:
            This operation does not cascade to related runs. Consider whether
            associated runs should also be cleaned up.
        """
        with self._lock:
            return self._pipelines.pop(pipeline_id, None) is not None
    def create_run(self, run: Run) -> Run:
        """
        Create a new run in storage.
        Stores the run and returns the same instance. The run's ID should
        already be set before calling this method.
        Args:
            run (Run): The run to store
        Returns:
            Run: The stored run (same instance as input)
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        """
        with self._lock:
            self._runs[run.id] = run
            return run
    def get_run(self, run_id: str) -> Optional[Run]:
        """
        Retrieve a specific run by ID.
        Args:
            run_id (str): Unique identifier of the run
        Returns:
            Optional[Run]: The run if found, None otherwise
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        """
        with self._lock:
            return self._runs.get(run_id)
    def update_run(self, run_id: str, run: Run) -> Optional[Run]:
        """
        Update an existing run in storage.
        Updates the run's data including status, logs, and timing information.
        Args:
            run_id (str): ID of the run to update
            run (Run): New run data
        Returns:
            Optional[Run]: The updated run if found, None if not found
        Thread Safety:
            This method is thread-safe and can be called concurrently.
        Note:
            Unlike pipelines, runs do not automatically update timestamps.
            The caller is responsible for setting appropriate timing fields.
        """
        with self._lock:
            if run_id not in self._runs:
                return None
            self._runs[run_id] = run
            return run
# Global database instance
db = InMemoryDB()
