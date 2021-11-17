# ha_rekognition
Integration for Home Assistant that submits images to AWS Rekognition, to determine if the specified objects are detected or not

## Requirements
1. Home Assistant
2. AWS Account, with an IAM user / role with the following permissions policy:

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "AllowRekognition",
            "Effect": "Allow",
            "Action": "rekognition:DetectLabels",
            "Resource": "*"
        },
        {
            "Sid": "AllowS3",
            "Effect": "Allow",
            "Action": [
                "s3:PutObject",
                "s3:GetObject",
                "s3:ListBucket",
                "s3:DeleteObject",
                "s3:PutObjectAcl"
            ],
            "Resource": [
                "arn:aws:s3:::<bucket name>",
                "arn:aws:s3:::<bucket name>/*"
            ]
        }
    ]
}
```

## Installation
1. Copy all contents of this repo to config/custom_components/detection
2. Restart home assistant
3. Modify the `configuration.yaml` and add the sensor (see example below)

## Configuration Example

```yaml
sensor:
  platform: detection
  bucket: <s3 bucket name>
  aws_id: <aws access key id>
  aws_key: <aws secret access key>
  input_file: /config/custom_components/detection/snapshot.png
  image_max_age: 300
  labels_to_find:
     - Bird
     - Crow
  min_confidence: 70
  max_allowed_checks: 100
  min_seconds_between_checks: 30
  hours_between_check_count_reset: 24
```

## Settings

| Setting | Required? | Default | Description
|---|---|---|---|
| bucket | Yes | | The name of the S3 bucket in the account to upload the image to |
| aws_id| Yes | | The access key ID for the target AWS account |
| aws_key| Yes | | The secret for the target AWS account |
| input_file| Yes | | The path to the file on the Home Assistant instance, to upload to S3 for processing |
| image_max_age| No | 300 | Maximum age, in seconds, of the image file to be uploaded.  If the image is older than that, it will not be submitted |
| labels_to_find| Yes | | List of labels, which if found, would be considered a positive detection |
| min_confidence| No | 70 | Minimum confidence of label for which results should be reported |
| max_allowed_checks | Yes | | Maximum number of images to submit for processing, before counter is reset |
| min_seconds_between_checks | Yes | | Minimum number of seconds between submitting images for processing |
| hours_between_check_count_reset | Yes | 24 | How often the check counter should be reset, used to control costs |