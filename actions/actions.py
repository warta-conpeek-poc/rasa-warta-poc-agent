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
from rasa_sdk.events import FollowupAction
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

baza_szkody_dict = {}
with open("actions/baza_szkody_utf8.csv") as f:
    f_csv = csv.DictReader(f, delimiter=';')
    for row in f_csv:
        baza_szkody_dict[row['Nr szkody']] = row

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
        if metadata and "caller_contact_address" in metadata:
            caller_contact_address = metadata["caller_contact_address"]
            match = re.match("^\d+$", caller_contact_address)
            if match:
                events.append(SlotSet("customer_phone_number", caller_contact_address))
                # events.append(SlotSet("customer_phone_number", "501003003"))
        if metadata and "callee_contact_address" in metadata:
            events.append(SlotSet("service_phone_number", metadata["callee_contact_address"]))
        events.append(SlotSet("validate_counter", 0))
        return events

class ActionAllSlotsReset(Action):

    def name(self) -> Text:
        return "action_all_slots_reset"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Wszystkie dane zostały zresetowane.")
        return [AllSlotsReset()]

class ActionRestarted(Action):

    def name(self) -> Text:
        return "action_restarted"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        dispatcher.utter_message(text="Konwersacja została zrestartowana.")
        return [Restarted()]

class ActionLowConfidence(Action):

    def name(self) -> Text:
        return "action_low_confidence"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        utter_list = []
        metadata = tracker.latest_message["metadata"]
        logging.info(metadata)
        if "stop_playback_date" in metadata and not metadata["stop_playback_date"]:
            utter_list.append("")
        else:
            utter_list.append("Czy możesz powtórzyć?")
        text_message = random.choice(utter_list)
        custom_message = {
            "blocks": [
                {
                    "text": text_message,
                }
            ]
        }
        if tracker.get_latest_input_channel() == "conpeek-voice":
            dispatcher.utter_message(json_message=custom_message)
        else:
            dispatcher.utter_message(text=text_message)
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
                "blocks": [
                    {
                        "text": text,
                    }
                ]
            }
        dispatcher.utter_message(json_message=custom)
        return [UserUtteranceReverted()]

class ValidateCustomerInfoForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_customer_info_form"

    def validate_customer_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "-"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        words = slot_value.split()
        if len(words) == 2:
            slots = {
                "customer_name": slot_value.title(),
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "customer_name": slot_value,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "customer_name": None,
                    "validate_counter": validate_counter
                }
        return slots

    def validate_customer_phone_number(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "empty"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        words = re.split('-|\s', slot_value)
        words = [x for x in words if x]
        customer_phone_number = ""
        for word in words:
            if word.isdigit():
                customer_phone_number += word
        match =re.match("^\d+$", customer_phone_number)
        if match:
            slots = {
                "customer_phone_number": customer_phone_number,
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "customer_phone_number": slot_value,
                    "customer_phone_number_confirmed": False,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "customer_phone_number": None,
                    "validate_counter": validate_counter
                }
        return slots

    def validate_customer_phone_number_confirmed(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict, ) -> Dict[Text, Any]:
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        latest_intent = tracker.get_intent_of_latest_message()
        if latest_intent == "affirm":
            slots = {
                "customer_phone_number_confirmed": True,
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "customer_phone_number_confirmed": False,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "customer_phone_number_confirmed": None,
                    "validate_counter": validate_counter
                }
        return slots

class ValidateClaimReportForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_claim_report_form"

    def validate_insurance_number(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "empty"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        words = re.split('-|\s', slot_value)
        words = [x for x in words if x]
        insurance_number = ""
        for word in words:
            if word.isdigit():
                insurance_number += word
        match =re.match("^9\d{11}$", insurance_number)
        if match:
            slots = {
                "insurance_number": insurance_number,
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "insurance_number": slot_value,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "insurance_number": None,
                    "validate_counter": validate_counter
                }
        return slots

    def validate_insurance_type(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "empty"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        if slot_value in ["internal", "external"]:
            slots = {
                "insurance_type": slot_value,
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "insurance_type": slot_value,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "insurance_type": None,
                    "validate_counter": validate_counter
                }
        return slots

    def validate_vehicle_number(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "empty"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        words = re.split('-|\s', slot_value)
        words = [x for x in words if x]
        vehicle_number = ""
        for word in words:
            if word.isdigit():
                vehicle_number += word
            else:
                vehicle_number += word[0].upper()
        match =re.match("^[A-Z0-9]*$", vehicle_number)
        if match:
            slots = {
                "insurance_number": vehicle_number,
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "insurance_number": slot_value,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "insurance_number": None,
                    "validate_counter": validate_counter
                }
        return slots

class ValidateIncidentNumberForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_incident_number_form"

    def validate_incident_number_verified(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "empty"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        words = re.split('-|\s', slot_value)
        words = [x for x in words if x]
        incident_number = words[0][0]
        for word in words:
            if word.isdigit():
                incident_number += word
        # prog = re.compile("^[wh]\d{12}(?:-\d{2})*$", re.IGNORECASE)
        match1 =re.match("^[wh]\d{12}$", incident_number, re.IGNORECASE)
        match2 =re.match("^[wh]\d{14}$", incident_number, re.IGNORECASE)
        match = False
        if match1:
            match = True
        elif match2:
            match = True
            incident_number = incident_number[:13] + "-" + incident_number[-2:]
        logging.critical(f"Got incident number: {incident_number} with matching result: {match}")
        if match and incident_number in baza_szkody_dict:
            logging.critical(f"Incident {incident_number} found in database.")
            incident_missing_documents_list = None
            incident_documents_submission_date = None
            incident_inspection_date = None
            incident_withdrawal_amount = None
            if baza_szkody_dict[incident_number]["Czy brakuje dokumentów"] == "Tak":
                incident_missing_documents_list = baza_szkody_dict[incident_number]["Jakich dokumentów brakuje"]
            if baza_szkody_dict[incident_number]["Wpływ dokumentów ostatnich (data)"]:
                incident_documents_submission_date = baza_szkody_dict[incident_number]["Wpływ dokumentów ostatnich (data)"]
            if baza_szkody_dict[incident_number]["Czy zostały zlecone oględziny"] == "Tak":
                incident_inspection_date = baza_szkody_dict[incident_number]["data oględzin"]
            if baza_szkody_dict[incident_number]["Kwota wypłaty"] and int(baza_szkody_dict[incident_number]["Kwota wypłaty"]) > 0:
                incident_withdrawal_amount = baza_szkody_dict[incident_number]["Kwota wypłaty"]
            incident_agent_email = baza_szkody_dict[incident_number]["Email opiekuna"]
            slots = {
                "incident_number": incident_number,
                "incident_number_verified": True,
                "incident_missing_documents_list": incident_missing_documents_list,
                "incident_documents_submission_date": incident_documents_submission_date,
                "incident_inspection_date": incident_inspection_date,
                "incident_withdrawal_amount": incident_withdrawal_amount,
                "incident_agent_email": incident_agent_email,
                "validate_counter": 0
            }
            logging.critical("Setting slots:")
            logging.critical(slots)
        else:
            if validate_counter > validate_limit:
                slots = {
                    "incident_number": slot_value,
                    "incident_number_verified": False,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "incident_number": slot_value,
                    "incident_number_verified": None,
                    "validate_counter": validate_counter
                }
        return slots

class ValidateInsuranceNumberForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_insurance_number_form"

    def validate_insurance_number_verified(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "empty"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        words = re.split('-|\s', slot_value)
        words = [x for x in words if x]
        insurance_number = ""
        for word in words:
            if word.isdigit():
                insurance_number += word
        match =re.match("^9\d{11}$", insurance_number)
        logging.critical(f"Got insurance number: {insurance_number} with matching result: {match}")
        if match and insurance_number in baza_polisy_dict:
            logging.critical(f"Incident {insurance_number} found in database.")
            next_installment_number = None
            next_installment_amount = None
            next_installment_date = None
            insurance_payment_2_amount = baza_polisy_dict[insurance_number]["Kwota płatności 2"]
            insurance_payment_2_date = baza_polisy_dict[insurance_number]["Termin płatności 2"]
            if baza_polisy_dict[insurance_number]["Czy opłacona 2?"] == "TAK":
                insurance_payment_2_done = True
            else:
                insurance_payment_2_done = False
                next_installment_number = 2
                next_installment_amount = insurance_payment_2_amount
                next_installment_date = insurance_payment_2_date
            insurance_payment_1_amount = baza_polisy_dict[insurance_number]["Kwota płatności 1"]
            insurance_payment_1_date = baza_polisy_dict[insurance_number]["Termin płatności 1"]
            if baza_polisy_dict[insurance_number]["Czy opłacona 1?"] == "TAK":
                insurance_payment_1_done = True
            else:
                insurance_payment_1_done = False
                next_installment_number = 1
                next_installment_amount = insurance_payment_1_amount
                next_installment_date = insurance_payment_1_date
            insurance_active = baza_polisy_dict[insurance_number]["Polisa aktywna"]
            insurance_end_date = baza_polisy_dict[insurance_number]["Data zakończenia"]
            insurance_subject_type = baza_polisy_dict[insurance_number]["Przedmiot ubezpieczenia"]
            insurance_customer_pesel = baza_polisy_dict[insurance_number]["Pesel ubezpieczonego"]
            insurance_customer_name = baza_polisy_dict[insurance_number]["Imię i nazwisko ubezpieczonego"]
            slots = {
                "insurance_number": insurance_number,
                "insurance_number_verified": True,
                "insurance_subject_type": insurance_subject_type,
                "insurance_customer_pesel": insurance_customer_pesel,
                "insurance_customer_name": insurance_customer_name,
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
                    "insurance_number": slot_value,
                    "insurance_number_verified": False,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "insurance_number": slot_value,
                    "insurance_number_verified": None,
                    "validate_counter": validate_counter
                }
        return slots


class ValidateCustomerAuthenticationForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_customer_authentication_form"

    async def extract_subject_type(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict) -> Dict[Text, Any]:
        logging.critical("Y"*10)
        subject_type = tracker.get_slot("subject_type")
        if subject_type:
            logging.critical(f"Slot subject_type exists with value {subject_type}")
        if not subject_type:
            for entity in tracker.latest_message['entities']:
                entity_name = entity["entity"]
                if entity_name == "subject_type":
                    entity_value = entity["value"]
                    logging.critical(f"Found entity {entity_name} with value {entity_value}")
                    subject_type = entity_value
        return {"subject_type": subject_type}

    def validate_subject_type(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        logging.critical("X"*10)
        logging.critical(slot_value)
        if not slot_value:
            slot_value = "-"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        if slot_value in ["PERSONAL", "MOTOR", "PROPERTY"]:
            slots = {
                "subject_type": slot_value,
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "subject_type": slot_value,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "subject_type": None,
                    "validate_counter": validate_counter
                }
        logging.critical(slots)
        return slots

    def validate_customer_name(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "-"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        words = slot_value.split()
        if len(words) == 2:
            slots = {
                "customer_name": slot_value.title(),
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "customer_name": slot_value,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "customer_name": None,
                    "validate_counter": validate_counter
                }
        return slots

    def validate_customer_pesel(self, slot_value: Any, dispatcher: CollectingDispatcher, tracker: Tracker, domain: DomainDict,) -> Dict[Text, Any]:
        if not slot_value:
            slot_value = "-"
        validate_limit = 2
        validate_counter = tracker.get_slot("validate_counter")
        validate_counter += 1
        customer_pesel = ""
        words = slot_value.split()
        for word in words:
            if word.isdigit():
                customer_pesel += word
        prog = re.compile('^\d{11}$', re.IGNORECASE)
        match = prog.match(customer_pesel)
        logging.critical(f"Got customer pesel: {customer_pesel} from slot_value: {slot_value} with matching result: {match}")
        if match :
            slots = {
                "customer_pesel": customer_pesel,
                "validate_counter": 0
            }
        else:
            if validate_counter > validate_limit:
                slots = {
                    "customer_pesel": slot_value,
                    "validate_counter": 0
                }
            else:
                slots = {
                    "customer_pesel": None,
                    "validate_counter": validate_counter
                }
        logging.critical(slots)
        return slots

class ActionSetSubjectType(Action):

    def name(self) -> Text:
        return "action_set_subject_type"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        subject_type = tracker.get_slot("subject_type")
        events.append(SlotSet("subject_type", subject_type))
        return events

class ActionInitClaimReport(Action):

    def name(self) -> Text:
        return "action_init_claim_report"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        subject_type = tracker.get_slot("subject_type")
        if subject_type != "MOTOR":
            events.append(SlotSet("vehicle_number", "-"))
        return events

class ActionSetStatusPath(Action):

    def name(self) -> Text:
        return "action_set_status_path"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        status_path = tracker.get_slot("status_path")
        status_path_flag = True
        if not status_path:
            latest_intent = tracker.get_intent_of_latest_message()
            logging.critical(f"Intent for status path: {latest_intent}")
            if latest_intent == "claim_status_consultant_direct":
                status_path = "consultant_direct"
            elif latest_intent == "claim_status_manager_message":
                status_path = "manager_message"
            elif latest_intent == "claim_status_bot_info_inspection":
                status_path = "bot_info_inspection"
            elif latest_intent == "claim_status_bot_info_withdrawal":
                status_path = "bot_info_withdrawal"
            elif latest_intent == "claim_status_bot_info_documents":
                status_path = "bot_info_documents"
            else:
                status_path = None
                status_path_flag = False
                logging.critical("No status path !!!")
        logging.critical(f"Setting slot status_path to {status_path}")
        events.append(SlotSet("status_path", status_path))
        events.append(SlotSet("status_path_flag", status_path_flag))
        return events

class ActionSetCustomerQuestionPath(Action):

    def name(self) -> Text:
        return "action_set_customer_question_path"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        customer_question_path = tracker.get_slot("customer_question_path")
        if not customer_question_path:
            latest_intent = tracker.get_intent_of_latest_message()
            logging.critical(f"Intent for customer question path: {latest_intent}")
            if latest_intent == "customer_question_payments":
                customer_question_path = "bot_info_payments"
            elif latest_intent == "customer_question_validity":
                customer_question_path = "bot_info_validity"
            else:
                customer_question_path = None
                logging.critical("No customer question path !!!")
        logging.critical(f"Setting slot customer_question_path to {customer_question_path}")
        events.append(SlotSet("customer_question_path", customer_question_path))
        return events


class ActionSelectUtterStatusBotInfo(Action):

    def name(self) -> Text:
        return "action_select_utter_status_bot_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        status_path = tracker.get_slot("status_path")
        if status_path == "bot_info_inspection":
            incident_inspection_date = tracker.get_slot("incident_inspection_date")
            if incident_inspection_date:
                events.append(FollowupAction("utter_status_inspection"))
            else:
                events.append(FollowupAction("utter_status_no_inspection"))
        elif status_path == "bot_info_withdrawal":
            incident_withdrawal_amount = tracker.get_slot("incident_withdrawal_amount")
            if incident_withdrawal_amount:
                events.append(FollowupAction("utter_status_withdrawal"))
            else:
                events.append(FollowupAction("utter_status_no_withdrawal"))
        elif status_path == "bot_info_documents":
            incident_documents_submission_date = tracker.get_slot("incident_documents_submission_date")
            incident_missing_documents_list = tracker.get_slot("incident_missing_documents_list")
            if incident_documents_submission_date:
                if incident_missing_documents_list:
                    events.append(FollowupAction("utter_status_date_list"))
                else:
                    events.append(FollowupAction("utter_status_date_no_list"))
            else:
                if incident_missing_documents_list:
                    events.append(FollowupAction("utter_status_no_date_list"))
                else:
                    events.append(FollowupAction("utter_status_no_date_no_list"))
        else:
            events.append(FollowupAction("utter_error"))
        return events

class ActionSelectUtterCustomerQuestionBotInfo(Action):

    def name(self) -> Text:
        return "action_select_utter_customer_question_bot_info"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        customer_question_path = tracker.get_slot("customer_question_path")
        if customer_question_path == "bot_info_payments":
            insurance_payment_1_done = tracker.get_slot("insurance_payment_1_done")
            insurance_payment_2_done = tracker.get_slot("insurance_payment_2_done")
            if insurance_payment_1_done and insurance_payment_2_done:
                events.append(FollowupAction("utter_customer_question_payment_done"))
            else:
                events.append(FollowupAction("utter_customer_question_payment_waiting"))
        elif customer_question_path == "bot_info_validity":
            insurance_active = tracker.get_slot("insurance_active")
            if insurance_active:
                events.append(FollowupAction("utter_customer_question__insurance_active"))
            else:
                events.append(FollowupAction("utter_customer_question__insurance_inactive"))
        else:
            events.append(FollowupAction("utter_error"))
        return events

class ActionPerformCustomerAuthentication(Action):

    def name(self) -> Text:
        return "action_perform_customer_authentication"

    def run(self, dispatcher: CollectingDispatcher, tracker: Tracker, domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:
        events = []
        insurance_subject_type = tracker.get_slot("insurance_subject_type")
        insurance_customer_name = tracker.get_slot("insurance_customer_name")
        insurance_customer_pesel = tracker.get_slot("insurance_customer_pesel")
        subject_type = tracker.get_slot("subject_type")
        customer_name = tracker.get_slot("customer_name")
        customer_pesel = tracker.get_slot("customer_pesel")

        auth_level = 0

        # Compare customer name
        logging.critical(f"insurance_customer_name: {insurance_customer_name}, customer_name: {customer_name}")
        insurance_customer_name_set = set(insurance_customer_name.split(' '))
        customer_name_set = set(customer_name.split(' '))
        if insurance_customer_name_set == customer_name_set:
            auth_level += 1

        # Compare subject type
        logging.critical(f"insurance_subject_type: {insurance_subject_type}, subject_type: {subject_type}")
        if insurance_subject_type == subject_type:
            auth_level += 1

        # Compare customer pesel
        logging.critical(f"insurance_customer_pesel: {insurance_customer_pesel}, customer_pesel: {customer_pesel}")
        if insurance_customer_pesel == customer_pesel:
            auth_level += 1

        if auth_level > 1:
            events.append(SlotSet("customer_authenticated", True))
        else:
            events.append(SlotSet("customer_authenticated", False))
        return events

