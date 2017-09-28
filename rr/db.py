import datetime
import json
import logging
import math
import random
import re

from google.appengine.ext import ndb

from rr import conf
from rr import datamodel
from rr import utils


# ---------------------------------------------------------------------------- #
# Utils.                                                                       #
# ---------------------------------------------------------------------------- #

def now():
  """Shortcut for current datetime."""
  return datetime.datetime.now()


def gen_conf_code():
  """Creates a new random confirmation code."""
  symbols = "abcdefghijkmnpqrstuvwxyz0123456789"
  return "".join(random.choice(symbols) for _ in range(4))


def salt():
  return random.randint(0, 1000 * 1000 * 1000 * 1000 * 1000)


def sid_key(sid):
  key = str(utils.hash(sid))
  logging.info("Key for sid {} is {}".format(sid, key))
  return key


def get_by_hash(cls, hashval):
  matches = cls.query(cls.hash == int(hashval)).fetch()
  if matches:
    return matches[0]


get_session_by_hash = lambda hashval: get_by_hash(datamodel.Session, hashval)
get_phone_by_hash = lambda hashval: get_by_hash(datamodel.Phone, hashval)
get_employee_by_hash = lambda hashval: get_by_hash(datamodel.Employee, hashval)
get_call_by_hash = lambda hashval: get_by_hash(datamodel.Call, hashval)


# ---------------------------------------------------------------------------- #
# Working with sessions.                                                       #
# ---------------------------------------------------------------------------- #

FRESH_SESSION_MAX_AGE = datetime.timedelta(3)  # 3 days


def get_session_by_id(sid):
  """Retrieve a session by ID and check for collisions."""
  assert isinstance(sid, basestring)
  sess = datamodel.Session.get_by_id(sid_key(sid))
  # This should never happen, but it could!
  if sess and sess.session_id != sid:
    raise LookupError(
        "Hash collision! Tried to retrieve {} but got {}.".format(
            sid, sess.session_id))
  return sess


def get_and_validate_session(sid, user_agent):
  """Retrieve a session by ID and confirm validity and staleness.

  Args:
    sid (str): The session ID.
    user_agent (str): The requesting device's user agent.

  Returns:
    tuple: Of session (None if missing or invalid), boolean (True iff valid).
  """
  sess = get_session_by_id(sid)
  if sess is None:
    return None, True
  if sess.created_at > now():
    return None, False
  if sess.user_agent != user_agent:
    return None, False
  return sess, True


def is_fresh(sess):
  if sess.last_confirmed_at is None:
    return False
  return (now() - sess.last_confirmed_at) < FRESH_SESSION_MAX_AGE


def create_session(sid, user_agent):
  """Creates a new session."""
  key = sid_key(sid)
  logging.info("Creating session with sid {} and key {}".format(sid, key))
  sess = datamodel.Session(
      id=key,
      session_id=sid,
      created_at=now(),
      user_agent=user_agent)
  sess.put()
  return sess


def validate_or_create_session(sid, user_agent):
  """Retrieves a session, or creates a new one if nonexistant or invalid."""
  sess, valid = get_and_validate_session(sid, user_agent)
  if valid and (sess is None):
    sess = create_session(sid, user_agent)
    return sess, True
  else:
    return sess, valid


def set_confirmation_code(sess):
  sess.confirmation_code = gen_conf_code()
  sess.put()


def set_session_phone(sess, digits):
  sess.phone = str(digits)
  sess.confirmed = False
  sess.confirmation_code = gen_conf_code()
  sess.put()


# ---------------------------------------------------------------------------- #
# Registering a phone number.                                                  #
# ---------------------------------------------------------------------------- #

def get_phone(digits):
  phone = datamodel.Phone.get_by_id(str(digits))
  if phone and phone.deleted:
    return
  else:
    return phone


def create_phone(digits):
  logging.info("Creating new record for phone {}".format(digits))
  phone = datamodel.Phone(id=str(digits), created_at=now())
  phone.put()
  return phone


def get_or_create_phone(digits):
  existing = get_phone(digits)
  if existing:
    logging.info("Found existing record for phone {}".format(digits))
  return existing or create_phone(digits)


COOLDOWN = datetime.timedelta(0, 60 * 15)  # 15 minutes


def check_cooldown(phone):
  suspicious = False
  if phone.bad_confirmations >= 4:
    suspicious = True
  if phone.unanswered_confirmations >= 4:
    suspicious = True
  if (suspicious and
      phone.last_malfeasance and
      ((now() - phone.last_malfeasance) < COOLDOWN)):
    return True
  phone.unanswered_confirmations += 1
  phone.last_malfeasance = now()
  phone.put()
  return False


