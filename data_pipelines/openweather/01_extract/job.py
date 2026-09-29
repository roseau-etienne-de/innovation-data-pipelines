# mandatory imports
from config_python.helper.helper import GetCmdArgs, GetConfig
import logging

# job imports
from datetime import datetime
import pytz
import json
import requests
from google.cloud import storage
from google.cloud import secretmanager
 
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

secret_id = config_file["extract"]["secret_id"]
city = config_file["extract"]["city"]


def access_secret(project, secret_id, version_id="latest"):
    sc_client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project}/secrets/{secret_id}/versions/{version_id}"
    response = sc_client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")


def request_weather(city, api_key):
    url = f"https://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    response = requests.get(url)
    return response.json()


def transform_weather(data):
    france_tz = pytz.timezone('Europe/Paris')
    transformed_data = {}
    transformed_data["ville"] = data["name"]
    transformed_data["pays"] = data["sys"]["country"]
    transformed_data["meteo"] = data["weather"][0]["description"]
    transformed_data["temperature"] = data["main"]["temp"]
    transformed_data["date_time"] = datetime.now(france_tz).strftime("%Y-%m-%d %H:%M:%S")
    return json.dumps(transformed_data)


def load_weather(transformed_data, filename):
    gs_client = storage.Client()
    bucket_obj = gs_client.get_bucket(bucket_name)

    blob = bucket_obj.blob(filename)
    blob.upload_from_string(
        data=transformed_data,
        content_type="text/json"
        )
    job_logger.info(f"weather.json loaded dans gcs bucket {bucket_name}")


def run_extract():
    api_key = access_secret(project, secret_id)
    data = request_weather(city, api_key)
    final_data = transform_weather(data)
    load_weather(final_data, filename)
    job_logger.info("job>report extract sucessful")


if __name__ == "__main__":
    if "extract" in ls_report:
        run_extract()
