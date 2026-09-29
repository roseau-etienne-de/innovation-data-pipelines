# Native packages
import argparse
from datetime import datetime
import json
import logging
import sys

from .cloud_logger_manager import CloudLoggerManager


LOG_MANAGER = CloudLoggerManager()
logger = logging.getLogger(__name__)


class GetCmdArgs():
    def __init__(self):
        """
        Retourne les arguments passés au runner (job.py), sous forme de dict.
        # ex : python file.py --reports extract load --rattrapage_debut 20220101
        # ex docker : --reports extract load etc
        """
        self.parser = argparse.ArgumentParser(description="Process reports and rattrapage dates.")

        self.parser.add_argument(
            "--env",
            required=False,
            help="Environnement à préciser : dev ou prd",
            type=str
        )

        self.parser.add_argument(
            "--reports",
            nargs="+",  # Accepts one or more values
            required=True,
            help="Liste des reports à executer",
            type=str
        )

        self.parser.add_argument(
            "--rattrapage_debut",
            required=False,
            help="Date de début pour rattrapage (format: YYYY-MM-DD)",
            type=lambda d: datetime.strptime(d, '%Y-%m-%d')
        )

        self.parser.add_argument(
            "--rattrapage_fin",
            required=False,
            help="Date de fin pour rattrapage (format: YYYY-MM-DD)",
            type=lambda d: datetime.strptime(d, '%Y-%m-%d')
        )

    def args_as_dict(self):
        python_args = vars(self.parser.parse_args())
        logger.info(f"Args -> {python_args}")
        return python_args


class GetConfig():
    """
    Retourne le fichier de configuration config_(noprod|prod).json
    en tant que dict.
    """
    def __init__(self, env="dev"):
        self.config_file = "config_pipeline/config_noprod.json"
        if env == "prd":
            self.config_file = "config_pipeline/config_prod.json"

    def as_dict(self):
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except:
            logger.error(f"Problème avec {self.config_file}")
            sys.exit(1)