def check_session_access_to_phone(sess, phone):
  """Checks a session has rights to a phone.

  Args:
    sess (datamodel.Session): The session.
    phone (datamodel.Phone): The phone.

  Returns:
    bool: True if the session may access the phone. 
  """
  confirmed = (
      sess and phone and
      (str(sess.phone) == phone.key.id()) and
      sess.confirmed and
      is_fresh(sess) and
      phone.confirmed)
  return bool(confirmed)


@ndb.transactional(xg=True)
def register_confirmation(sid, user_agent, digits, code):
  sess, valid = get_and_validate_session(sid, user_agent)
  code = code.lower()
  if digits is None:
    logging.info("No digits provided so retrieving from session.")
    digits = sess.phone

  # Validate
  invalid = (
      (sess is None) or
      (not valid) or
      (digits != sess.phone) or
      (sess.confirmation_code is None) or
      (code != sess.confirmation_code))
  has_access = not invalid

  if has_access:
    # Update session
    sess.confirmed = True
    sess.last_confirmed_at = now()
    sess.put()
    # Update phone
    phone = get_or_create_phone(digits)
    phone.bad_confirmations = 0
    phone.unanswered_confirmations = 0
    phone.confirmed = True
    phone.put()
    return True, sess, phone
    
  else:
    phone = get_phone(digits)
    if phone is not None:
      phone.bad_confirmations += 1
      phone.last_bad_confirmation = now()
      phone.put()
    return False, sess, phone


def get_valid_session_with_phone(sid, user_agent):
  sess, valid = get_and_validate_session(sid, user_agent)
  if not valid or not sess or sess.phone is None:
    return None, None
  phone = get_phone(sess.phone)
  if not check_session_access_to_phone(sess, phone):
    return None, None
  return sess, phone


@ndb.transactional(xg=True)
def delete_phone(sid, user_agent):
  sess, phone = get_valid_session_with_phone(sid, user_agent)
  if not (sess and phone):
    return False
  logging.info("Marking phone {} as deleted".format(sess.phone))

  # Remove phone from session
  sess.phone = None
  sess.confirmation_code = None
  sess.confirmed = False
  sess.last_confirmed_at = None
  sess.put()

  # Mark phone as deleted
  phone.deleted = True
  phone.put()

  return True


# ---------------------------------------------------------------------------- #
# Updating a phone with call request details.                                  #
# ---------------------------------------------------------------------------- #

VALID_TIMEZONES = set([
    "eastern", "central", "mountain", "pacific",
    "alaskan", "hawaiian"])


def save_details(sid, user_agent, tz, schedule, monicker, topic):
  sess, phone = get_valid_session_with_phone(sid, user_agent)

  # Validate
  if sess is None or phone is None:
    return False, sess, phone
  if tz not in VALID_TIMEZONES:
    return False, sess, phone
  if not (schedule and monicker and topic):
    return False, sess, phone

  # Update
  phone.timezone = tz
  phone.schedule_note = schedule
  phone.monicker = monicker
  phone.topic = topic
  phone.put()
  return True, sess, phone


# ---------------------------------------------------------------------------- #
# Save customer payment info.                                                  #
# ---------------------------------------------------------------------------- #

@ndb.transactional(xg=True)
def save_stripe_customer(phone, stripe_customer, stripe_token):
  # Validate
  customer_id = stripe_customer.id
  zipcode = stripe_token.get("card", {}).get("address_zip", "")
  last_digits = stripe_token.get("card", {}).get("last4")
  logging.info("Saving customer data: id={} zip={} last={}".format(
      customer_id, zipcode, last_digits))
  if not (phone and customer_id and zipcode and last_digits):
    return False

  # Update
  phone.stripe_customer_id = customer_id
  phone.card_address_zip = zipcode
  phone.card_last_digits = last_digits
  phone.put()
  return True


# ---------------------------------------------------------------------------- #
# Authorizing employees.                                                       #
# ---------------------------------------------------------------------------- #

def get_employee(digits):
  return datamodel.Employee.get_by_id(str(digits))


def create_employee(digits, is_admin=False):
  logging.info("Creating new record for employee {}".format(digits))
  emp = datamodel.Employee(
      id=str(digits), created_at=now(), is_admin=is_admin)
  emp.put()
  return emp


def authed_employee(sess, phone):
  access = check_session_access_to_phone(sess, phone)
  digits = phone.key.id()
  emp = get_employee(digits)
  if emp and not emp.inactive:
    return emp
  elif digits in conf.creds.admin_phones:
    return create_employee(digits, is_admin=True)


# ---------------------------------------------------------------------------- #
# Employee payable accounts.                                                   #
# ---------------------------------------------------------------------------- #

def create_payment_info(employee, stripe_account_id):
  epi = datamodel.EmployeePaymentInfo(id="0", parent=employee.key)
  epi.stripe_account_id = stripe_account_id
  epi.put()
  return epi


