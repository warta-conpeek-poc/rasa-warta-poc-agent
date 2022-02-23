import logging

from rasa.core.channels.channel import InputChannel
from rasa.core.channels.channel import CollectingOutputChannel
from rasa.core.channels.channel import UserMessage
from sanic import Sanic
from sanic import Blueprint
from sanic import response
from sanic.request import Request
from sanic.response import HTTPResponse
from typing import Text
from typing import Callable
from typing import Awaitable
from typing import Dict
from typing import Any
from typing import Optional
from typing import NoReturn
import inspect
import asyncio
import json


class ConpeekVoiceChannel(InputChannel):

    CHANNEL_NAME = "conpeek-voice"

    def name(self) -> Text:
        return ConpeekVoiceChannel.CHANNEL_NAME


    def blueprint(self, on_new_message: Callable[[UserMessage], Awaitable[None]]) -> Blueprint:

        custom_webhook = Blueprint("custom_webhook_{}".format(type(self).__name__), inspect.getmodule(self).__name__,)

        @custom_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @custom_webhook.route("/webhook", methods=["POST"])
        async def receive(request: Request) -> HTTPResponse:
            sender_id = request.json.get("sender")
            text = request.json.get("text")
            input_channel = self.name()
            metadata = request.json.get("metadata")
            logging.info("metadata: {}".format(metadata))

            collector = ConpeekVoiceOutputChannel()

            # include exception handling

            await on_new_message(UserMessage(text, collector, sender_id, input_channel=input_channel, metadata=metadata,))

            return response.json(collector.messages)

        return custom_webhook

class ConpeekVoiceOutputChannel(CollectingOutputChannel):

    @classmethod
    def name(cls) -> Text:
        return ConpeekVoiceChannel.CHANNEL_NAME
