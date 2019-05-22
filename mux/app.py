import os
import sys
import collections.abc
from io import StringIO
import csv
import json
import boto3
import time

# Mux SDK library Setup
envMuxRoot = os.environ["LAMBDA_TASK_ROOT"]
#print("LAMBDA_TASK_ROOT env var:" + os.environ["LAMBDA_TASK_ROOT"])
#print("sys.path:" + str(sys.path))
sys.path.insert(0, envMuxRoot + "/lib")
#print("sys.path:" + str(sys.path))  # to check Mux Path

import mux_python
# Mux Authentication Setup
configuration = mux_python.Configuration()
configuration.username = os.environ['MUX_TOKEN_ID']
configuration.password = os.environ['MUX_TOKEN_SECRET']

# API Client Initialization
metrics_api = mux_python.MetricsApi(mux_python.ApiClient(configuration))
video_views_api = mux_python.VideoViewsApi(mux_python.ApiClient(configuration))

import logging
# pulled from Environment Varibales in Lambda -- default is: ERROR
log_level = os.environ['LOG_LEVEL']
log_level = log_level.upper()  ## set log level to upper case
# works with AWS Logger: https://stackoverflow.com/questions/10332748/python-logging-setlevel
logger = logging.getLogger()
level = logging.getLevelName(log_level)
logger.setLevel(level)


# https://developer.mozilla.org/en-US/docs/Web/HTTP/Basics_of_HTTP/MIME_types/Complete_list_of_MIME_types
def out_to_s3(csv):
    aws_bucket_name = os.environ['DESTINATION_BUCKET']
    s3 = boto3.resource('s3')
    bucket = s3.Bucket(aws_bucket_name)
    t = time.time()
    t_str = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(t))
    filename = "Mux-Overall_%s.csv" % (t_str)
    bucket.put_object(
        ACL='private',
        ContentType='text/csv',
        Key=filename,
        Body=csv.getvalue(),
    )
    body = {
        "uploaded": "true",
        "bucket": aws_bucket_name,
        "path": filename,
    }
    return {
        "statusCode": 200,
        "body": json.dumps(body)
    }

def convert_to_csv(d):
    # https://stackoverflow.com/questions/51953233/python-csv-writer-outputs-commas-after-each-letter
    # https://stackoverflow.com/questions/38154040/save-dataframe-to-csv-directly-to-s3-python
    output_buffer = StringIO()
    writer = csv.writer(output_buffer)
    b = []
    c = []
    for key, value in d.items():
        b.append(key)
        c.append(value)
    writer.writerow(b)
    writer.writerow(c)
    logger.error(output_buffer.getvalue())
    return output_buffer

def flatten(d, parent_key='', sep='.'):
    # https://stackoverflow.com/questions/6027558/flatten-nested-dictionaries-compressing-keys
    items = []
    for k, v in d.items():
        new_key = parent_key + sep + k if parent_key else k
        logger.debug("flatten, New_Key: %s" % new_key)
        logger.debug("flatten, v: %s " % v)
        if isinstance(v, collections.abc.MutableMapping):
            items.extend(flatten(v, new_key, sep=sep).items())
        elif v is None:
            v = ""
            items.append((new_key, v))
        else:
            items.append((new_key, v))
    return dict(items)

def get_metrics(search_strings):
    returned_values = {}
    for key in search_strings:
        mux_data = metrics_api.get_overall_values(metric_id=key, timeframe=['24:hours'])
        logger.info('get_metrics, key: %s mux_data: %s \n' % (key, str(mux_data)))
        returned_values[key] = mux_data.to_dict()
    return returned_values

def lambda_handler(event, context):
    mux_values = ["viewer_experience_score", "playback_success_score", "startup_time_score", "smoothness_score", "video_quality_score"]
    mux_metrics = get_metrics(mux_values)
    logger.info("lambda_handler, Mux_metrics: %s" % mux_metrics)
    flattened = flatten(mux_metrics)
    logger.info("flattened %s " % flattened)
    upload = convert_to_csv(flattened)
    logger.info("convert_to_csv %s " % upload.getvalue())
    finish = out_to_s3(upload)
    logging.warning(finish)