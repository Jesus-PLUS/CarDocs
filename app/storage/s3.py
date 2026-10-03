from typing import BinaryIO


class S3Adapter:
    def __init__(self, bucket: str, region: str, access_key_id: str, secret_access_key: str):
        import boto3  # only needed when USE_S3=true

        self.bucket = bucket
        self.client = boto3.client(
            "s3",
            region_name=region,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
        )

    # No ACL is passed: objects keep the bucket default, which is private.
    def save(self, key: str, file: BinaryIO) -> str:
        self.client.upload_fileobj(file, self.bucket, key)
        return key

    def open(self, key: str) -> BinaryIO:
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"]

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)
