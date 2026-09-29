from google.cloud import bigquery
from google.cloud.bigquery import TableReference
import logging
import pandas as pd


logger = logging.getLogger(__name__)

class BigqueryV2:
    def __init__(self, project: str, location="eu"):
        self.location = location
        self.client = bigquery.Client(project=project)


    def create_dataset_if_not_exist(self, dataset_id: str):
            """Crée un dataset s'il n'existe pas encore.

            Args:
                dataset_id (str): l'ID du dataset à créer s'il n'existe pas.
            """
            dataset_ids = [dataset.dataset_id for dataset in self.client.list_datasets()]
            if dataset_id not in dataset_ids:
                dataset_ref = self.client.dataset(dataset_id)
                dataset = bigquery.Dataset(dataset_ref)
                dataset.location = self.location
                dataset = self.client.create_dataset(dataset)
                logger.info("created dataset: {}".format(dataset_id))


    def check_if_table_exists(self, table_ref: TableReference) -> bool:
            """Check if a table exists in a dataset.

            Args:
                table_ref (TableReference): the table reference to check.

            Returns:
                bool: True if the table exists, False otherwise.
            """
            try:
                self.client.get_table(table_ref)
                return True
            except NotFound:
                return False
    

    def get_total_rows(self, destination_table: TableReference) -> int:
        """Retourne le nombre de ligne d'une table.

        Args:
            destination_table (TableReference): référence de la table ciblée.

        Returns:
            int: nombre de lignes que contient la table ciblée.
        """
        num_rows = 0
        try:
            num_rows = self.client.get_table(destination_table).num_rows or 0
        except NotFound:
            logger.warning(f"Table {destination_table} does not exist yet")
        return num_rows


    def load_from_dataframe(self, df_data: pd.DataFrame, config: dict):
            """Construit un job bq à partir de la config, load un pd.DataFrame vers bigquery.

            Args:
                df_data (Type[pd.DataFrame]): DataFrame à charger
                config (dict): Pipeline config
            """
            # Get config
            _target = config["df_target"]

            # Create dataset if not exist
            self.create_dataset_if_not_exist(_target["dataset"])

            # Init client target details
            if _target.get("dataset") and _target.get("table"):
                dataset = self.client.dataset(_target["dataset"])
                destination_table = dataset.table(_target["table"])
            else:
                err_msg = f"Missing destination details in config:" + \
                    f"{_target.get("dataset")}, {_target.get("table")},{Table}"
                logger.error(err_msg)
                raise Exception(err_msg)
            
            table_exists = self.check_if_table_exists(destination_table)

            # Init LoadJobConfig
            job_config = bigquery.LoadJobConfig()

            # Handle partitioning
            if _target.get("partitioning_field"):
                job_config.time_partitioning = bigquery.TimePartitioning(
                    type_=bigquery.TimePartitioningType.DAY,
                    field=_target["partitioning_field"],
                )

            # Handle write disposition
            if _target.get("write_disposition"):
                job_config.write_disposition = _target["write_disposition"]
                number_rows_before_query = 0
                if table_exists and _target["write_disposition"] == "WRITE_APPEND":
                    number_rows_before_query = self.get_total_rows(destination_table)
            else:
                raise Exception("Write disposition missing in config")

            # Convert schema str to bigquery.Schema
            if _target.get("schema"):
                schema_arr = _target["schema"].split(",")
                schema_fields = [field.split(":") for field in schema_arr]
                job_config.schema = [
                    bigquery.SchemaField(fields[0], fields[1]) for fields in schema_fields
                ]
            else:
                job_config.autodetect = True

            # Handle schema update options
            if _target.get("schema_update_options"):
                schema_update_options = []
                if "addition" in _target["schema_update_options"]:
                    schema_update_options.append(
                        bigquery.SchemaUpdateOption.ALLOW_FIELD_ADDITION
                    )
                if "relaxation" in _target["schema_update_options"]:
                    schema_update_options.append(
                        bigquery.SchemaUpdateOption.ALLOW_FIELD_RELAXATION
                    )
                job_config.schema_update_options = schema_update_options

            # Run job
            job = self.client.load_table_from_dataframe(
                df_data,
                destination_table,
                job_config=job_config,
                location=self.location,
            )
            # Wait job & log results
            job.result()
            rows_inserted = (
                self.get_total_rows(destination_table) - number_rows_before_query
                if table_exists
                else self.get_total_rows(destination_table)
            )
            logger.info(f"Loaded {rows_inserted} rows.")

    
    def remove_duplicates(self, dataset: str, table: str):
        """
        Supprime les lignes en double d'une table bigquery.

        Args:
            dataset (str): le nom du dataset
            table_id (str): le nom de la table
        """
        table_id = f"{self.client.project}.{dataset}.{table}"
        query_string = f"""
        CREATE OR REPLACE TABLE `{table_id}` AS
        SELECT DISTINCT * FROM `{table_id}`
        """

        job = self.client.query(query_string)
        job.result()
        return