import logging
import os
from google.cloud.logging import Client
from google.cloud.logging.handlers import StructuredLogHandler

class CloudLoggerManager:
    """
    Cette classe initialise un Logger qui detecte son environment:
    - Cloud Run → Google Cloud Logging
    - Local → Console (StreamHandler)
    """
    def __init__(self, project_id, log_name="crj-log-runner", log_level=logging.INFO):
        self.log_name = log_name
        self.log_level = log_level
        self.logger = logging.getLogger()  # root logger
        self.logger.setLevel(self.log_level)
        self.project_id = project_id
        self.client = None
        self.handler = None
        
        # Detection
        if os.environ.get("CLOUD_RUN_JOB"):
            self._setup_cloud_logging()
        else:
            self._setup_console_logging()

    def _setup_cloud_logging(self):
        try:
            self.client = Client()
            self.handler = StructuredLogHandler()
            self.logger.addHandler(self.handler)
            self.logger.info(
                "Cloud Logging initialized for Cloud Run environment.",
                extra={"severity": "INFO"})

        except Exception as e:
            self._setup_console_logging()
            self.logger.error(f"Failed to set up Cloud Logging: {e}", exc_info=True)

    def _setup_console_logging(self):
        stream_handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        stream_handler.setFormatter(formatter)
        self.logger.addHandler(stream_handler)
        self.logger.info("Console logging initialized for local environment.")

    def close(self):
        if self.handler:
            self.handler.flush()
            if self.handler in self.logger.handlers:
                self.logger.removeHandler(self.handler)
        if self.client:
            self.client.close()

    def get_logger(self):
        return self.logger
