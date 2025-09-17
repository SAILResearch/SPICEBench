from dataclasses import dataclass, asdict
@dataclass(frozen=True)
class Environment:
    instance_id: str
    repo_path: str
    log_dir: str