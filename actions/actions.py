import json
import random
from typing import Any, Text, Dict, List
#
from rasa_sdk import Action, Tracker
from rasa_sdk.events import AllSlotsReset
from rasa_sdk.events import SlotSet
from rasa_sdk.events import SessionStarted
from rasa_sdk.events import ActionExecuted
from rasa_sdk.events import Restarted
from rasa_sdk.events import EventType
from rasa_sdk.events import UserUtteranceReverted
from rasa_sdk.executor import CollectingDispatcher
#
#
from rasa_sdk import Tracker, FormValidationAction
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.types import DomainDict

import re
import logging
import datetime
import csv


logger = logging.getLogger(__name__)

baza_polisy_dict = {}
with open("actions/baza_polisy_utf8.csv") as f:
    f_csv = csv.DictReader(f, delimiter=';')
    for row in f_csv:
        baza_polisy_dict[row['Nr polisy']] = row

class ActionSessionStart(Action):

    def name(self) -> Text:
        return "action_session_start"

    async def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[EventType]:
        logging.critical("Session started !!!")
        events = [SessionStarted(), ActionExecuted("action_listen")]
        metadata = tracker.get_slot("session_started_metadata")
        logging.critical(metadata)
        events.append(SlotSet("validate_counter", 0))
        return events

class ActionAsrLowConfidence(Action):

    def name(self) -> Text:
        return "action_asr_low_confidence"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        metadata = tracker.latest_message["metadata"]
        logging.info(metadata)
        if "stop_playback_date" in metadata and not metadata["stop_playback_date"]:
            text = ""
        else:
            text = "Czy możesz powtórzyć?"
        bot_event = next(e for e in reversed(tracker.events) if e["event"] == "bot")
        custom = {
            "blocks": bot_event["data"]["custom"]["blocks"]
        }
        custom["blocks"][0]["text"] = text
        if tracker.get_latest_input_channel() in ("conpeek-voice", "conpeek-text"):
            dispatcher.utter_message(json_message=custom)
        else:
            dispatcher.utter_message(text=text)
        return [UserUtteranceReverted()]

class ActionNluLowConfidence(Action):

    def name(self) -> Text:
        return "action_nlu_low_confidence"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        metadata = tracker.latest_message["metadata"]
        logging.info(metadata)
        if "stop_playback_date" in metadata and not metadata["stop_playback_date"]:
            text = ""
        else:
            text = "Czy możesz powtórzyć?"
        bot_event = next(e for e in reversed(tracker.events) if e["event"] == "bot")
        custom = {
            "blocks": bot_event["data"]["custom"]["blocks"]
        }
        custom["blocks"][0]["text"] = text
        if tracker.get_latest_input_channel() in ("conpeek-voice", "conpeek-text"):
            dispatcher.utter_message(json_message=custom)
        else:
            dispatcher.utter_message(text=text)
        return [UserUtteranceReverted()]

class ActionOutOfScope(Action):

    def name(self) -> Text:
        return "action_out_of_scope"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        bot_event = next(e for e in reversed(tracker.events) if e["event"] == "bot")
        if bot_event.get("data").get("custom").get("out_of_scope"):
            text = bot_event["data"]["custom"]["blocks"][0]["text"]
            custom = bot_event.get("data").get("custom")
        else:
            text = "Niestety, nie wiem co mam powiedzieć. Wróćmy proszę do tematu rozmowy. "
            text += bot_event["data"]["custom"]["blocks"][0]["text"]
            custom = {
                "out_of_scope": True,
                "blocks": bot_event["data"]["custom"]["blocks"]
            }
            custom["blocks"][0]["text"] = text
        if tracker.get_latest_input_channel() in ("conpeek-voice", "conpeek-text"):
            dispatcher.utter_message(json_message=custom)
        else:
            dispatcher.utter_message(text=text)
        return [UserUtteranceReverted()]


class ValidateInsuranceNumberForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_insurance_number_form"

    def validate_given_insurance_number(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "empty"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        words = re.split('-|\s', slot_value)
        words = [x for x in words if x]
        given_insurance_number = ""
        for word in words:
            if word.isdigit():
                given_insurance_number += word
        match =re.match("^9\d{11}$", given_insurance_number)
        logging.critical(f"Got insurance number: {given_insurance_number} with matching result: {match}")
        if match and given_insurance_number in baza_polisy_dict:
            system_insurance_number = given_insurance_number
            logging.critical(f"Incident {given_insurance_number} found in database.")
            next_installment_number = None
            next_installment_amount = None
            next_installment_date = None
            insurance_payment_2_amount = baza_polisy_dict[given_insurance_number]["Kwota płatności 2"]
            insurance_payment_2_date = baza_polisy_dict[given_insurance_number]["Termin płatności 2"]
            if baza_polisy_dict[given_insurance_number]["Czy opłacona 2?"] == "TAK":
                insurance_payment_2_done = True
            else:
                insurance_payment_2_done = False
                next_installment_number = 2
                next_installment_amount = insurance_payment_2_amount
                next_installment_date = insurance_payment_2_date
            insurance_payment_1_amount = baza_polisy_dict[given_insurance_number]["Kwota płatności 1"]
            insurance_payment_1_date = baza_polisy_dict[given_insurance_number]["Termin płatności 1"]
            if baza_polisy_dict[given_insurance_number]["Czy opłacona 1?"] == "TAK":
                insurance_payment_1_done = True
            else:
                insurance_payment_1_done = False
                next_installment_number = 1
                next_installment_amount = insurance_payment_1_amount
                next_installment_date = insurance_payment_1_date
            insurance_active = baza_polisy_dict[given_insurance_number]["Polisa aktywna"]
            insurance_end_date = baza_polisy_dict[given_insurance_number]["Data zakończenia"]
            system_subject_type = baza_polisy_dict[given_insurance_number]["Przedmiot ubezpieczenia"]
            system_agent_pesel = baza_polisy_dict[given_insurance_number]["Pesel agenta"]
            system_agent_number = baza_polisy_dict[given_insurance_number]["Nr pośrednika"]
            system_agent_name = baza_polisy_dict[given_insurance_number]["Imię i nazwisko agenta"]
            slots = {
                "given_insurance_number": given_insurance_number,
                "system_insurance_number": system_insurance_number,
                "insurance_number_verified": True,
                "system_subject_type": system_subject_type,
                "system_agent_pesel": system_agent_pesel,
                "system_agent_number": system_agent_number,
                "system_agent_name": system_agent_name,
                "insurance_payment_1_amount": insurance_payment_1_amount,
                "insurance_payment_1_done": insurance_payment_1_done,
                "insurance_payment_1_date": insurance_payment_1_date,
                "insurance_payment_2_amount": insurance_payment_2_amount,
                "insurance_payment_2_done": insurance_payment_2_done,
                "insurance_payment_2_date": insurance_payment_2_date,
                "insurance_active": insurance_active,
                "insurance_end_date": insurance_end_date,
                "next_installment_number": next_installment_number,
                "next_installment_amount": next_installment_amount,
                "next_installment_date": next_installment_date,
                "validate_counter": 0
            }
            logging.critical("Setting slots:")
            logging.critical(slots)
        else:
            if validate_counter > validate_limit:
                slots = {
                    "given_insurance_number": slot_value,
                    "insurance_number_verified": False,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "given_insurance_number": None,
                    "insurance_number_verified": False,
                    "validate_counter": validate_counter
                }
        return slots


class ValidateAgentAuthenticationForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_agent_authentication_form"

    def validate_given_agent_number(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "-"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        words = slot_value.split()
        given_agent_number = words[0][0]
        for word in words:
            if word.isdigit():
                given_agent_number += word
            elif word[1:] and word[1:].isdigit():
                given_agent_number += word[1:]
        prog = re.compile('[a-zA-Z]\d{11}$', re.IGNORECASE)
        match = prog.match(given_agent_number)
        logging.critical(f"Got given agent number: {given_agent_number} from slot_value: {slot_value} with matching result: {match}")
        if match :
            slots = {
                "given_agent_number": given_agent_number.upper(),
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "given_agent_number": slot_value,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "given_agent_number": None,
                    "validate_counter": validate_counter
                }
        logging.critical(slots)
        return slots

    def validate_given_agent_pesel(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "-"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        given_agent_pesel = ""
        words = slot_value.split()
        for word in words:
            if word.isdigit():
                given_agent_pesel += word
        prog = re.compile('^\d{11}$', re.IGNORECASE)
        match = prog.match(given_agent_pesel)
        logging.critical(f"Got agent pesel: {given_agent_pesel} from slot_value: {slot_value} with matching result: {match}")
        if match :
            slots = {
                "given_agent_pesel": given_agent_pesel,
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "given_agent_pesel": slot_value,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "given_agent_pesel": None,
                    "validate_counter": validate_counter
                }
        logging.critical(slots)
        return slots

class ActionSetAgentQuestionPath(Action):

    def name(self) -> Text:
        return "action_set_agent_question_path"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        agent_question_path = tracker.get_slot("agent_question_path")
        if not agent_question_path:
            latest_intent = tracker.get_intent_of_latest_message()
            logging.critical(f"Intent for agent question path: {latest_intent}")
            if latest_intent == "agent_question_payments":
                agent_question_path = "bot_info_payments"
            elif latest_intent == "agent_question_validity":
                agent_question_path = "bot_info_validity"
            else:
                agent_question_path = None
                logging.critical("No agent question path !!!")
        logging.critical(f"Setting slot agent_question_path to {agent_question_path}")
        events.append(SlotSet("agent_question_path", agent_question_path))
        return events


class ActionSelectUtterAgentQuestionBotInfo(Action):

    def name(self) -> Text:
        return "action_select_utter_agent_question_bot_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        agent_question_path = tracker.get_slot("agent_question_path")
        if agent_question_path == "bot_info_payments":
            insurance_payment_1_done = tracker.get_slot("insurance_payment_1_done")
            insurance_payment_2_done = tracker.get_slot("insurance_payment_2_done")
            if insurance_payment_1_done and insurance_payment_2_done:
                dispatcher.utter_template("utter_agent_question_payment_done", tracker)
            else:
                dispatcher.utter_template("utter_agent_question_payment_waiting", tracker)
        elif agent_question_path == "bot_info_validity":
            insurance_active = tracker.get_slot("insurance_active")
            if insurance_active == "TAK":
                dispatcher.utter_template("utter_agent_question_insurance_active", tracker)
            else:
                dispatcher.utter_template("utter_agent_question_insurance_inactive", tracker)
        else:
            dispatcher.utter_template("utter_error", tracker)
        return events

class ActionPerformAgentAuthentication(Action):

    def name(self) -> Text:
        return "action_perform_agent_authentication"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        system_agent_number = tracker.get_slot("system_agent_number")
        system_agent_pesel = tracker.get_slot("system_agent_pesel")
        given_agent_number = tracker.get_slot("given_agent_number")
        given_agent_pesel = tracker.get_slot("given_agent_pesel")

        auth_level = 0

        # Compare agent number
        logging.critical(f"system_agent_number: {system_agent_number}, given_agent_number: {given_agent_number}")
        if system_agent_number == given_agent_number:
            auth_level += 1

        # Compare agent pesel
        logging.critical(f"system_agent_pesel: {system_agent_pesel}, given_agent_pesel: {given_agent_pesel}")
        if system_agent_pesel == given_agent_pesel:
            auth_level += 1

        if auth_level > 1:
            events.append(SlotSet("agent_authenticated", True))
        else:
            events.append(SlotSet("agent_authenticated", False))
        return events