def get_payment_info(employee):
  logging.info("GETTING PAYMENT INFO FOR {}".format(employee))
  return datamodel.EmployeePaymentInfo.get_by_id("0", parent=employee.key)


def get_payment_info_by_stripe_id(stripe_account_id):
  epi = datamodel.EmployeePaymentInfo.get_by_account_id(stripe_account_id)
  if epi is None:
    raise KeuyError("No payment info found for Stripe account {}".format(
        stripe_account_id))
  employee = epi.key.parent().get()
  return employee, epi


VALID_COUNTRIES = ["US"]
VALID_US_STATES = [
    "AL", "AK", "AS", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FM", "FL",
    "GA", "GU", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MH",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
    "NY", "NC", "ND", "MP", "OH", "OK", "OR", "PW", "PA", "PR", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VI", "VA", "WA", "WV", "WI", "WY", "AE",
    "AP", "AA"
    ]


@ndb.transactional(xg=True)
def add_verification_to_payment_info(employee, epi, ip_address, id_info):
  # Update the payment info
  if id_info.get("given_name"):
    epi.given_name = id_info["given_name"]
  if id_info.get("family_name"):
    epi.family_name = id_info["family_name"]
  if id_info.get("date_of_birth"):
    epi.date_of_birth = datetime.datetime.strptime(
        id_info["date_of_birth"], "%m/%d/%Y")
  if id_info.get("ssn_last_digits"):
    assert re.match(r"^\d{4}$", id_info["ssn_last_digits"])
    epi.ssn_last_digits = id_info["ssn_last_digits"]
  if id_info.get("address_line_1"):
    epi.address_line_1 = id_info["address_line_1"]
  if id_info.get("address_line_2"):
    epi.address_line_2 = id_info["address_line_2"]
  if id_info.get("address_city"):
    epi.address_city = id_info["address_city"]
  if id_info.get("address_state"):
    assert id_info["address_state"].upper() in VALID_US_STATES
    epi.address_state = id_info["address_state"].upper()
  if id_info.get("address_zip"):
    assert re.match(r"^\d{5}$", id_info["address_zip"])
    epi.address_zip = id_info["address_zip"]
  if id_info.get("address_country"):
    assert id_info["address_country"].upper() in VALID_COUNTRIES
    epi.address_country = id_info["address_country"].upper()
  if epi.tos_acceptance_ip is None:
    epi.tos_acceptance_ip = ip_address
  epi.put()

  # Update the employee
  if epi.given_name != employee.given_name:
    employee.given_name = epi.given_name
    employee.put()

  return employee, epi


@ndb.transactional(xg=True)
def update_payment_info_status(employee, epi, stripe_response):
  # Update payment info
  epi.payouts_enabled = stripe_response.payouts_enabled
  epi.verification_status = stripe_response.legal_entity.verification.status
  if stripe_response.verification.due_by:
    epi.due_by = datetime.datetime.utcfromtimestamp(
        stripe_response.verification.due_by)
  epi.stripe_status_blob = str(stripe_response.verification)
  epi.put()

  # Update employee
  setup = (
    (epi.payouts_enabled is True) and
    (epi.verification_status == "verified"))
  fn_json = json.dumps(stripe_response.verification.fields_needed)
  new_fields_needed = fn_json != employee.verification_fields_needed
  employee.setup_done = setup
  employee.verification_fields_needed = fn_json
  employee.put()


# ---------------------------------------------------------------------------- #
# Calls.                                                                       #
# ---------------------------------------------------------------------------- #

open_first_calls = datamodel.Phone.open_first_calls
open_followup_calls = datamodel.Phone.open_followup_calls
history_for_client = datamodel.Call.history_for_client
history_for_employee = datamodel.Call.history_for_employee


def get_call(call_id):
  assert isinstance(call_id, basestring)
  return datamodel.Call.get_by_id(str(utils.hash(call_id)))


@ndb.transactional(xg=True)
def create_call(employee, phone, call_id, handle_for_agent):
  # Validate
  assert (
      isinstance(employee, datamodel.Employee) and
      isinstance(phone, datamodel.Phone) and
      isinstance(call_id, basestring) and
      isinstance(handle_for_agent, basestring) and
      phone.claimed_by in (None, employee.key.id()))
  if get_call(call_id):
    logging.error(
        "Tried to create a call to {} that already exists: {}".format(
            phone.key.id(), call_id))
    return

  # Create the call
  call = datamodel.Call(
    id=str(utils.hash(call_id)),
    created_at=now(),
    phone=phone.key.id(),
    sid=call_id,
    employee_id=employee.key.id(),
    handle_for_agent=handle_for_agent)
  call.put()

  # Update the phone
  phone.claimed = True
  phone.claimed_by = employee.key.id()
  phone.last_called = now()
  phone.put()

  logging.info("Created call from {} to {}: {}".format(
      employee.key.id(), phone.key.id(), call))
  return call


