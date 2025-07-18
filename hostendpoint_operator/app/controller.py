import logging
import re
import time
from typing import Dict, Any

# Time kubernetes import
start_time = time.time()
logging.debug("Importing kubernetes client...")
from kubernetes import client
from kubernetes.client import ApiException
logging.debug(f"Kubernetes client imported in {time.time() - start_time:.2f}s")

# Import our modules
from . import k8s_api
from .config import settings

class HostEndpointController:
    """
    Manages the reconciliation loop for Calico HostEndpoints.
    Ensures that every Node in the cluster has a corresponding, up-to-date
    HostEndpoint resource.
    """

    def __init__(self):
        # Compile regex patterns for label filtering
        self.labels_include_regex = None
        self.labels_exclude_regex = None
        
        if settings.node_labels_include_regex:
            self.labels_include_regex = re.compile(settings.node_labels_include_regex)
            logging.info(f"Node labels include regex: '{settings.node_labels_include_regex}'")
            
        if settings.node_labels_exclude_regex:
            self.labels_exclude_regex = re.compile(settings.node_labels_exclude_regex)
            logging.info(f"Node labels exclude regex: '{settings.node_labels_exclude_regex}'")

    def _filter_node_labels(self, node_labels: Dict[str, str]) -> Dict[str, str]:
        """
        Filters node labels based on include/exclude regex patterns.
        
        Args:
            node_labels: Original node labels dictionary
            
        Returns:
            Filtered labels dictionary
        """
        if not node_labels:
            return {}
            
        filtered_labels = {}
        
        for label_key, label_value in node_labels.items():
            # Apply include filter first (if specified)
            if self.labels_include_regex:
                if not self.labels_include_regex.match(label_key):
                    continue  # Skip this label as it doesn't match include pattern
                    
            # Apply exclude filter (if specified)
            if self.labels_exclude_regex:
                if self.labels_exclude_regex.match(label_key):
                    continue  # Skip this label as it matches exclude pattern
                    
            # Label passed all filters
            filtered_labels[label_key] = label_value
            
        logging.debug(f"Filtered {len(node_labels)} labels down to {len(filtered_labels)} labels")
        return filtered_labels

    def _build_expected_he(self, node: client.V1Node) -> dict:
        """
        Builds the desired ("expected") state of a HostEndpoint for a given Node.
        """
        # Collect all IP addresses (v4 and v6)
        expected_ips_v4 = []
        expected_ips_v6 = []
        for addr in node.status.addresses:
            # We only care about the IPs used for internal/external communication
            if addr.type in ["InternalIP", "ExternalIP"]:
                if ":" in addr.address:  # Simple check for IPv6
                    expected_ips_v6.append(addr.address)
                else:
                    expected_ips_v4.append(addr.address)

        # The body of the HostEndpoint resource
        spec = {
            "node": node.metadata.name,
            # No interfaceName specified - Calico will automatically apply policies
            # only to external interfaces, excluding loopback and Calico's own interfaces
            "expectedIPs": sorted(expected_ips_v4), # Sort for consistent comparison
        }
        
        # Only add expectedIPsV6 if there are IPv6 addresses
        if expected_ips_v6:
            spec["expectedIPsV6"] = sorted(expected_ips_v6)
            
        return {
            "apiVersion": f"{settings.calico_api_group}/{settings.calico_api_version}",
            "kind": "HostEndpoint",
            "metadata": {
                "name": node.metadata.name,
                "labels": self._filter_node_labels(node.metadata.labels or {})
            },
            "spec": spec
        }

    def reconcile(self) -> None:
        """
        Performs a single reconciliation loop.
        """
        nodes = k8s_api.get_all_nodes()
        existing_hes = k8s_api.get_existing_hostendpoints()

        if not nodes:
            logging.warning("No nodes found in the cluster. Skipping reconciliation.")
            return

        for node in nodes:
            node_name = node.metadata.name
            expected_he = self._build_expected_he(node)

            if node_name not in existing_hes:
                # HostEndpoint does not exist, create it.
                logging.info(f"HostEndpoint for node '{node_name}' not found. Creating...")
                try:
                    k8s_api.create_hostendpoint(expected_he)
                except ApiException:
                    logging.error(f"An exception was caught during HostEndpoint creation for '{node_name}'. Will retry next cycle.")
                continue # Move to the next node

            # HostEndpoint exists, check if it needs an update.
            current_he = existing_hes[node_name]
            
            # We only care about comparing the spec and labels
            current_data = {
                'spec': current_he.get('spec', {}), 
                'labels': current_he.get('metadata', {}).get('labels', {})
            }
            expected_data = {
                'spec': expected_he.get('spec', {}), 
                'labels': expected_he.get('metadata', {}).get('labels', {})
            }
            
            # Use DeepDiff for detailed comparison (lazy import to improve startup time)
            from deepdiff import DeepDiff
            diff = DeepDiff(t1=current_data, t2=expected_data, ignore_order=True)
            needs_update = bool(diff)
            diff_details = str(diff) if diff else None

            if needs_update:
                logging.info(f"HostEndpoint for node '{node_name}' is outdated. Patching...")
                if diff_details:
                    logging.debug(f"Diff details: {diff_details}")
                
                # Use strategic merge patch with explicit content type
                patch_body = {
                    "metadata": {
                        "labels": expected_he["metadata"]["labels"]
                    },
                    "spec": expected_he["spec"]
                }
                
                try:
                    k8s_api.patch_hostendpoint_strategic(node_name, patch_body)
                except ApiException:
                    logging.error(f"An exception was caught during HostEndpoint patching for '{node_name}'. Will retry next cycle.")
            else:
                logging.info(f"HostEndpoint for node '{node_name}' is up-to-date.")