from typing import List, Dict, Optional
import logging
from datetime import datetime, timedelta, timezone
from weaviate.backup.backup import BackupStorage
from core.connection.weaviate_connection_manager import get_weaviate_client, get_weaviate_manager

logger = logging.getLogger(__name__)

_STORAGE_LABELS = {
    BackupStorage.S3: "S3 (AWS)",
    BackupStorage.GCS: "GCS (GCP)",
    BackupStorage.AZURE: "Azure Blob Storage",
}


def detect_backup_storage(endpoint: str) -> Optional[BackupStorage]:
    """Infer BackupStorage backend from the cluster endpoint URL.

    Detection rules (case-insensitive):
        • URL contains "aws"   → S3
        • URL contains "gcp"   → GCS
        • URL contains "azure" → Azure Blob Storage

    Returns None when the backend cannot be determined.
    """
    if not endpoint:
        return None
    lower = endpoint.lower()
    if "aws" in lower:
        return BackupStorage.S3
    if "gcp" in lower:
        return BackupStorage.GCS
    if "azure" in lower:
        return BackupStorage.AZURE
    return None


def get_backup_backend_label() -> str:
    """Return a human-readable storage label for the connected cluster.

    Returns 'Unknown' when the endpoint does not match any known provider.
    """
    manager = get_weaviate_manager()
    storage = detect_backup_storage(manager.get_endpoint())
    return _STORAGE_LABELS.get(storage, "Unknown")


def list_backups(days: int = 30) -> List[Dict]:
    """Retrieve backups from the last *days* days from the cluster's auto-detected storage backend.

    Parameters
    ----------
    days : int
        Number of days to look back from now (default: 30).

    Returns a list of dicts with keys:
        Backup ID, Status, Started At, Completed At, Size (GB), Collections

    Raises
    ------
    ValueError
        When the storage backend cannot be inferred from the endpoint URL.
    Exception
        Propagated from the Weaviate client on API errors.
    """
    logger.info("list_backups() called")
    client = get_weaviate_client()
    manager = get_weaviate_manager()

    endpoint = manager.get_endpoint()
    storage = detect_backup_storage(endpoint)

    if storage is None:
        raise ValueError(
            f"Cannot determine backup storage backend from endpoint '{endpoint}'. "
            "The URL must contain 'aws', 'gcp', or 'azure'."
        )

    logger.info(f"Listing backups using storage backend: {_STORAGE_LABELS[storage]}")

    results = client.backup.list_backups(
        backend=storage,
        sort_by_starting_time_asc=False,
    )

    cutoff = datetime.now(tz=timezone.utc) - timedelta(days=days)
    logger.info(f"Filtering backups to last {days} days (cutoff: {cutoff.isoformat()})")

    backups = []
    for b in results:
        if b.started_at is not None and b.started_at < cutoff:
            continue
        started = (
            b.started_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if b.started_at
            else "N/A"
        )
        completed = (
            b.completed_at.strftime("%Y-%m-%d %H:%M:%S UTC")
            if b.completed_at
            else "N/A"
        )
        size_gb = round(b.size, 6) if b.size is not None else "N/A"
        collections = (
            ", ".join(sorted(b.collections)) if b.collections else "N/A"
        )
        status = (
            b.status.value if hasattr(b.status, "value") else str(b.status)
        )
        backups.append(
            {
                "Backup ID": b.backup_id,
                "Status": status,
                "Started At": started,
                "Completed At": completed,
                "Size (GB)": size_gb,
                "Collections": collections,
            }
        )

    logger.info(f"Retrieved {len(backups)} backup(s) within the last {days} days")
    return backups
