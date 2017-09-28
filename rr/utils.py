import datetime
import hashlib
import json

from google.appengine.ext import ndb


def hash(*args):
  hobj = hashlib.md5("".join(str(obj) for obj in args))
  return int(hobj.hexdigest(), 16) % (2 ** 48)


_PROTECTED_FIELDS = set([
  "phone",
  "session_id",
  "stripe_customer_id",
  "user_agent",
  "confirmation_code",
  "stripe_customer_id",
  "card_address_zip",
  "card_last_digits",
  "claimed_by",
  "sid",
  "employee_id",
  "stripe_account_id",
  ])


def make_safe(d_obj):
  for dkey in d_obj.keys():
    if dkey in _PROTECTED_FIELDS:
      del d_obj[dkey]


def id_hash(model):
  return hash(model.key.id(), model.created_at)


def _default_serializer(obj):
    if isinstance(obj, (datetime.datetime, datetime.date)):
      return obj.isoformat()
    elif isinstance(obj, ndb.Model):
      d_obj = obj._to_dict()
      make_safe(d_obj)
      return d_obj
    raise TypeError ("Type %s not serializable" % type(obj))


def serialize(obj):
  return json.dumps(obj, default=_default_serializer)
