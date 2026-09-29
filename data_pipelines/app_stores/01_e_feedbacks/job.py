# mandatory imports
from config_python.helper.helper import GetCmdArgs, GetConfig
import logging

# job imports
from config_python.customIO.apis.secretManager import SecretManager
from config_python.customIO.apis.feedbackAppConn import (
    AndroidFeedback,
    IosFeedback
)
from config_python.customIO.database.bigquery_v2 import BigqueryV2
from google.cloud import secretmanager

import json
import pandas as pd
from datetime import datetime, timedelta, time
from zoneinfo import ZoneInfo
from typing import Generator, Union
import sys

logger = logging.getLogger(__name__)

# 1. --- Get python args
args = GetCmdArgs().args_as_dict()
ENV = args.get("env")
ls_report = args.get("reports")
start_date = args.get("rattrapage_debut")
end_date = args.get("rattrapage_fin")

# 2. --- Get config_(prod|noprod).json as dict
global_config = GetConfig(ENV).as_dict()
# global
project = global_config["global"]["project"]

# 3. --- job setup
france_tz = ZoneInfo("Europe/Paris")
today_midnight = datetime.combine(datetime.now(tz=france_tz).date(), time.min)
yesterday_midnight = today_midnight - timedelta(days=2)

bq = BigqueryV2(project=project)

def except_none(dic, *args):
    """
    Vérifie si les clés d'un dictionnaire nesté existent.
    """
    current = dic
    for key in args:
        if current.get(key):
            current = current[key]
        else:
            return None
    return current


def extract_values(review: dict) -> dict:
    """
    Extrait les informations nécessaires des feebacks (commmentaires)
    """
    for d in review["comments"]:
        if not d.get("userComment"):
            continue

        cleaned_review = {}
        dt = datetime.fromtimestamp(
            int(d["userComment"]["lastModified"]["seconds"]))
        dt_formatted = dt.isoformat(timespec='seconds')

        cleaned_review["dateTime"] = dt_formatted
        cleaned_review["reviewId"] = review.get("reviewId")
        cleaned_review["authorName"] = review.get("authorName")
        cleaned_review["text"] = except_none(d, "userComment", "text")
        cleaned_review["reviewerLanguage"] = except_none(d, "userComment", "reviewerLanguage")
        cleaned_review["starRating"] = except_none(d, "userComment", "starRating")
        cleaned_review["thumbsUpCount"] = except_none(d, "userComment", "thumbsUpCount")
        cleaned_review["thumbsDownCount"] = except_none(d, "userComment", "thumbsDownCount")
        cleaned_review["device"] = except_none(d, "userComment", "deviceMetadata", "productName")
        cleaned_review["manufacturer"] = except_none(d, "userComment", "deviceMetadata", "manufacturer")
        cleaned_review["androidOsVersion"] = except_none(d, "userComment", "androidOsVersion")

    return cleaned_review


def format_date(report_name: str, *args: str) -> Generator[Union[str, float], None, None]:
    for date in args:
        if "android" in report_name:
            yield str(date.timestamp())
        elif "ios" in report_name:
            yield date.isoformat()


# 4. --- Launch reports
if "e_feedbacks_android" in ls_report:
    report_config = global_config["e_feedbacks_android"]
    logger.info(f"Running report 'e_feedbacks_android'")

    if start_date and end_date:
        start_date, end_date = format_date("e_feedbacks_android", start_date, end_date)

    # 1. Local setup
    try:
        sa_key = json.loads(
            SecretManager().get_secret(secret_id="android_appstore_sa_key")
        )
    except:
        sc_client = secretmanager.SecretManagerServiceClient()
        path_key = f"projects/{project}/secrets/android_appstore_sa_key/versions/latest"
        response = sc_client.access_secret_version(request={"name": path_key})
        sa_key = response.payload.data.decode("UTF-8")
        sa_key = json.loads(sa_key)

    package_name = report_config.get("package_name")

    dataset_id = report_config.get("df_target").get("dataset")
    table_id = report_config.get("df_target").get("table")
    yesterday_seconds = str(yesterday_midnight.timestamp())

    # 2. Fetch Android reviews
    android = AndroidFeedback(sa_key=sa_key)
    response = android.get_api_response(package_name=package_name)
    generator_reviews = android.get_reviews(
            response,
            start_date=start_date,
            end_date=end_date,
            yesterday_date=yesterday_seconds,
        )
  
    try:
        # see if the generator is empty
        first_item = next(generator_reviews)
        # if not, we can iterate
        android_reviews = [
            extract_values(review) for review in [first_item] + [i for i in generator_reviews]
        ]
    except StopIteration:
        logger.info(f"StopIteration Error : The generator is empty")
        logger.info(f"No android reviews since {yesterday_midnight}")

    # 3. Load reviews to bigquery
    df = pd.DataFrame(android_reviews)
    bq.load_from_dataframe(df, report_config)
    bq.remove_duplicates(dataset_id, table_id)
    logger.info(f"{df.shape[0]} Android reviews append in bigquery, for the day {yesterday_midnight}")


if "e_feedbacks_ios" in ls_report:
    logger.info(f"Running report 'e_feedbacks_ios'")
    report_config = global_config["e_feedbacks_ios"]

    if start_date and end_date:
        start_date, end_date = format_date("e_feedbacks_ios", start_date, end_date)

    # 1. Local setup
    secret_manager = SecretManager()
    secret_manager.intialize(project_id=project)
    ios_creds = json.loads(
        SecretManager().get_secret(secret_id="ios_appstore_credentials")
    )
    private_key = SecretManager().get_secret(secret_id="ios_appstore_private_key")
    dataset_id = report_config.get("df_target").get("dataset")
    table_id = report_config.get("df_target").get("table")
    url = report_config.get("url")
    yesterday_iso = yesterday_midnight.isoformat()

    # 2. Fetch Ios reviews
    ios = IosFeedback(
        token_duration=600.0,
        key_id=ios_creds["key_id"],
        issuer_id=ios_creds["issuer_id"],
        private_key=private_key
    )

    ios_reviews = ios.get_last_reviews(
        url=url,
        start_date=start_date,
        end_date=end_date,
        yesterday_date=yesterday_iso
    )

    if not ios_reviews or ios_reviews == []:
        logger.info(f"No ios reviews since {yesterday_midnight}")

    # 3. Load reviews to bigquery
    else:
        df = pd.DataFrame(ios_reviews)
        bq.load_from_dataframe(df, report_config)
        bq.remove_duplicates(dataset_id, table_id)
        logger.info(f"{df.shape[0]} Ios reviews append in bigquery, for the day {yesterday_midnight}")

sys.exit(0)