import binascii
import io
import logging

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
  logging.info("CASHOUT RESPONSE: {}".format(kwargs.keys()))
  return flask.Response(utils.serialize(kwargs), mimetype="text/json")


class NamedIO(io.BytesIO):

  def __init__(self, name, buff=None):
    self.name = name
    io.BytesIO.__init__(self, buff)


def _datauri_to_jpeg(uri):
  binary_string = uri.partition("jpeg;base64,")[-1]
  blob = binascii.a2b_base64(binary_string)
  file = NamedIO("id_document.jpg", blob)
  return file

# ---------------------------------------------------------------------------- #
# Onboarding and ID verification.                                              #
# ---------------------------------------------------------------------------- #

@auth.with_employee_auth
def submit_dirdep(
    employee=None, stripe_token=None, ip_address=None, id_info=None,
    **kwargs):
  # Create a stripe account and attach it to an EmployeePaymentInfo record
  epi = strp.create_employee_account(employee, stripe_token)
  if epi is None:
    flask.abort(500)

  # Update the EmployeePaymentInfo identity verification data
  db.add_verification_to_payment_info(employee, epi, ip_address, id_info)
  # Send the identity verification data to Stripe
  stripe_acct = strp.basic_id_verification(employee, epi)
  # Update the EmployeePaymentInfo with Stripe's response
  db.update_payment_info_status(employee, epi, stripe_acct)

  return _response(employee=employee, success=True)


@auth.with_employee_auth
def submit_personal_id(employee=None, pid=None, **kwargs):
  epi = db.get_payment_info(employee)
  stripe_acct = strp.add_personal_id_number(pid, employee, epi)
  db.update_payment_info_status(employee, epi, stripe_acct)
  return _response(employee=employee, success=True)


@auth.with_employee_auth
def submit_id_document(employee=None, datauri=None, **kwargs):
  epi = db.get_payment_info(employee)
  file = _datauri_to_jpeg(datauri)
  stripe_acct = strp.add_id_document(file, employee, epi)
  db.update_payment_info_status(employee, epi, stripe_acct)
  return _response(employee=employee, success=True)


# ---------------------------------------------------------------------------- #
# Withdrawing balance.                                                         #
# ---------------------------------------------------------------------------- #

@auth.with_employee_auth
def submit_withdraw_balance(employee=None, **kwargs):
  success = strp.payout_full_balance(employee)
  return _response(employee=employee, success=success)


# ---------------------------------------------------------------------------- #
# Stripe webhooks.                                                             #
# ---------------------------------------------------------------------------- #

def strp_events_account(event):
  return _response(received=True)


def strp_events_connect(event):
  if event.type == "account.updated":
    tw.send_account_update_alert(*strp.pull_account_update(event.account))
  return _response(received=True)
