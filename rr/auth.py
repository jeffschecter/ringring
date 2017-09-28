import flask

from rr import conf
from rr import db



def authed_employee_from_sid(sid, user_agent):
  sess, phone = db.get_valid_session_with_phone(sid, user_agent)
  if sess and phone:
    return db.authed_employee(sess, phone)


def with_employee_auth(fn):
  def _wrapper(sid=None, user_agent=None, **kwargs):
    authed_employee = authed_employee_from_sid(sid, user_agent)
    if authed_employee:
      kwargs["employee"] = authed_employee
      return fn(**kwargs)
    else:
      flask.abort(404)
  return _wrapper


def with_admin_auth(fn):
  def _wrapper(sid=None, user_agent=None, **kwargs):
    sess, phone = db.get_valid_session_with_phone(sid, user_agent)
    if phone.key.id() in conf.creds.admin_phones:
      return fn(**kwargs)
    else:
      flask.abort(404)
  return _wrapper
