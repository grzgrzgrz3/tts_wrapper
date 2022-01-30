import logging
import os

from homeassistant.components.tts import Provider, DOMAIN

import voluptuous as vol

from homeassistant.components.tts import PLATFORM_SCHEMA
from homeassistant.config import async_process_component_config, async_hass_config_yaml
from homeassistant.const import CONF_PLATFORM
import homeassistant.helpers.config_validation as cv
from homeassistant.loader import async_get_integration
from homeassistant.setup import async_prepare_setup_platform
from .audio_converter import AudioConverter
from .const import CONF_WRAPPED_PLATFORM, DEFAULT_WRAPPED_PLATFORM, CONF_TMP_DIR, DEFAULT_TMP_DIR

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_WRAPPED_PLATFORM, default=DEFAULT_WRAPPED_PLATFORM): cv.string,
        vol.Optional(CONF_TMP_DIR, default=DEFAULT_TMP_DIR): cv.string,
    }
)

_LOGGER = logging.getLogger(__name__)

BIT_RATE_DEFAULT = "48K"
SAMPLE_RATE_DEFAULT = "24000"
FORMAT_DEFAULT = "mp3"
FFMPEG_PARAMS = {"write_xing": 0}


async def async_get_engine(hass, config, discovery_info=None):
    """Set up TTS wrapper component."""
    tmp_dir = await hass.async_add_executor_job(_init_tts_tmp_dir, hass, config[CONF_TMP_DIR])
    _LOGGER.warning(f"Wrapping platform {config[CONF_WRAPPED_PLATFORM]}")
    wrapped_provider = await _get_provider(hass, config[CONF_WRAPPED_PLATFORM], discovery_info)
    _LOGGER.warning(f"Provider wrap: {wrapped_provider}")
    _LOGGER.warning(f"Provider supported platforms: {wrapped_provider.supported_options}")
    return TTSWrapper(hass, config, wrapped_provider, tmp_dir)


class TTSWrapper(Provider):
    def __init__(self, hass, config, wrapped_provider, tmp_dir):
        self._hass = hass
        self.name = "TTS Wrapped (%s)" % wrapped_provider.name
        self._config = config
        self._provider = wrapped_provider
        self._converter = AudioConverter(
            tmp_dir=tmp_dir, bit_rate=BIT_RATE_DEFAULT, sample_rate=SAMPLE_RATE_DEFAULT, format_name=FORMAT_DEFAULT,
            ffmpeg_params=FFMPEG_PARAMS
        )

    @property
    def supported_languages(self):
        """Return a list of supported languages."""
        return self._provider.supported_languages

    @property
    def default_language(self):
        """Return a list of supported languages."""
        return self._provider.default_language

    @property
    def supported_options(self):
        """Return a list of supported languages."""
        return self._provider.supported_options

    @property
    def default_options(self):
        """Return a list of supported languages."""
        return self._provider.default_options

    def get_tts_audio(self, message, language, options=None):
        audio_format, data = self._provider.get_tts_audio(message, language, options)
        return self._converter.convert(data, audio_format)


def _get_platform_conf(conf, platform_name):
    for item in conf:
        if item[CONF_PLATFORM] == platform_name:
            return item
    return {}


async def _get_provider(hass, provider_name, discovery_info):
    global_conf = await async_hass_config_yaml(hass)
    integration = await async_get_integration(hass, DOMAIN)
    component_config = await async_process_component_config(hass, global_conf, integration)

    platform = await async_prepare_setup_platform(hass, component_config, DOMAIN, provider_name)
    if platform is None:
        _LOGGER.error("Error setting up platform %s", provider_name)
        return

    platform_conf = _get_platform_conf(component_config[DOMAIN], provider_name)

    if hasattr(platform, "async_get_engine"):
        return await platform.async_get_engine(hass, platform_conf, discovery_info)
    else:
        return await hass.async_add_executor_job(platform.get_engine, hass, platform_conf, discovery_info)


def _init_tts_tmp_dir(hass, cache_dir):
    """Init tmp folder."""
    if not os.path.isabs(cache_dir):
        cache_dir = hass.config.path(cache_dir)
    if not os.path.isdir(cache_dir):
        _LOGGER.info("Create tts_wrapper tmp dir %s", cache_dir)
        os.mkdir(cache_dir)
    return cache_dir
