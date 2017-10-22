import logging
import sys

import flask

from rr import auth
from rr import conf
from rr import db
from rr import strp
from rr import tw
from rr import utils


# ---------------------------------------------------------------------------- #
# Utils.                                                                       #
# ---------------------------------------------------------------------------- #

def _response(**kwargs):
  logging.info("COCKPIT RESPONSE: {}".format(kwargs.keys()))
  return flask.Response(utils.serialize(kwargs), mimetype="text/json")


# ---------------------------------------------------------------------------- #
# Call lists.                                                                  #
# ---------------------------------------------------------------------------- #

@auth.with_employee_auth
def available_calls(employee=None, **kwargs):
  return _response(
    employee=employee,
    first_calls=db.open_first_calls(),
    followup_calls=db.open_followup_calls(employee.key.id()))


@auth.with_employee_auth
def client_call_history(phone_hash=None, **kwargs):
  phone = db.get_phone_by_hash(phone_hash)
  if not phone:
    flask.abort(500)
  return _response(calls=db.call_history_for_client(phone.key.id()))


@auth.with_employee_auth
def agent_call_history(phone_hash=None, **kwargs):
  employee = db.get_employee_by_hash(phone_hash)
  if not employee:
    flask.abort(500)
  return _response(calls=db.call_history_for_client(employee.key.id()))


# ---------------------------------------------------------------------------- #
# Making calls.                                                                #
# ---------------------------------------------------------------------------- #

@auth.with_employee_auth
def tw_token(**kwargs):
  return _response(device_token=tw.call_token())


@auth.with_employee_auth
def tw_dial(
    employee=None, phone_hash=None, callsid=None, handle_for_agent=None,
    **kwargs):
  # Validate args
  if not employee and phone_hash and callsid and handle_for_agent:
    flask.abort(500)

  # Find the customer we're trying to call and create a call record
  phone = db.get_phone_by_hash(phone_hash)
  logging.info("Phone with hash {} is {}".format(
      phone_hash, phone and phone.key.id()))
  if not phone:
    flask.abort(500)
  if phone.claimed_by is not None and phone.claimed_by != employee.key.id():
    logging.error(
        "Employee {} attempted to dial phone {} which is claimed by {}".format(
            employee.key.id(), phone.key.id(), phone.claimed_by))
    flask.abort()
  db.create_call(employee, phone, callsid, handle_for_agent)

  # Respond
  resp = tw.dial_response(phone.key.id())
  logging.info("COCKPIT DIAL RESPONSE: {}".format(
      resp.replace("\n", "").replace("  ", "")))
  return resp


def tw_status(
    callsid=None, parentcallsid=None, accountsid=None, callduration=None,
    callstatus=None, **kwargs):
  logging.info("Received call status {} for call {}".format(
      callstatus, callsid))
  if  accountsid != conf.creds.tw_user:
    logging.warn("Status callback account sid incorrect: {}, {}".format(
        accountsid))
    flask.abort(500)
  if callstatus == "in-progress":
    db.mark_answered(parentcallsid)
  if callstatus in ("completed", "no-answer"):
    db.complete_call(parentcallsid or callsid, callduration)
    return "call_complete"
  else:
    return "received unexpected status {}".format(callstatus)


@auth.with_employee_auth
def call_exists(handle, include_history=None, **kwargs):
  call = db.get_call_by_handle(handle)
  exists = call is not None
  answered = exists and call.answered_at is not None
  if include_history and call is not None:
    return _response(
      exists=exists, answered=answered,
      calls=db.call_history_for_client(call.phone))
  else:
    return _response(exists=exists, answered=answered)


@auth.with_employee_auth
def debrief(
    handle=None, category=None, notes=None, days_to_next=None, employee=None,
    **kwargs):
  # Categories are retry, cancel, followup, final, unsatisfied
  call = db.get_call_by_handle(handle)
  if not call:
    logging.error("Couldn't find call with handle {}".format(handle))
    return _response(success=False)
  had_conversation = category in ("followup", "final", "unsatisfied")
  charge = category in ("followup", "final")
  needs_followup = category in ("retry", "followup")
  days = 0 if days_to_next is None else int(days_to_next)
  success = db.debrief_call(
    call, had_conversation, charge, needs_followup, notes, days)

  # Charge the client and credit the agent
  if success:
    success = strp.charge_for_call(employee, call)

  return _response(
      success=success,
      first_calls=db.open_first_calls(),
      followup_calls=db.open_followup_calls(employee.key.id()))
