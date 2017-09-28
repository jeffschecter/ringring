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


def send(digits, text):
  CLIENT.messages.create(
    to="1" + str(digits),
    from_=conf.creds.tw_phone,
    body=text)


def send_confirmation_code(sess, phone):
  digits = phone.key.id()
  if db.check_cooldown(phone):
    raise ValueError("Tried to text a number in cooldown: {}".format(digits))
  send(digits, "CONFIRMATOIN CODE: {}".format(sess.confirmation_code))


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
