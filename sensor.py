"""Platform for sensor integration."""
from __future__ import annotations
from boto3 import client
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
import logging
import os
from datetime import timedelta, datetime

_LOGGER = logging.getLogger(__name__)
SCAN_INTERVAL = timedelta(seconds=5)
STATE_ATTR_STATUS = "Status"
STATE_ATTR_DETECTIONS = "Detections"
STATE_ATTR_NUMBER_OF_CHECKS = "Number Of Checks"
STATE_ATTR_LAST_CHECK_TIMESTAMP = "Last Checked"
STATE_ATTR_LAST_CHECK_RESET = "Count Last Reset"
STATE_ATTR_NEXT_CHECK_RESET = "Count Next Reset"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the sensor platform."""
    bucket = config.get('bucket')
    aws_id = config.get('aws_id')
    aws_key = config.get('aws_key')
    input_file = config.get('input_file')
    image_max_age = config.get('image_max_age')
    labels_to_find = config.get('labels_to_find')
    min_confidence = config.get('min_confidence', 30)
    max_allowed_checks = config.get('max_allowed_checks', 1000)
    min_seconds_between_checks = config.get('min_seconds_between_checks', 60)
    hours_between_check_count_reset = config.get('hours_between_check_count_reset', 24)

    add_entities([ObjectDetection(bucket=bucket,
                                  aws_id=aws_id,
                                  aws_key=aws_key,
                                  input_file=input_file,
                                  image_max_age=image_max_age,
                                  labels_to_find=labels_to_find,
                                  min_confidence=min_confidence,
                                  max_allowed_checks=max_allowed_checks,
                                  min_seconds_between_checks=min_seconds_between_checks,
                                  hours_between_check_count_reset=hours_between_check_count_reset)])


class ObjectDetection(SensorEntity):
    """Representation of a Sensor."""

    def __init__(self, bucket, aws_id, aws_key, input_file, image_max_age, labels_to_find,
                 min_confidence, max_allowed_checks, min_seconds_between_checks, hours_between_check_count_reset):
        """Initialize the sensor."""
        self._state = "off"
        self._status = "None"
        self._detections = {}
        self._number_of_checks = 0
        self._last_check_timestamp = datetime.now()
        self._last_check_count_reset = datetime.now()
        self._next_check_count_reset = datetime.now() + timedelta(hours=hours_between_check_count_reset)
        self._hours_between_check_count_reset = hours_between_check_count_reset
        self.bucket = bucket
        self.aws_id = aws_id
        self.aws_key = aws_key
        self.input_file = input_file
        self.image_max_age = image_max_age
        self.labels_to_find = labels_to_find
        self.min_confidence = min_confidence
        self.max_allowed_checks = max_allowed_checks
        self.min_seconds_between_checks = min_seconds_between_checks


    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return 'Object Detection'

    @property
    def extra_state_attributes(self):
        return {
           STATE_ATTR_DETECTIONS: self._detections,
            STATE_ATTR_STATUS: self._status,
            STATE_ATTR_NUMBER_OF_CHECKS: self._number_of_checks,
            STATE_ATTR_LAST_CHECK_TIMESTAMP: self._last_check_timestamp,
            STATE_ATTR_LAST_CHECK_RESET: self._last_check_count_reset,
            STATE_ATTR_NEXT_CHECK_RESET: self._next_check_count_reset
        }

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state


    def _reset_check_count(self):
        """
        Checks current time, and if it is beyond when the counter should be reset, we reset the counter and update
        the timestamps for last and next reset
        """
        if datetime.now() > self._next_check_count_reset:
            self._number_of_checks = 0
            self._last_check_count_reset = datetime.now()
            self._next_check_count_reset = datetime.now() + timedelta(hours=self._hours_between_check_count_reset)


    def _does_input_file_exist(self):
        """
        Verifies if the input file exists or not
        :returns: True or False
        """
        if os.path.exists(self.input_file):
            return True
        else:
            return False


    def _past_check_interval(self):
        """
        Compares the timestamp of the last check against our defined minimum delay, and reports of another check can
        be done or not
        :returns: True or False
        """
        if (self._last_check_timestamp + timedelta(seconds=self.min_seconds_between_checks)) < datetime.now():
            return True
        else:
            return False


    def _checks_remain(self):
        """
        Compares the number of checks done since the last counter reset, against the maximum number of defined checks,
        and reports if any remain or not
        :returns: True or False
        """
        if self._number_of_checks < self.max_allowed_checks:
            return True
        else:
            return False


    def _upload_file(self):
        """
        Uploads the source file to the defined S3 bucket for processing, then deletes the local copy
        """
        # Upload the file
        s3_client = client('s3', aws_access_key_id=self.aws_id, aws_secret_access_key=self.aws_key, region_name="us-east-2")
        try:
            s3_client.upload_file(self.input_file, self.bucket, "snapshot.png")
        except Exception as e:
            os.remove(self.input_file)
            return False
        os.remove(self.input_file)
        return True


    def _get_labels(self, max_labels=20):
        """
        Submits the processing request to AWS, and returns the detection results
        :returns: Dict of detected labels
        """
        rekognition = client("rekognition", aws_access_key_id=self.aws_id, aws_secret_access_key=self.aws_key, region_name="us-east-2")
        response = rekognition.detect_labels(
            Image={
                "S3Object": {
                    "Bucket": self.bucket,
                    "Name": "snapshot.png",
                }
            },
            MaxLabels=max_labels,
            MinConfidence=self.min_confidence,
        )
        self._number_of_checks += 1
        return response['Labels']


    def _get_detections(self, labels):
        """
        Creates dict of name/count for each label deteced, for us in the additional state attribute
        """
        detections = {}
        for entry in labels:
            detections[entry["Name"]] = len(entry["Instances"])
        return detections


    def _is_label_found(self, labels):
        """
        Checks the detected labels against the list of labels we are looking for, and reports if any of the desired labels
        are found.
        :returns: True or False
        """
        _LOGGER.warning("-- Looking for labels: {}".format(self.labels_to_find))
        for entry in labels:
            _LOGGER.warning("-- Found label: {}".format(entry["Name"]))
            if entry["Name"] in self.labels_to_find:
                _LOGGER.warning("--- Yes!")
                return True
        return False


    def update(self) -> None:
        """Fetch new state data for the sensor.
        This is the only method that should fetch new data for Home Assistant.
        """

        if self._does_input_file_exist():

            self._reset_check_count()

            if not self._checks_remain():
                self._status = "Maximum checks reached ({}/{})".format(self._number_of_checks, self.max_allowed_checks)
                self._state = "off"
                self._detections = {}
                return

            if not self._past_check_interval():
                self._status = "Last check too recent"
                self._state = "off"
                self._detections = {}
                return

            if self._upload_file():
                labels = self._get_labels()
                self._detections = self._get_detections(labels)

                if self._is_label_found(labels):
                    self._status = "Labels detected"
                    self._state = "on"
                else:
                    self._status = "No relevant labels detected"
                    self._state = "off"

            else:
                self._status = "File upload failed"
                self._detections = {}
                self._state = "off"

        else:
            self._status = "Input file not found"
            self._detections = {}
            self._state = "off"
