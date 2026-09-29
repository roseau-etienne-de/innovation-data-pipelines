# mandatory imports
from config_python.helper.helper import GetCmdArgs, GetConfig
import logging

# job imports
from google.cloud import bigquery

job_logger = logging.getLogger(__name__)

# 1. --- Get python args
args = GetCmdArgs().args_as_dict()
ENV = args.get("env")
ls_report = args.get("reports")
job_logger.info(f"Liste des reports à lancer : {ls_report}")

# 2. --- Get config file as dict
config_file = GetConfig(ENV).as_dict()
# global
project = config_file["global"]["project"]
bucket_name = config_file["global"]["bucket_name"]
filename = config_file["global"]["filename"]


uri = f"gs://{bucket_name}/{filename}"
dataset = config_file["load"]["dataset"]
table = config_file["load"]["table"]
table_id = f"{project}.{dataset}.{table}"


def load_to_bq():
    bq_client = bigquery.Client()

    job_config = bigquery.LoadJobConfig(
        schema=[
            bigquery.SchemaField("date_time", "DATETIME"),
            bigquery.SchemaField("ville", "STRING"),
            bigquery.SchemaField("pays", "STRING"),
            bigquery.SchemaField("meteo", "STRING"),
            bigquery.SchemaField("temperature", "FLOAT"),
        ],
        source_format=bigquery.SourceFormat.NEWLINE_DELIMITED_JSON,
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    load_job = bq_client.load_table_from_uri(
        source_uris=uri,
        destination=table_id,
        location="EU",
        job_config=job_config,
    )

    load_job.result()

    destination_table = bq_client.get_table(table_id)
    job_logger.info(f"Loaded {destination_table.num_rows} lignes dans la table {destination_table}")


if __name__ == "__main__":
    if "load" in ls_report:
        load_to_bq()
        job_logger.info(f"finished")
