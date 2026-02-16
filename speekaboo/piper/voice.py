import json
import logging
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union, Generator

import numpy as np
import onnxruntime
from piper_phonemize import phonemize_codepoints, phonemize_espeak, tashkeel_run

from .config import PhonemeType, PiperConfig
from .const import BOS, EOS, PAD
from .util import audio_float_to_int16

_LOGGER = logging.getLogger(__name__)


@dataclass
class PiperVoice:
    session: onnxruntime.InferenceSession
    config: PiperConfig
    runopts: onnxruntime.RunOptions
    max_phonemes: int

    @staticmethod
    def load(
        model_path: Union[str, Path],
        config_path: Optional[Union[str, Path]] = None,
        use_cuda: bool = False,
        num_threads: int = 0,
        max_phonemes: int = 200
    ) -> "PiperVoice":
        """Load an ONNX model and config."""
        if config_path is None:
            config_path = f"{model_path}.json"

        with open(config_path, "r", encoding="utf-8") as config_file:
            config_dict = json.load(config_file)

        providers: List[Union[str, Tuple[str, Dict[str, Any]]]]
        if use_cuda:
            providers = [
                (
                    "CUDAExecutionProvider",
                    {"cudnn_conv_algo_search": "HEURISTIC"},
                )
            ]
        else:
            providers = ["CPUExecutionProvider"]

        options = onnxruntime.SessionOptions()
        # thread limit
        if num_threads > 0:
            options.intra_op_num_threads = num_threads

        # Denial of service prevention: Make sure ONNX has a hard memory limit, and that
        # it releases memory immediately.
        options.add_session_config_entry("session.use_env_allocators", "1")
        options.enable_cpu_mem_arena = False

        runopts = onnxruntime.RunOptions()
        # Forcibly enable memory shrinkage so ONNX doesn't leak memory
        runopts.add_run_config_entry("memory.enable_memory_arena_shrinkage", "cpu:0")
        return PiperVoice(
            config=PiperConfig.from_dict(config_dict),
            session=onnxruntime.InferenceSession(
                str(model_path),
                sess_options=options,
                providers=providers,
            ),
            runopts=runopts,
            max_phonemes=max_phonemes,
        )


    def phonemize(self, text: str) -> List[List[str]]:
        """Text to phonemes grouped by sentence."""
        if self.config.phoneme_type == PhonemeType.ESPEAK:
            if self.config.espeak_voice == "ar":
                # Arabic diacritization
                # https://github.com/mush42/libtashkeel/
                text = tashkeel_run(text)

            return phonemize_espeak(text, self.config.espeak_voice)

        if self.config.phoneme_type == PhonemeType.TEXT:
            return phonemize_codepoints(text)

        raise ValueError(f"Unexpected phoneme type: {self.config.phoneme_type}")

    def phonemes_to_ids(self, phonemes: List[str]) -> List[int]:
        """Phonemes to ids."""
        id_map = self.config.phoneme_id_map
        ids: List[int] = list(id_map[BOS])

        for phoneme in phonemes:
            if phoneme not in id_map:
                _LOGGER.warning("Missing phoneme from id map: %s", phoneme)
                continue

            ids.extend(id_map[phoneme])
            ids.extend(id_map[PAD])

        ids.extend(id_map[EOS])

        return ids

    def split_at_commas(self, text: List[str]) -> Generator[List[str], Any, None]:
        """
        Denial of service prevention: Split up the phonemes if the sentence is too long to avoid
        giving ONNX too many tokens at once.

        Hacky Logic:
          - Loop over the sentence, tracking spaces and commas
          - When we get to a multiple of self.max_phonemes, try to split at the nearest comma
          - If we get to 2x the max phonemes since the last comma, split at the nearest space
          - If we get to 2x the max phonemes since the last space, hard split.
        """
        last_start = 0
        last_comma = 0
        last_space = 0
        _LOGGER.warning("Splitting up long sentence")
        for i, phoneme in enumerate(text):
            # commas are ,<space>
            if phoneme == ',':
                last_comma = i
            # second worst case: find the closest space to halfway
            elif phoneme == ' ' and (i - last_start) < self.max_phonemes:
                last_space = i

            if i % self.max_phonemes == 0 and last_comma != last_start and last_comma + 1 < len(text):
                yield text[last_start:last_comma]
                last_start = last_space = last_comma + 2
            elif i - last_comma > self.max_phonemes * 2 and last_space > last_comma:
                _LOGGER.warning("breaking at space")
                yield text[last_start:last_space]
                last_start = last_comma = last_space
            elif i - last_space > self.max_phonemes * 2:
                _LOGGER.warning("forcing break!")
                yield text[last_start:i]
                last_start = last_comma = last_space = i

        yield text[last_start:]


    def phonemize_with_limit(self, text: str, max_words: int) -> Optional[List[Tuple[List[str], bool]]]:
        """
        Like phonemize_impl, but splits up long sentences. Long sentences can consume
        gigabytes of RAM when inferencing.
        """
        phonemes = self.phonemize(text)

        num_words = 0

        out: List[Tuple[List[str], bool]] = []
        for sentence in phonemes:
            num_words += 1 + sentence.count(' ')

            if max_words > 0 and num_words > max_words:
                return None

            if len(sentence) > self.max_phonemes:
                for fragment in self.split_at_commas(sentence):
                    if fragment:
                        out.append((fragment, False))
                out.append(([], True))
            else:
                out.append((sentence, True))
        return out


    def synthesize(
        self,
        text: str,
        wav_file: wave.Wave_write,
        speaker_id: Optional[int] = None,
        length_scale: Optional[float] = None,
        noise_scale: Optional[float] = None,
        noise_w: Optional[float] = None,
        sentence_silence: float = 0.0,
    ):
        """Synthesize WAV audio from text."""
        wav_file.setframerate(self.config.sample_rate)
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setnchannels(1)  # mono

        for audio_bytes in self.synthesize_stream_raw(
            text,
            speaker_id=speaker_id,
            length_scale=length_scale,
            noise_scale=noise_scale,
            noise_w=noise_w,
            sentence_silence=sentence_silence,
        ):
            wav_file.writeframes(audio_bytes)

    def synthesize_stream_raw(
        self,
        text: str,
        speaker_id: Optional[int] = None,
        length_scale: Optional[float] = None,
        noise_scale: Optional[float] = None,
        noise_w: Optional[float] = None,
        sentence_silence: float = 0.0,
        max_words: int = 0
    ) -> Iterable[bytes]:
        """Synthesize raw audio per sentence from text."""
        sentence_phonemes = self.phonemize_with_limit(text, max_words)

        if sentence_phonemes is None:
            raise OverflowError("Text is longer than word limit")

        # 16-bit mono
        num_silence_samples = int(sentence_silence * self.config.sample_rate)
        silence_bytes = np.zeros(num_silence_samples * 2, dtype=np.float32)
    
        for phonemes, pause in sentence_phonemes:
            if len(phonemes) == 0:
                if pause and len(silence_bytes):
                    yield silence_bytes
                continue

            phoneme_ids = self.phonemes_to_ids(phonemes)
            synthesized = self.synthesize_ids_to_raw(
                phoneme_ids,
                speaker_id=speaker_id,
                length_scale=length_scale,
                noise_scale=noise_scale,
                noise_w=noise_w,
            )
            if pause:
                synthesized = np.append(synthesized, silence_bytes)

            yield synthesized

    def synthesize_ids_to_raw(
        self,
        phoneme_ids: List[int],
        speaker_id: Optional[int] = None,
        length_scale: Optional[float] = None,
        noise_scale: Optional[float] = None,
        noise_w: Optional[float] = None,
    ) -> bytes:
        """Synthesize raw audio from phoneme ids."""
        if length_scale is None:
            length_scale = self.config.length_scale

        if noise_scale is None:
            noise_scale = self.config.noise_scale

        if noise_w is None:
            noise_w = self.config.noise_w

        phoneme_ids_array = np.expand_dims(np.array(phoneme_ids, dtype=np.int64), 0)
        phoneme_ids_lengths = np.array([phoneme_ids_array.shape[1]], dtype=np.int64)
        scales = np.array(
            [noise_scale, length_scale, noise_w],
            dtype=np.float32,
        )

        args = {
            "input": phoneme_ids_array,
            "input_lengths": phoneme_ids_lengths,
            "scales": scales
        }

        if self.config.num_speakers <= 1:
            speaker_id = None

        if (self.config.num_speakers > 1) and (speaker_id is None):
            # Default speaker
            speaker_id = 0

        if speaker_id is not None:
            sid = np.array([speaker_id], dtype=np.int64)
            args["sid"] = sid

        # Synthesize through Onnx
        audio = self.session.run(None, args, self.runopts)[0].squeeze((0, 1))
        audio = audio_float_to_int16(audio.squeeze())
        return audio.tobytes()
