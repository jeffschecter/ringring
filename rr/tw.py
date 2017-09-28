import json
import logging

import requests_toolbelt.adapters.appengine

from twilio.base import exceptions
from twilio.jwt.client import ClientCapabilityToken
from twilio.rest import Client

from rr import conf
from rr import db


requests_toolbelt.adapters.appengine.monkeypatch()
CREDS = (conf.creds.tw_user, conf.creds.tw_auth)
CLIENT = Client(*CREDS)
ERROR = exceptions.TwilioRestException


# ---------------------------------------------------------------------------- #
# Text messaging.                                                              #
# ---------------------------------------------------------------------------- #

def _send(digits, text):
  logging.info("Sending {} message '{}'".format(digits, text))
  CLIENT.messages.create(
    to="1" + str(digits),
    from_=conf.creds.tw_phone,
    body=text)


def send_confirmation_code(sess, phone):
  digits = phone.key.id()
  if db.check_cooldown(phone):
    raise ValueError("Tried to text a number in cooldown: {}".format(digits))
  _send(digits, "CONFIRMATOIN CODE: {}".format(sess.confirmation_code))


MSG_VERIFICATION_TMPL = (
    "Stripe has requested {} for direct deposit identity "
    "verification purposes. Please log on to {} to complete the ID "
    "verification process.").format("{}", conf.creds.domain)
MSG_PID = MSG_VERIFICATION_TMPL.format("your full Social Security number")
MSG_DOC = MSG_VERIFICATION_TMPL.format("a photo of government-issued ID")
MSG_REVIEW = (
    "Stripe has placed your {} direct deposit account under review. We'll "
    "send you a text when the review is complete!").format(conf.creds.domain)
MSG_ACTIVATED = "Stripe has activated your {} direct deposit account!".format(
    conf.creds.domain)


def send_account_update_alert(employee, epi, prev_status, prev_vfn):
  digits = employee.key.id()
  was_verified = prev_status == "verified"
  is_verified = epi.verification_status == "verified"
  raw_vfn = employee.verification_fields_needed
  if raw_vfn:
    vfn = json.loads(employee.verification_fields_needed)
  else:
    vfn = []
  msg = None

  # What message should we send if any?
  if vfn and (raw_vfn != prev_vfn):
    if "legal_entity.personal_id_number" in vfn:
      msg = MSG_PID
    elif "legal_entity.verification.document" in vfn:
      msg = MSG_DOC
  elif was_verified and (not is_verified):
    msg = MSG_REVIEW
  elif (not was_verified) and is_verified:
    msg = MSG_ACTIVATED

  if msg is not None:
    _send(digits, msg)


# ---------------------------------------------------------------------------- #
# Phone.                                                                       #
# ---------------------------------------------------------------------------- #

def call_token():
    capability = ClientCapabilityToken(*CREDS)
    capability.allow_client_outgoing(conf.creds.tw_ml_app)
    return capability.to_jwt()


DIAL_RESPONSE = """<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial callerId="{tw_phone}">
        <Number
         statusCallbackEvent="answered completed"
         statusCallback="https://{domain}/api/tw_status"
         statusCallbackMethod="POST">
            +1{to}
        </Number>
    </Dial>
</Response>"""


def dial_response(digits):
  return DIAL_RESPONSE.format(
    tw_phone=conf.creds.tw_phone, domain=conf.creds.domain, to=digits)