def mark_answered(call_id):
  call = get_call(call_id)
  if call.completed:
    logging.error("Tried to mark completed call {} as answered".format(
        call.sid))
    return False
  call.answered_at = now()
  call.put()
  return True


def complete_call(call_id, duration_str):
  duration = int(duration_str) if duration_str else 0
  call = get_call(call_id)

  # Validate
  if call is None:
    logging.error("Tried to complete nonexistant call {}".format(call_id))
    return
  if call.completed_at is not None:
    logging.error("Tried to update call {} already completed at {}".format(
        call_id, call.completed_at))
    return

  # Update
  call.completed = True
  call.completed_at = now()
  call.duration_seconds = duration
  if call.answered_at is None:
    call.had_conversation = False
    call.charged = False
    call.needs_followup = True
    call.notes = "No answer"
    call.debrief_completed_at = now()
    call.debriefed = True
  call.put()

  logging.info("Completed call {} with a duration of {} seconds".format(
      call_id, duration))
  return call


def get_call_by_handle(handle):
  return datamodel.Call.get_by_handle(handle)


@ndb.transactional(xg=True)
def debrief_call(
    call, had_conversation, charged, needs_followup, notes, days_to_next):
  # Validate
  if call.debriefed:
    logging.error("Call {} already debriefed".format(call.sid))
    return False
  if call.answered_at is None and (had_conversation or charged):
    logging.error("Tried to mark unanswered call {} with:{}".format(
        call.sid,
        "" + (" charged" * charged) + (" had_conversation" * had_conversation)))
    return False

  # Update call
  call.had_conversation = had_conversation
  call.charged = charged
  call.needs_followup = needs_followup
  call.notes = notes
  call.debrief_completed_at = now()
  call.debriefed = True
  call.put()

  # Update phone
  phone = get_phone(call.phone)
  if days_to_next is not None:
    phone.expecting_call_after = now() + datetime.timedelta(days_to_next)
  phone.followup_note = notes
  phone.put()

  return True


def call_history_for_client(digits):
  return datamodel.Call.history_for_client(digits)


def call_history_for_employee(employee_id):
  return datamodel.Call.history_for_employee(employee_id)


# ---------------------------------------------------------------------------- #
# Charging customers.                                                          #
# ---------------------------------------------------------------------------- #

def create_charge(call):
  # Validate
  valid = (
      call.completed and
      call.had_conversation and
      call.charged and
      call.debriefed and
      (call.duration_seconds is not None) and
      (call.duration_seconds > 0))
  if not valid:
    return
  charge = datamodel.Charge(id="0", parent=call.key)

  # How much do we charge the client?
  minutes = int(math.ceil(call.duration_seconds / 60.0))
  metered_fee = minutes * call.fee_cents_per_minute
  fee = max(metered_fee, call.fee_cents_minimum)
  charge.fee_cents = fee

  # How much goes to the agent?
  commission = int(
      call.commission_cents_per_minute * (call.duration_seconds / 60.0))
  charge.commission_cents = commission

  # Store it
  console.log(
      "Charge for call {} with duration {}: "
      "client {} pays {} cents; agent {} earns {} cents".format(
          call.sid, call.duration_sconds, call.phone,
          fee, agent.key.id(), commission))
  charge.put()


def mark_charge_result(charge, success, charge_id):
  charge.succeeded = success
  charge.stripe_id = charge_id
  charge.put()


# ---------------------------------------------------------------------------- #
# Employee ledgers and payouts.                                                #
# ---------------------------------------------------------------------------- #

@ndb.transactional(xg=True)
def create_cemployee_ledger_entry(
    employee, etype, source, amount, call=None, payout=None):
  # Validate
  assert not (call and payout)

  # Update the employee
  balance_before = employee.balance
  balance_adj = amount * (1 if etype == "credit" else -1)
  new_balance = balance_before + balance_adj
  employee.balance = new_balance
  employee.put()

  # Create the ledger entry
  amount = int(amount)
  name = "{eid} {ty} {src} {amt} {ts} {salt}".format(
      eid=employee.key.id(), ty=etype, src=source, amt=amount,
      ts=now(), salt=salt())
  ele = datamodel.EmployeeLedgerEntry(
      id=name, parent=employee.key,
      source=source, amount_cents=amount,
      balance_before=old_balance, balance_after=new_balance,
      call=call, payout=payout)
  ele.put()

  return ele


def create_ledger_entry_from_charge(employee, charge):
  return create_cemployee_ledger_entry(
      employee, "credit", "commission", charge.commission_cents,
      call=charge.parent().key.id())
