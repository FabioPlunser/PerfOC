# models.py
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Float,
    Boolean,
    ForeignKey,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import json

SQLALCHEMY_DATABASE_URL = "sqlite:///./benchmark.db"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class Benchmark(Base):
    __tablename__ = "benchmarks"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String)
    source_code_path = Column(String, nullable=False)
    compile_arguments = Column(String)
    output_path = Column(String, nullable=False)
    execution_folder = Column(String)
    is_remote = Column(Boolean, default=False)
    host_id = Column(Integer, ForeignKey("hosts.id"))
    metrics = Column(JSON)  # Store metrics to track as JSON
    plots = Column(JSON)  # Store plot configurations as JSON
    min_repetitions = Column(Integer, default=5)
    max_repetitions = Column(Integer, default=30)
    confidence_level = Column(Float, default=0.95)  # For dynamic repetition adjustment
    command_line_args_sets = Column(JSON)  # Store sets of command line arguments
    compile_time_definitions = Column(JSON, default=list)


class Host(Base):
    __tablename__ = "hosts"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    address = Column(String, nullable=False)
    username = Column(String, nullable=False)
    password = Column(String)  # Consider encryption
    ssh_key_path = Column(String)
    use_slurm = Column(Boolean, default=False)
    slurm_template = Column(String)  # Template for Slurm job files


class BenchmarkResult(Base):
    __tablename__ = "benchmark_results"

    id = Column(Integer, primary_key=True, index=True)
    benchmark_id = Column(Integer, ForeignKey("benchmarks.id"))
    timestamp = Column(String)
    results_data_json = Column(String)  # Store JSON as string

    @property
    def results_data(self):
        return json.loads(self.results_data_json) if self.results_data_json else {}

    @results_data.setter
    def results_data(self, value):
        self.results_data_json = json.dumps(value)


# Add relationship to Benchmark model
Benchmark.results = relationship("BenchmarkResult", back_populates="benchmark")
