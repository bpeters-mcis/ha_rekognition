"""
Support for showing text in the frontend.

For more details about this component, please refer to the documentation at
https://home-assistant.io/cookbook/python_component_basic_state/
"""
import logging

DOMAIN = 'detection'

_LOGGER = logging.getLogger(__name__)

def setup(hass, config):
    """Set up is called when Home Assistant is loading our component."""
    # Return boolean to indicate that initialization was successfully.
    return True