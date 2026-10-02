'''refernece code from: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/quickstart.html
https://boto3.amazonaws.com/v1/documentation/api/latest/_modules/boto3/s3/transfer.html
designed  for:  uploading videos to AWS s3 bucket.
to do: 
1. design a function to upload a given file to s3 bucket.
2. develop a function to transit videos from s3 to EC2.
'''

'''demo function part.'''
from PyQt5 import QtCore
from time import time
import sys
import threading
import numpy as np
import cv2
import os
import boto3
import json
from boto3.s3.transfer import TransferConfig, S3Transfer
from .key_loader import check_json_file_exists
def get_bucket_name(): #allow the user to define their bucket in data.json
    configured_bucket = os.environ.get("DYNASMILE_BUCKET")
    if configured_bucket:
        return configured_bucket
    current_path=os.path.abspath(__file__)
    current_folder=os.path.dirname(current_path)

    search_target=os.path.join(current_folder,"data.json")
    if check_json_file_exists(search_target)==True:
        with open(search_target, 'r') as file:
            config = json.load(file)
            return config.get("bucket_name")
    else:
        return 'frank--bucket'

def upload_func(s3_link, filename, bucket_name='frank--bucket', folder_target=None):
    # Let's use Amazon S3
    img = cv2.imread(filename)
    data = np.array(cv2.imencode('.png', img)[1]).tobytes()
    s3_link.Bucket(bucket_name).put_object(
        Key=os.path.basename(filename), Body=data)
    # Do not use cv2 in uploading.


def upload_video(s3_link, filename, bucket_name='frank--bucket', folder_target=None):
    with open(filename, 'rb') as data:
        s3_link.Bucket(bucket_name).put_object(
            Key=os.path.basename(filename), Body=data)


def download_func(s3_link, filename, bucket_name='frank--bucket', folder_target=None):
    target_file = folder_target+os.path.basename(filename)
    with open(target_file, 'wb') as f:
        s3_link.download_fileobj(bucket_name, os.path.basename(target_file), f)


class ProgressPercentage(object):
    def __init__(self, filename):
        self._filename = filename
        self._size = float(os.path.getsize(filename))
        self._seen_so_far = 0
        self._lock = threading.Lock()

    def __call__(self, bytes_amount):
        # To simplify we'll assume this is hooked up
        # to a single filename.
        with self._lock:
            self._seen_so_far += bytes_amount
            percentage = (self._seen_so_far / self._size) * 100
            # sys.stdout.write(
            #    "\r%s  %s / %s  (%.2f%%)" % (
            #        self._filename, self._seen_so_far, self._size,
            #        percentage))
            int_percentage = int(percentage)
            print(int_percentage)
        # sys.stdout.flush()


def upload_video_new(s3_client, filename, bucket_name, signal_func=None, target_folder=None):
    config = TransferConfig(
        multipart_threshold=1 * 1024 * 1024,
        multipart_chunksize=1 * 1024 * 1024,
        max_concurrency=10,
        io_chunksize=256 * 1024,
        num_download_attempts=10,
    )
    transfer = S3Transfer(s3_client, config)
    transfer.upload_file(filename, bucket_name, os.path.basename(
        filename), callback=ProgressPercentage(filename))


if __name__ == '__main__':
    s3_resource = boto3.resource('s3')
    upload_func(s3_resource, 'C:\\Users\\denti\\Pictures\\R-C.png',
                get_bucket_name(),)
    s3_client = boto3.client('s3')
    # download_func(s3_client,'R-C.png','frank--bucket','test\\')
    config = TransferConfig(
        multipart_threshold=1 * 1024 * 1024,
        multipart_chunksize=1 * 1024 * 1024,
        max_concurrency=10,
        io_chunksize=256 * 1024,
        num_download_attempts=10,
    )

    transfer = S3Transfer(s3_client, config)
    now = time()
    transfer.upload_file('416918082.mp4', get_bucket_name(),
                         '416918082.mp4', callback=ProgressPercentage('416918082.mp4'))
    now = time()-now
    print(now)
