import datetime
import json
import logging
import random
import sys

import flask

from rr import db
from rr import strp
from rr import tw

# ---------------------------------------------------------------------------- #
# Utils.                                                                       #
# ---------------------------------------------------------------------------- #

EMPTY_RESPONSE = {
  "card_last_digits": None,         # str last 4 digits of credit card
  "cockpit_link": None,             # bool show link to the employee cockpit
  "error_message": None,            # str human readable error
  "monicker": None,                 # str client's given name
  "new_session_id": None,           # str session id
  "phone_access_confirmed": None,   # bool we've confirmed phone access
  "phone_digits": None,             # str phone number
  "schedule_note": None,            # str schedule request from client
  "session_confirmed": None,        # bool acknowledge valid session
  "timezone": None,                 # str timezone
  "topic": None,                    # str conversation topic
  "ui_state": None,                 # str new user interface state name
}


def session_id():
  datestr = datetime.datetime.today().isoformat()[:19] + "_"
  return datestr + str(random.randint(0, sys.maxint))


def _response(**kwargs):
  resp = dict(EMPTY_RESPONSE)
  extra_args = set(kwargs) - set(resp)
  if extra_args:
    raise AssertionError("Extra response arguments: {}".format(extra_args))
  resp.update(kwargs)
  logging.info("SIGNUP RESPONSE: {}".format(kwargs))
  return flask.Response(json.dumps(resp), mimetype="text/json")


def _response_for_state(sess, phone, error_message=None):
  has_access = db.check_session_access_to_phone(sess, phone)
  if not db.is_fresh(sess):
    return _response(
        error_message=error_message,
        phone_access_confirmed=False,
        ui_state="splash")
  elif not has_access:
    return _response(
        error_message=error_message,
        phone_access_confirmed=False,
        ui_state="awaiting_confirmation")
  elif not phone.timezone:
    ui_state = "details"
  elif not phone.card_last_digits:
    ui_state = "payment"
  else:
    ui_state = "finished"
  return _response(
      card_last_digits=phone.card_last_digits,
      cockpit_link=bool(db.authed_employee(sess, phone)),
      error_message=error_message,
      monicker=phone.monicker,
      phone_access_confirmed=has_access,
      phone_digits=str(phone.key.id()),
      schedule_note=phone.schedule_note,
      timezone=phone.timezone,
      topic=phone.topic,
      ui_state=ui_state)


# ---------------------------------------------------------------------------- #
# Find the user's current state, or start a new session.                       #
# ---------------------------------------------------------------------------- #

def ensure_session_created(sid=None, user_agent=None, **kwargs):
  sess = db.get_session_by_id(sid)
  if sess is None:
    logging.info("Creating new session for sid {}".format(sid))
    db.create_session(sid, user_agent)
    return _response(session_confirmed=True, ui_state="splash")
  elif sess.phone is None:
    logging.info("Found session with no phone for sid {}".format(sid))
    return _response(session_confirmed=True, ui_state="splash")
  else:
    phone = db.get_phone(sess.phone)
    logging.info("Found session with phone for sid {}".format(sid))
    return _response_for_state(sess, phone)


# ---------------------------------------------------------------------------- #
# Signup flow.                                                                 #
# ---------------------------------------------------------------------------- #

def set_phone(sid=None, user_agent=None, digits=None, **kwargs):
  sess, valid = db.validate_or_create_session(sid, user_agent)
  if not (sess and valid):
    return _response(new_session_id=session_id())
  db.set_session_phone(sess, digits)
  phone = db.get_or_create_phone(digits)
  try:
    tw.send_confirmation_code(sess, phone)
  except (tw.ERROR, ValueError) as e:
    logging.error("ERROR tryingto text {}: {}".format(digits, e))
    return _response(error_message="We are unable to text that number.")
  return _response(
      phone_access_confirmed=False,
      ui_state="awaiting_confirmation")


def confirm_phone(
    sid=None, user_agent=None, digits=None, confirmation_code=None, **kwargs):
  success, sess, phone = db.register_confirmation(
      sid, user_agent, digits, confirmation_code.strip().lower())
  if success:
    return _response_for_state(sess, phone)
  else:
    return _response(
        phone_access_confirmed=False,
        error_message="The confirmation code you entered is not valid.")


def submit_details(
    sid=None, user_agent=None,
    tz=None, schedule=None, monicker=None, topic=None, **kwargs):
  success, sess, phone = db.save_details(
      sid, user_agent, tz, schedule, monicker, topic)
  msg = None
  if not success:
    msg = "We couldn't process your request details. Please try again!"
  return _response_for_state(sess, phone, error_message=msg)


def payment_token(sid=None, user_agent=None, stripe_token=None, **kwargs):
  try:
    success, sess, phone = strp.create_customer(sid, user_agent, stripe_token)
    msg = None
    if not success:
      msg = "We couldn't process your payment information. Please try again!"
    return _response_for_state(sess, phone, error_message=msg)
  except strp.ERROR as e:
    return _response(error_message=e.message)


def delete_phone(sid=None, user_agent=None, **kwargs):
  success = db.delete_phone(sid, user_agent)
  if success:
    return _response(phone_access_confirmed=False, ui_state="logout")
  else:
    return _response(error_message="We couldn't delete that phone number.")
