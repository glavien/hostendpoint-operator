import os
import logging
from dataclasses import dataclass

@dataclass(frozen=True, slots=True)
class AppConfig:
    """
    Application configuration loaded from environment variables.
    Provides type-safe access to configuration parameters.
    """
    log_level: int
    scan_interval_seconds: int
    calico_api_group: str
    calico_api_version: str
    calico_plural: str
    operator_id: str
    node_labels_include_regex: str
    node_labels_exclude_regex: str

    @classmethod
    def from_env(cls) -> 'AppConfig':
        """
        Factory method to create a config instance from environment variables.
        """
        # Log Level Configuration
        log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
        log_level = getattr(logging, log_level_str, logging.INFO)

        # Scan Interval Configuration
        try:
            scan_interval_seconds = int(os.getenv("SCAN_INTERVAL_SECONDS", "60"))
            if scan_interval_seconds < 10:
                scan_interval_seconds = 10
        except (ValueError, TypeError):
            scan_interval_seconds = 60

        # Calico CRD Configuration
        calico_api_group = os.getenv("CALICO_API_GROUP", "crd.projectcalico.org")
        calico_api_version = os.getenv("CALICO_API_VERSION", "v1")
        calico_plural = os.getenv("CALICO_PLURAL", "hostendpoints")

        # Operator ID for labeling
        operator_id = os.getenv("OPERATOR_ID", "glavien.io/hostendpoint-operator")

        # Node Labels Filtering
        # Include only labels that match this regex pattern (empty means include all)
        node_labels_include_regex = os.getenv("NODE_LABELS_INCLUDE_REGEX", "")
        
        # Exclude labels that match this regex pattern (applied after include filter)
        # By default, exclude common system labels that change frequently
        node_labels_exclude_regex = os.getenv("NODE_LABELS_EXCLUDE_REGEX", 
            r"^(node\.kubernetes\.io/.*|kubernetes\.io/.*|beta\.kubernetes\.io/.*|"
            r"kubelet\.kubernetes\.io/.*|node-role\.kubernetes\.io/.*-timestamp.*|"
            r".*-timestamp.*|.*\.timestamp.*|.*-last-.*|.*\.last-.*|.*-heartbeat.*|"
            r".*\.heartbeat.*|.*-update.*|.*\.update.*)$")

        return cls(
            log_level=log_level,
            scan_interval_seconds=scan_interval_seconds,
            calico_api_group=calico_api_group,
            calico_api_version=calico_api_version,
            calico_plural=calico_plural,
            operator_id=operator_id,
            node_labels_include_regex=node_labels_include_regex,
            node_labels_exclude_regex=node_labels_exclude_regex,
        )

# Create a singleton instance to be imported by other modules
settings = AppConfig.from_env()

def configure_logging():
    """Configure logging with the loaded settings. Should be called once at startup."""
    logging.basicConfig(
        level=settings.log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )