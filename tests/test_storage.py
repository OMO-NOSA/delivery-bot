import pytest
import threading
import time
from datetime import datetime, timedelta
from api.storage import InMemoryDB
from api.models import Pipeline, Run, RunStatus, Step, StepType


class TestInMemoryDB:
    """Test InMemoryDB storage operations."""
    
    def setup_method(self):
        """Set up fresh DB instance for each test."""
        self.db = InMemoryDB()
    
    def test_create_pipeline(self):
        """Test creating a pipeline."""
        pipeline = Pipeline(
            name="test-pipeline",
            repo_url="https://github.com/example/repo",
            steps=[Step(name="test", type=StepType.run, command="echo")]
        )
        
        result = self.db.create_pipeline(pipeline)
        
        assert result.id == pipeline.id
        assert result.name == "test-pipeline"
        assert len(self.db._pipelines) == 1
    
    def test_list_pipelines_empty(self):
        """Test listing pipelines when DB is empty."""
        pipelines = self.db.list_pipelines()
        assert pipelines == []
    
    def test_list_pipelines_with_data(self):
        """Test listing pipelines with data."""
        p1 = Pipeline(name="pipeline1", repo_url="https://github.com/example/repo1")
        p2 = Pipeline(name="pipeline2", repo_url="https://github.com/example/repo2")
        
        self.db.create_pipeline(p1)
        self.db.create_pipeline(p2)
        
        pipelines = self.db.list_pipelines()
        assert len(pipelines) == 2
        names = [p.name for p in pipelines]
        assert "pipeline1" in names
        assert "pipeline2" in names
    
    def test_get_pipeline_exists(self):
        """Test getting an existing pipeline."""
        pipeline = Pipeline(name="test", repo_url="https://github.com/example/repo")
        created = self.db.create_pipeline(pipeline)
        
        retrieved = self.db.get_pipeline(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.name == "test"
    
    def test_get_pipeline_not_exists(self):
        """Test getting a non-existent pipeline."""
        result = self.db.get_pipeline("non-existent-id")
        assert result is None
    
    def test_update_pipeline_exists(self):
        """Test updating an existing pipeline."""
        original = Pipeline(name="original", repo_url="https://github.com/example/repo")
        created = self.db.create_pipeline(original)
        
        # Create updated version
        updated = Pipeline(
            id=created.id,
            name="updated",
            repo_url="https://github.com/example/updated-repo",
            created_at=created.created_at
        )
        
        result = self.db.update_pipeline(created.id, updated)
        
        assert result is not None
        assert result.name == "updated"
        assert str(result.repo_url) == "https://github.com/example/updated-repo"
        assert result.updated_at > created.updated_at
        
        # Verify it's updated in storage
        retrieved = self.db.get_pipeline(created.id)
        assert retrieved.name == "updated"
    
    def test_update_pipeline_not_exists(self):
        """Test updating a non-existent pipeline."""
        pipeline = Pipeline(name="test", repo_url="https://github.com/example/repo")
        
        result = self.db.update_pipeline("non-existent-id", pipeline)
        
        assert result is None
    
    def test_delete_pipeline_exists(self):
        """Test deleting an existing pipeline."""
        pipeline = Pipeline(name="test", repo_url="https://github.com/example/repo")
        created = self.db.create_pipeline(pipeline)
        
        result = self.db.delete_pipeline(created.id)
        
        assert result is True
        assert self.db.get_pipeline(created.id) is None
        assert len(self.db._pipelines) == 0
    
    def test_delete_pipeline_not_exists(self):
        """Test deleting a non-existent pipeline."""
        result = self.db.delete_pipeline("non-existent-id")
        assert result is False
    
    def test_create_run(self):
        """Test creating a run."""
        run = Run(pipeline_id="pipeline-123")
        
        result = self.db.create_run(run)
        
        assert result.id == run.id
        assert result.pipeline_id == "pipeline-123"
        assert len(self.db._runs) == 1
    
    def test_get_run_exists(self):
        """Test getting an existing run."""
        run = Run(pipeline_id="pipeline-123")
        created = self.db.create_run(run)
        
        retrieved = self.db.get_run(created.id)
        
        assert retrieved is not None
        assert retrieved.id == created.id
        assert retrieved.pipeline_id == "pipeline-123"
    
    def test_get_run_not_exists(self):
        """Test getting a non-existent run."""
        result = self.db.get_run("non-existent-id")
        assert result is None
    
    def test_update_run_exists(self):
        """Test updating an existing run."""
        original = Run(pipeline_id="pipeline-123")
        created = self.db.create_run(original)
        
        # Update run with new status and logs
        updated = Run(
            id=created.id,
            pipeline_id=created.pipeline_id,
            status=RunStatus.running,
            started_at=datetime.utcnow(),
            logs=["Step 1 started"]
        )
        
        result = self.db.update_run(created.id, updated)
        
        assert result is not None
        assert result.status == RunStatus.running
        assert result.started_at is not None
        assert len(result.logs) == 1
        
        # Verify it's updated in storage
        retrieved = self.db.get_run(created.id)
        assert retrieved.status == RunStatus.running
    
    def test_update_run_not_exists(self):
        """Test updating a non-existent run."""
        run = Run(pipeline_id="pipeline-123")
        
        result = self.db.update_run("non-existent-id", run)
        
        assert result is None


class TestInMemoryDBThreadSafety:
    """Test thread safety of InMemoryDB operations."""
    
    def setup_method(self):
        """Set up fresh DB instance for each test."""
        self.db = InMemoryDB()
        self.results = []
        self.errors = []
    
    def test_concurrent_pipeline_creation(self):
        """Test concurrent pipeline creation is thread-safe."""
        def create_pipeline(name_suffix):
            try:
                pipeline = Pipeline(
                    name=f"pipeline-{name_suffix}",
                    repo_url="https://github.com/example/repo"
                )
                result = self.db.create_pipeline(pipeline)
                self.results.append(result)
            except Exception as e:
                self.errors.append(e)
        
        # Create 10 threads that create pipelines concurrently
        threads = []
        for i in range(10):
            thread = threading.Thread(target=create_pipeline, args=(i,))
            threads.append(thread)
        
        # Start all threads
        for thread in threads:
            thread.start()
        
        # Wait for all threads to complete
        for thread in threads:
            thread.join()
        
        # Verify results
        assert len(self.errors) == 0, f"Errors occurred: {self.errors}"
        assert len(self.results) == 10
        assert len(self.db.list_pipelines()) == 10
        
        # Verify all pipelines have unique IDs
        ids = [p.id for p in self.results]
        assert len(set(ids)) == 10  # All unique
    
    def test_concurrent_read_write_operations(self):
        """Test concurrent read and write operations are thread-safe."""
        # Create initial pipeline
        initial_pipeline = Pipeline(name="initial", repo_url="https://github.com/example/repo")
        created = self.db.create_pipeline(initial_pipeline)
        
        def reader():
            """Thread that reads pipelines repeatedly."""
            try:
                for _ in range(50):
                    pipelines = self.db.list_pipelines()
                    self.results.append(len(pipelines))
                    time.sleep(0.001)  # Small delay
            except Exception as e:
                self.errors.append(e)
        
        def writer():
            """Thread that creates pipelines repeatedly."""
            try:
                for i in range(10):
                    pipeline = Pipeline(
                        name=f"writer-{i}",
                        repo_url="https://github.com/example/repo"
                    )
                    self.db.create_pipeline(pipeline)
                    time.sleep(0.005)  # Small delay
            except Exception as e:
                self.errors.append(e)
        
        # Start reader and writer threads
        reader_thread = threading.Thread(target=reader)
        writer_thread = threading.Thread(target=writer)
        
        reader_thread.start()
        writer_thread.start()
        
        reader_thread.join()
        writer_thread.join()
        
        # Verify no errors occurred
        assert len(self.errors) == 0, f"Errors occurred: {self.errors}"
        
        # Final pipeline count should be initial + 10 written
        final_count = len(self.db.list_pipelines())
        assert final_count == 11
    
    def test_concurrent_run_updates(self):
        """Test concurrent run updates are thread-safe."""
        # Create initial run
        run = Run(pipeline_id="pipeline-123")
        created = self.db.create_run(run)
        
        def update_run_logs(thread_id):
            """Thread that updates run logs."""
            try:
                for i in range(20):
                    current_run = self.db.get_run(created.id)
                    if current_run:
                        current_run.logs.append(f"Thread {thread_id} - Update {i}")
                        self.db.update_run(created.id, current_run)
                    time.sleep(0.001)
            except Exception as e:
                self.errors.append(e)
        
        # Start multiple threads updating the same run
        threads = []
        for i in range(5):
            thread = threading.Thread(target=update_run_logs, args=(i,))
            threads.append(thread)
        
        for thread in threads:
            thread.start()
        
        for thread in threads:
            thread.join()
        
        # Verify no errors occurred
        assert len(self.errors) == 0, f"Errors occurred: {self.errors}"
        
        # Verify final run has logs from all threads
        final_run = self.db.get_run(created.id)
        assert final_run is not None
        assert len(final_run.logs) == 100  # 5 threads * 20 updates each
