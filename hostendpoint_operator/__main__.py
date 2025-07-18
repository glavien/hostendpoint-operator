import logging
import sys
import time

# We set a basic config first, which will be updated by the app config later.
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stdout
)

# Add a startup message to confirm the module is being executed
logging.info("Starting hostendpoint-operator module...")

try:
    # Time individual imports to identify slow ones
    import time
    start_time = time.time()
    
    logging.debug("Importing config...")
    from hostendpoint_operator.app.config import settings, configure_logging
    configure_logging()  # Setup logging with proper configuration
    logging.debug(f"Config imported in {time.time() - start_time:.2f}s")
    
    import_start = time.time()
    logging.debug("Importing controller...")
    from hostendpoint_operator.app.controller import HostEndpointController
    logging.debug(f"Controller imported in {time.time() - import_start:.2f}s")
    
    logging.debug(f"All modules imported successfully in {time.time() - start_time:.2f}s")
except ImportError as e:
    logging.critical(f"Failed to import modules: {e}. Check PYTHONPATH.", exc_info=True)
    sys.exit(1)


def run():
    """
    The main entry point of the operator.
    """
    # Re-configure logging with the level from settings
    # This will override the basic config we set earlier.
    logging.getLogger().setLevel(settings.log_level)
    
    logging.info(f"Operator starting up. Log level: {logging.getLevelName(settings.log_level)}, Scan interval: {settings.scan_interval_seconds}s")

    controller = HostEndpointController()

    while True:
        try:
            controller.reconcile()
        except Exception as e:
            logging.critical(f"A critical error occurred in the main loop: {e}", exc_info=True)

        logging.debug(f"Sleeping for {settings.scan_interval_seconds} seconds...")
        time.sleep(settings.scan_interval_seconds)


if __name__ == "__main__":
    run()