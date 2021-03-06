import datetime
import logging
import stripe

from rr import conf
from rr import db


ERROR = stripe.error.CardError
EPOCH = datetime.datetime.utcfromtimestamp(0)


stripe.api_key = conf.creds.stripe_auth


# ---------------------------------------------------------------------------- #
# Utils.                                                                       #
# ---------------------------------------------------------------------------- #

def webhook_event(raw_event, sig, secret):
  try:
    return stripe.Webhook.construct_event(raw_event, sig, secret)
  except Exception as e:
    logging.error("Error in Stripe webhook: {}".format(e))


# ---------------------------------------------------------------------------- #
# Account creation.                                                            #
# ---------------------------------------------------------------------------- #

def create_customer(sid, user_agent, stripe_token):
  try:
    sess, phone = db.get_valid_session_with_phone(sid, user_agent)
    customer = stripe.Customer.create(source=stripe_token.get("id"))
    success = db.save_stripe_customer(phone, customer, stripe_token)
    return success, sess, phone
  except stripe.error as e:
    logging.error("Failed to retrieve customer for token {}: {}".format(
        stripe_token, e))
    return False, sess, phone


def create_employee_account(employee, stripe_token):
  try:
    acct = stripe.Account.create(country="US", type="custom")
    acct.external_accounts.create(external_account=stripe_token.get("id"))
    account_id = acct["id"]
    return db.create_payment_info(employee, account_id)
  except stripe.error as e:
    logging.error(
        "Failed to create Stripe payable account for employee {}: {}".format(
            employee.key.id(), e))


# ---------------------------------------------------------------------------- #
# Moving money.                                                                #
# ---------------------------------------------------------------------------- #

def _charge_customer(digits, cents, idempotency_token):
  # Verify
  if cents < 50:
    logging.error(
        "Failed to charge client {} for {} cents: amount too small".format(
            digits, cents))
    return

  # Charge
  phone = db.get_phone(digits)
  try:
    stripe_charge = stripe.Charge.create(
        amount=cents,
        currency="usd",
        customer=phone.stripe_customer_id,
        idempotency_key=idempotency_token)
    return stripe_charge.id
  except stripe.error as e:
    logging.error(
        "Failed to charge client {} for {} cents: {}".format(digits, cents, e))


def charge_for_call(employee, call):
  charge = db.create_charge(call)
  if charge:
    charge_id = _charge_customer(call.phone, charge.fee_cents, call.key.id())
    success = charge_id is not None
    db.mark_charge_result(charge, charge_id)
  else:
    success = False

  if success:
    db.create_ledger_entry_from_charge(employee, charge)
  return success


def _transfer_to_employee(employee, cents, idempotency_token):
  epi = db.get_payment_info(employee)
  try:
    xfr = stripe.Transfer.create(
      amount=cents,
      currency="usd",
      destination=epi.stripe_account_id,
      idempotency_key=idempotency_token)
    return xfr.id
  except stripe.error as e:
    logging.error(
        "Failed to transfer employee {} in the amount of {} cents: {}".format(
            employee.key.id(), cents, e))


def payout_full_balance(employee):
  payout = db.create_payout(employee)
  if payout:
    tok = "{}_{}_{}".format(
        employee.hash, employee.balance_cents, employee.last_cashout)
    payout_id = _transfer_to_employee(employee, payout.amount_cents, tok)
    success = payout_id is not None
    db.mark_payout_result(payout, payout_id)
  else:
    success = False

  if success:
    db.create_ledger_entry_from_payout(employee, payout)
  return success


# ---------------------------------------------------------------------------- #
# ID verification.                                                             #
# ---------------------------------------------------------------------------- #

def basic_id_verification(employee, epi):
  acct = stripe.Account.retrieve(epi.stripe_account_id)

  # Personal info
  acct.legal_entity.type = "individual"
  acct.legal_entity.first_name = epi.given_name
  acct.legal_entity.last_name = epi.family_name
  acct.legal_entity.ssn_last_4 = epi.ssn_last_digits
  acct.legal_entity.dob.day = epi.date_of_birth.day
  acct.legal_entity.dob.month = epi.date_of_birth.month
  acct.legal_entity.dob.year = epi.date_of_birth.year

  # Address
  acct.legal_entity.address.line1 = epi.address_line_1
  acct.legal_entity.address.line2 = epi.address_line_2
  acct.legal_entity.address.city = epi.address_city
  acct.legal_entity.address.state = epi.address_state
  acct.legal_entity.address.postal_code = epi.address_zip
  acct.legal_entity.address.country = epi.address_country

  # TOS
  acct.tos_acceptance.date = int((epi.last_updated_at - EPOCH).total_seconds())
  acct.tos_acceptance.ip = epi.tos_acceptance_ip

  try:
    acct.save()
  except stripe.error as e:
    logging.error("Failed to update Stripe id verification info for {}".format(
        employee.key.id()))

  return acct


def add_personal_id_number(pid, employee, epi):
  acct = stripe.Account.retrieve(epi.stripe_account_id)
  acct.legal_entity.personal_id_number = pid
  try:
    acct.save()
  except stripe.error as e:
    logging.error("Failed to add personal ID number for {}".format(
        employee.key.id()))
  return acct


def add_id_document(file, employee, epi):
  upload_result = stripe.FileUpload.create(
    purpose="identity_document",
    file=file,
    stripe_account=epi.stripe_account_id)
  remote_handle = upload_result.id
  acct = stripe.Account.retrieve(epi.stripe_account_id)
  acct.legal_entity.verification.document = remote_handle
  try:
    acct.save()
  except stripe.error as e:
    logging.error("Failed to attach ID document for {}".format(
        employee.key.id()))
  return acct


def pull_account_update(stripe_account_id):
  employee, epi = db.get_payment_info_by_stripe_id(stripe_account_id)
  prev_status = epi.verification_status
  prev_vfn = employee.verification_fields_needed
  acct = stripe.Account.retrieve(epi.stripe_account_id)
  db.update_payment_info_status(employee, epi, acct)
  logging.info("Pulled update on Stripe account for {}: {} -> {}".format(
      employee.key.id(), prev_status, epi.verification_status))
  return employee, epi, prev_status, prev_vfn
