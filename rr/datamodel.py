import datetime

from google.appengine.ext import ndb

from rr import utils


class Model(ndb.Model):

  def put(self):
    if self.created_at is None:
      self.created_at = datetime.datetime.now()
    self.last_updated_at = datetime.datetime.now()
    self.hash = utils.id_hash(self)
    self._put()


class Session(Model):
  """A device session.

  Ancestor: None
  Name: (str) Abs of hashed session ID.
  """
  hash = ndb.IntegerProperty(required=True)
  created_at = ndb.DateTimeProperty(required=True)
  last_updated_at = ndb.DateTimeProperty()
  session_id = ndb.StringProperty(required=True)
  user_agent = ndb.StringProperty(required=True)
  confirmation_code = ndb.StringProperty()
  phone = ndb.StringProperty()
  confirmed = ndb.BooleanProperty(default=False)
  last_confirmed_at = ndb.DateTimeProperty()


class Phone(Model):
  """A user, identified by phone number.

  Ancestor: None
  Name: (str) The digits of a phone number. 
  """
  hash = ndb.IntegerProperty(required=True)
  created_at = ndb.DateTimeProperty(required=True)
  last_updated_at = ndb.DateTimeProperty()
  deleted = ndb.BooleanProperty(default=False)
  bad_confirmations = ndb.IntegerProperty(default=0)
  unanswered_confirmations = ndb.IntegerProperty(default=0)
  last_malfeasance = ndb.DateTimeProperty()
  confirmed = ndb.BooleanProperty(default=False)
  timezone = ndb.StringProperty()
  schedule_note = ndb.StringProperty()
  monicker = ndb.StringProperty()
  topic = ndb.StringProperty()
  stripe_customer_id = ndb.StringProperty()
  card_address_zip = ndb.StringProperty()
  card_last_digits = ndb.StringProperty()
  claimed_by = ndb.StringProperty()
  claimed = ndb.BooleanProperty(default=False)
  expecting_call_after = ndb.DateTimeProperty()
  followup_note = ndb.StringProperty()
  last_called = ndb.DateTimeProperty()

  @classmethod
  def open_first_calls(cls):
    calls = cls.query(
        cls.deleted == False,
        cls.card_last_digits > "",
        cls.claimed == False,
        ).fetch()
    return sorted(calls, key=lambda call: call.created_at)

  @classmethod
  def open_followup_calls(cls, employee_id):
    candidates = cls.query(
      cls.deleted == False,
      cls.claimed_by == employee_id,
      #cls.expecting_call_after <= datetime.datetime.today()
      ).fetch()
    return sorted(
      [cnd for cnd in candidates if (
       cnd.card_last_digits is not None and
       cnd.expecting_call_after is not None)],
      key=lambda call: call.expecting_call_after)


class Employee(Model):
  """An employee, identified by phone number.

  Ancestor: None
  Name: (str) The digits of a phone number.
  """
  hash = ndb.IntegerProperty(required=True)
  created_at = ndb.DateTimeProperty(required=True)
  last_updated_at = ndb.DateTimeProperty()
  inactive = ndb.BooleanProperty(default=False)
  is_admin = ndb.BooleanProperty(default=False)
  given_name = ndb.StringProperty()
  setup_done = ndb.BooleanProperty(default=False)
  verification_fields_needed = ndb.StringProperty()


class EmployeePaymentInfo(Model):
  """An employee's Stripe payment info.

  Ancestor: Employee
  Name: (str) "0"
  """
  hash = ndb.IntegerProperty(required=True)
  created_at = ndb.DateTimeProperty(required=True)
  last_updated_at = ndb.DateTimeProperty()
  stripe_account_id = ndb.StringProperty(required=True)
  given_name = ndb.StringProperty()
  family_name = ndb.StringProperty()
  date_of_birth = ndb.DateTimeProperty()
  ssn_last_digits = ndb.StringProperty()
  address_line_1 = ndb.StringProperty()
  address_line_2 = ndb.StringProperty()
  address_city = ndb.StringProperty()
  address_state = ndb.StringProperty()
  address_zip = ndb.StringProperty()
  address_country = ndb.StringProperty(default="US")
  tos_acceptance_ip = ndb.StringProperty()
  payouts_enabled = ndb.BooleanProperty(default=False)
  verification_status = ndb.StringProperty()
  due_by = ndb.DateTimeProperty()
  stripe_status_blob = ndb.StringProperty()


class Call(Model):
  """An instance of a call from an agent to a client.

  Ancestor: None
  Name: (str) Hash of the Twillio Call SID.
  """
  hash = ndb.IntegerProperty(required=True)
  created_at = ndb.DateTimeProperty(required=True)
  last_updated_at = ndb.DateTimeProperty()
  phone = ndb.StringProperty(required=True)
  sid = ndb.StringProperty(required=True)
  employee_id = ndb.StringProperty(required=True)
  handle_for_agent = ndb.StringProperty(required=True)
  answered_at = ndb.DateTimeProperty()
  duration_seconds = ndb.IntegerProperty()
  fee_cents_per_minute = ndb.IntegerProperty(default=100)
  completed = ndb.BooleanProperty(default=False)
  completed_at = ndb.DateTimeProperty()
  had_conversation = ndb.BooleanProperty(default=False)
  charged = ndb.BooleanProperty(default=False)
  needs_followup = ndb.BooleanProperty(default=False)
  notes = ndb.StringProperty()
  debrief_completed_at = ndb.DateTimeProperty()
  debriefed = ndb.BooleanProperty(default=False)

  @classmethod
  def get_by_handle(cls, call_handle):
    calls = cls.query(cls.handle_for_agent == call_handle).fetch()
    if calls:
      return calls[0]

  @classmethod
  def history_for_client(cls, client_id):
    calls = cls.query(cls.phone == client_id).fetch()
    return sorted(calls, key=lambda call: call.created_at, reverse=True)

  @classmethod
  def history_for_employee(cls, employee_id):
    calls = cls.query(cls.employee_id == employee_id).fetch()
    return sorted(calls, key=lambda call: call.created_at, reverse=True)

  @classmethod
  def need_debrief(cls):
    calls = cls.query(
      cls.debriefed == False,
      cls.completed == True).fetch()
    return sorted(calls, key=lambda call: call.created_at, reverse=True)
