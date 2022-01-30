import contextlib
import logging
import os
import uuid
from pathlib import Path

import ffmpeg

_LOGGER = logging.getLogger(__name__)


class AudioConverter:
    def __init__(self, tmp_dir, bit_rate, sample_rate, format_name, ffmpeg_params):
        self._tmp_dir = Path(tmp_dir)
        self._bit_rate = bit_rate
        self._sample_rate = sample_rate
        self._format_name = format_name
        self._ffmpeg_params = ffmpeg_params

    def convert(self, audio_data, extension):
        with self._save_to_tmp_dir(_tmp_name(extension), audio_data) as file_path:
            if self._need_conversion(file_path):
                return extension, self._convert(file_path)
        return extension, audio_data

    def _convert(self, file_path):
        out_path = _tmp_name(self._format_name)
        try:
            ffmpeg.input(file_path).output(
                filename=out_path,
                audio_bitrate=self._bit_rate,
                format=self._format_name,
                ar=self._sample_rate,
                **self._ffmpeg_params
            ).run()
            with open(out_path, "rb") as fd:
                return fd.read()
        finally:
            try:
                os.remove(out_path)
            except OSError:
                pass

    @contextlib.contextmanager
    def _save_to_tmp_dir(self, name, data):
        file_path = self._tmp_dir / name
        try:
            with open(file_path, "wb") as fd:
                fd.write(data)
            yield file_path
        finally:
            try:
                os.remove(file_path)
            except OSError:
                pass

    def _need_conversion(self, file_path):
        audio_info = _probe(file_path)
        audio_stream = audio_info["streams"][0]
        return (
            audio_info["format"]["format_name"] != self._format_name
            or audio_stream["bit_rate"] != self._bit_rate
            or audio_stream["sample_rate"] != self._sample_rate
        )


def _probe(audio_file_path):
    return ffmpeg.probe(audio_file_path)


def _tmp_name(extension):
    uniq_name = uuid.uuid4()
    return f"{uniq_name}.{extension}"
