# -*- coding: utf-8 -*-
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this
# file, You can obtain one at http://mozilla.org/MPL/2.0/.

import argparse
import logging
import mimetypes
from datetime import datetime

import boto3
import botocore.exceptions
import taskcluster

from taskboot.config import Configuration
from taskboot.target import Target
from taskboot.utils import download_artifact
from taskboot.utils import load_artifacts

logger = logging.getLogger(__name__)


def push_s3(target: Target, args: argparse.Namespace) -> None:
    """
    Push files from a remote task on an AWS S3 bucket
    """
    assert args.task_id is not None, "Missing task id"
    assert not args.artifact_folder.endswith("/"), (
        "Artifact folder {} must not end in /".format(args.artifact_folder)
    )

    # Load config from file/secret
    config = Configuration(args)
    assert config.has_aws_auth(), "Missing AWS authentication"

    # Configure boto3 client
    s3 = boto3.client(
        "s3",
        aws_access_key_id=config.aws["access_key_id"],
        aws_secret_access_key=config.aws["secret_access_key"],
    )

    # Check the bucket is available
    try:
        s3.head_bucket(Bucket=args.bucket)
        logger.info("S3 Bucket {} is available".format(args.bucket))
    except botocore.exceptions.ClientError as e:
        logger.error("Bucket {} unavailable: {}".format(args.bucket, e))
        return

    # Load queue service
    queue = taskcluster.Queue(config.get_taskcluster_options())

    # Download all files from the specified artifact folder
    # These files are then uploaded on the bucket, stripping the artifact folder
    # from their final path
    artifacts = load_artifacts(args.task_id, queue, "{}/*".format(args.artifact_folder))
    for task_id, artifact_name in artifacts:
        # Download each artifact
        assert artifact_name.startswith(args.artifact_folder)
        local_path = download_artifact(queue, task_id, artifact_name)

        # Detect mime/type to set valid content-type for web requests
        content_type, _ = mimetypes.guess_type(local_path)
        if content_type is None:
            # Use a default content type to avoid crashes on upload
            # when a file's MIME type is not detected
            content_type = "text/plain"

        # Push that artifact on the S3 bucket, without the artifact folder
        s3_path = artifact_name[len(args.artifact_folder) + 1 :]
        s3.put_object(
            Bucket=args.bucket,
            Key=s3_path,
            Body=open(local_path, "rb"),
            ContentType=content_type,
        )
        logger.info("Uploaded {} as {} on S3".format(s3_path, content_type))

    cloudfront_distribution_id = config.aws.get("cloudfront_distribution_id")
    if cloudfront_distribution_id is not None:
        cloudfront_client = boto3.client(
            "cloudfront",
            aws_access_key_id=config.aws["access_key_id"],
            aws_secret_access_key=config.aws["secret_access_key"],
        )

        cloudfront_client.create_invalidation(
            DistributionId=cloudfront_distribution_id,
            InvalidationBatch={
                "Paths": {
                    "Quantity": 1,
                    "Items": [
                        "/*",
                    ],
                },
                "CallerReference": str(int(datetime.utcnow().timestamp())),
            },
        )

        logger.info("Cloudfront invalidation created")
