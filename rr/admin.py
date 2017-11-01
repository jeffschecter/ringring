import logging

import flask

from rr import auth
from rr import conf
from rr import db
from rr import utils


# ---------------------------------------------------------------------------- #
# Utils.                                                                       #
# ---------------------------------------------------------------------------- #

def _response(**kwargs):
  logging.info("ADMIN RESPONSE: {}".format(kwargs.keys()))
  return flask.Response(utils.serialize(kwargs), mimetype="text/json")


# ---------------------------------------------------------------------------- #
# Endpoints.                                                                   #
# ---------------------------------------------------------------------------- #

@auth.with_admin_auth
def create_employee(digits, **kwargs):
  existing = db.get_employee(digits)
  created = (existing is None) and db.create_employee(digits)
  return _response(
      already_exists=bool(existing),
      created_employee=created)
