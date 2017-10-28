#!/usr/bin/env python

# Copyright 2017 Google Inc. All Rights Reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Google Cloud Speech API sample application using the streaming API.
NOTE: This module requires the additional dependency `pyaudio`. To install
using pip:
    pip install pyaudio
Example usage:
    python transcribe_streaming_mic.py
"""

from __future__ import division

import jtalk
import json
import sys
import subprocess

import time, os, signal

import pyaudio
import requests
from google.cloud import speech
from google.cloud.speech import enums
from google.cloud.speech import types

import queue

RATE = 16000
CHUNK = int(RATE / 10)  # 100ms


class MicrophoneStream(object):

    def __init__(self, rate, chunk):
        self._rate = rate
        self._chunk = chunk

        # Create a thread-safe buffer of audio data
        self._buff = queue.Queue()
        self.closed = True

    def __enter__(self):
        self._audio_interface = pyaudio.PyAudio()
        self._audio_stream = self._audio_interface.open(
            format=pyaudio.paInt16,
            channels=1, rate=self._rate,
            input=True, frames_per_buffer=self._chunk,
            stream_callback=self._fill_buffer,
        )

        self.closed = False

        return self

    def __exit__(self, type, value, traceback):
        self._audio_stream.stop_stream()
        self._audio_stream.close()
        self.closed = True
        self._buff.put(None)
        self._audio_interface.terminate()

    def _fill_buffer(self, in_data, frame_count, time_info, status_flags):
        self._buff.put(in_data)
        return None, pyaudio.paContinue

    def generator(self):
        while not self.closed:
            chunk = self._buff.get()
            if chunk is None:
                return
            data = [chunk]

            while True:
                try:
                    chunk = self._buff.get(block=False)
                    if chunk is None:
                        return
                    data.append(chunk)
                except queue.Empty:
                    break

            yield b''.join(data)



def listen_print_loop(responses):
    num_chars_printed = 0
    for response in responses:
        if not response.results:
            continue

        result = response.results[0]
        if not result.alternatives:
            continue

        transcript = result.alternatives[0].transcript

        overwrite_chars = ' ' * (num_chars_printed - len(transcript))

        if not result.is_final:
            sys.stdout.write(transcript + overwrite_chars + '\r')
            sys.stdout.flush()

            num_chars_printed = len(transcript)

        else:
            num_chars_printed = 0
            return transcript
            break

def main():
    language_code = 'ja-JP'  # a BCP-47 language tag

    client = speech.SpeechClient()
    config = types.RecognitionConfig(
        encoding=enums.RecognitionConfig.AudioEncoding.LINEAR16,
        sample_rate_hertz=RATE,
        language_code=language_code)
    streaming_config = types.StreamingRecognitionConfig(
        config=config,
        interim_results=False)

    with MicrophoneStream(RATE, CHUNK) as stream:
        print ("ok")
        audio_generator = stream.generator()
        requests = (types.StreamingRecognizeRequest(audio_content=content)
                    for content in audio_generator)

        responses = client.streaming_recognize(streaming_config, requests)

        return listen_print_loop(responses)

def postdata(get_word):
    url = "http://192.168.2.29:9000/talk"
    response = requests.post(
        "http://192.168.2.29:9000/talk",
        json.dumps({"text": get_word}),
        headers={'Content-Type': 'application/json'})

    json_responses = json.loads(response.text)

    subprocess.call('echo "%s" > sample.txt' % json_responses["text"], shell=True)
    subprocess.call('open_jtalk -x /usr/local/Cellar/open-jtalk/1.10_1/dic -m /usr/local/Cellar/open-jtalk/1.10_1/voice/mei/mei_happy.htsvoice -ow out.wav sample.txt', shell=True)
    subprocess.call('afplay out.wav', shell=True)#話す部分
    print(get_word)


def timer():
    child_id = os.fork()
    if child_id != 0:
        time.sleep(20)
        commands = os.popen('ps aux | grep %d | grep -v grep' % child_id)
        lines = commands.readlines()
        if len(lines) == 0 or 'Z+' in lines[0].strip():
            pass
        else:
            os.kill(child_id, signal.SIGKILL)  # kill it.
            CAN_KILLED = False

        timer()

    else:
        print(postdata(main()))
        sys.exit()

if __name__ == '__main__':
    timer()
