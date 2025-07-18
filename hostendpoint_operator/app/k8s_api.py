import logging
import time
from typing import List, cast, Optional

# Time kubernetes import
start_time = time.time()
logging.debug("k8s_api: Importing kubernetes modules...")
from kubernetes import client
from kubernetes.client import ApiException
from kubernetes.config import ConfigException, load_incluster_config, load_kube_config
logging.debug(f"k8s_api: Kubernetes modules imported in {time.time() - start_time:.2f}s")

from .config import settings

# API Client Variables - initialized lazily
_core_v1_api: Optional[client.CoreV1Api] = None
_custom_objects_api: Optional[client.CustomObjectsApi] = None
_config_loaded = False


def _ensure_config_loaded():
    """Ensure Kubernetes configuration is loaded."""
    global _config_loaded, _core_v1_api, _custom_objects_api
    
    if _config_loaded:
        return
    
    try:
        load_incluster_config()
        logging.info("Successfully loaded in-cluster config.")
    except ConfigException:
        logging.warning("Could not load in-cluster config. Falling back to kube_config().")
        try:
            load_kube_config()
            logging.info("Successfully loaded local kube_config.")
        except ConfigException:
            logging.critical("Failed to load any Kubernetes configuration.")
            raise
    
    # Initialize API clients
    _core_v1_api = client.CoreV1Api()
    _custom_objects_api = client.CustomObjectsApi()
    _config_loaded = True


def get_core_v1_api() -> client.CoreV1Api:
    """Get the Core V1 API client, initializing if necessary."""
    _ensure_config_loaded()
    return _core_v1_api


def get_custom_objects_api() -> client.CustomObjectsApi:
    """Get the Custom Objects API client, initializing if necessary."""
    _ensure_config_loaded()
    return _custom_objects_api


def get_all_nodes() -> List[client.V1Node]:
    """
    Fetches all Node objects from the cluster.
    
    Returns:
        A list of V1Node objects.
    """
    logging.debug("Fetching all nodes from the cluster.")
    try:
        core_v1_api = get_core_v1_api()
        nodes = core_v1_api.list_node().items
        return cast(List[client.V1Node], nodes)
    except ApiException as e:
        logging.error(f"Failed to list nodes: {e.reason}")
        return []

def get_existing_hostendpoints() -> dict[str, dict]:
    """
    Fetches all existing HostEndpoint objects from the cluster.

    Returns:
        A dictionary mapping HostEndpoint names to their full object representation.
    """
    logging.debug("Fetching all existing HostEndpoints.")
    try:
        custom_objects_api = get_custom_objects_api()
        response = custom_objects_api.list_cluster_custom_object(
            group=settings.calico_api_group,
            version=settings.calico_api_version,
            plural=settings.calico_plural
        )
        # Create a map for quick lookups by name
        return {he['metadata']['name']: he for he in response.get('items', [])}
    except ApiException as e:
        logging.error(f"Failed to list HostEndpoints: {e.reason}")
        return {}

def create_hostendpoint(body: dict) -> None:
    """
    Creates a new HostEndpoint object in the cluster.

    Args:
        body: The dictionary representation of the HostEndpoint to create.
    """
    name = body.get("metadata", {}).get("name", "unknown")
    logging.info(f"Attempting to create HostEndpoint '{name}'.")
    try:
        custom_objects_api = get_custom_objects_api()
        custom_objects_api.create_cluster_custom_object(
            group=settings.calico_api_group,
            version=settings.calico_api_version,
            plural=settings.calico_plural,
            body=body
        )
        logging.info(f"Successfully created HostEndpoint '{name}'.")
    except ApiException as e:
        if e.status == 409: # Conflict
            logging.warning(f"HostEndpoint '{name}' already exists (conflict). Skipping creation.")
        else:
            logging.error(f"Failed to create HostEndpoint '{name}': {e.reason}")
            raise # Re-raise the exception to be handled by the controller loop

def patch_hostendpoint_strategic(name: str, body: dict) -> None:
    """
    Patches an existing HostEndpoint object using strategic merge patch.

    Args:
        name: The name of the HostEndpoint to patch.
        body: The patch body.
    """
    logging.info(f"Attempting to patch HostEndpoint '{name}' (strategic merge).")
    try:
        custom_objects_api = get_custom_objects_api()
        custom_objects_api.patch_cluster_custom_object(
            group=settings.calico_api_group,
            version=settings.calico_api_version,
            plural=settings.calico_plural,
            name=name,
            body=body,
            _content_type='application/strategic-merge-patch+json'
        )
        logging.info(f"Successfully patched HostEndpoint '{name}'.")
    except ApiException as e:
        logging.error(f"Failed to patch HostEndpoint '{name}': {e.reason}")
        raise


def patch_hostendpoint(name: str, body: dict) -> None:
    """
    Patches an existing HostEndpoint object.

    Args:
        name: The name of the HostEndpoint to patch.
        body: The patch body (e.g., using strategic merge patch format).
    """
    logging.info(f"Attempting to patch HostEndpoint '{name}'.")
    try:
        custom_objects_api = get_custom_objects_api()
        custom_objects_api.patch_cluster_custom_object(
            group=settings.calico_api_group,
            version=settings.calico_api_version,
            plural=settings.calico_plural,
            name=name,
            body=body
        )
        logging.info(f"Successfully patched HostEndpoint '{name}'.")
    except ApiException as e:
        logging.error(f"Failed to patch HostEndpoint '{name}': {e.reason}")
        raise


def delete_hostendpoint(name: str) -> None:
    """
    Deletes an existing HostEndpoint object.

    Args:
        name: The name of the HostEndpoint to delete.
    """
    logging.info(f"Attempting to delete HostEndpoint '{name}'.")
    try:
        custom_objects_api = get_custom_objects_api()
        custom_objects_api.delete_cluster_custom_object(
            group=settings.calico_api_group,
            version=settings.calico_api_version,
            plural=settings.calico_plural,
            name=name
        )
        logging.info(f"Successfully deleted HostEndpoint '{name}'.")
    except ApiException as e:
        logging.error(f"Failed to delete HostEndpoint '{name}': {e.reason}")
        raise