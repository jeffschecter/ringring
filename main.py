import json
import logging
import urllib

import flask

from rr import auth
from rr import cashout
from rr import cockpit
from rr import conf
from rr import signup
from rr import strp


app = flask.Flask(__name__)
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0


# ---------------------------------------------------------------------------- #
# Utils.                                                                       #
# ---------------------------------------------------------------------------- #

def get_post_params():
  req = flask.request
  params = dict(json.loads(req.data))
  display_params = dict(params)
  if "datauri" in display_params:
    display_params["datauri"] = display_params["datauri"][:100] + "..."
  logging.info("POST PARAMS: {}".format(display_params))
  params.update({"user_agent": req.user_agent.string})
  params.update({"ip_address": req.headers.get(
      "X-Forwarded-For", req.remote_addr)})
  return params


def get_tw_webhook_params():
  params = dict((k.lower(), v) for k, v in flask.request.form.items())
  logging.info("TWILIO WEBHOOK POST PARAMS: {}".format(params))
  return params


def get_strp_webhook_event(secret):
  req = flask.request
  sig = req.headers.get("Stripe-Signature")
  event = strp.webhook_event(req.data, sig, secret)
  if event is None:
    logging.error("STRIPE WEBHOOK FAILED: {}".format(sig))
    flask.abort(404)
  logging.info("STRIPE WEBHOOK PARSED: {} {} {}".format(
      event.type, event.id, sig))
  return event


def auth_from_query():
  req = flask.request
  return bool(auth.authed_employee_from_sid(
      urllib.unquote(req.query_string), req.user_agent.string))


@app.errorhandler(500)
def serve_error(e):
  logging.exception(e)
  return str(e), 500


@app.after_request
def add_header(req):
    req.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    req.headers["Pragma"] = "no-cache"
    req.headers["Expires"] = "0"
    req.headers['Cache-Control'] = 'public, max-age=0'
    return req


# ---------------------------------------------------------------------------- #
# Signup app.                                                                  #
# ---------------------------------------------------------------------------- #

@app.route("/", methods=["GET"])
def serve_index():
  return flask.render_template(
      "index.html",
      conf=conf,
      session_id=signup.session_id())


@app.route("/api/ensure_session_created", methods=["POST"])
def ensure_session_created():
  return signup.ensure_session_created(**get_post_params())


@app.route("/api/set_phone", methods=["POST"])
def set_phone():
  return signup.set_phone(**get_post_params())


@app.route("/api/confirm_phone", methods=["POST"])
def confrm_phone():
  return signup.confirm_phone(**get_post_params())


@app.route("/api/submit_details", methods=["POST"])
def submit_details():
  return signup.submit_details(**get_post_params())


@app.route("/api/payment_token", methods=["POST"])
def payment_token():
  return signup.payment_token(**get_post_params())


@app.route("/api/delete_phone", methods=["POST"])
def delete_phone():
  return signup.delete_phone(**get_post_params())


# ---------------------------------------------------------------------------- #
# Agent payment.                                                               #
# ---------------------------------------------------------------------------- #

@app.route("/api/submit_dirdep", methods=["POST"])
def submit_dirdep():
  return cashout.submit_dirdep(**get_post_params())


@app.route("/api/submit_personal_id", methods=["POST"])
def submit_personal_id():
  return cashout.submit_personal_id(**get_post_params())


@app.route("/api/submit_id_document", methods=["POST"])
def submit_id_document():
  return cashout.submit_id_document(**get_post_params())


# ---------------------------------------------------------------------------- #
# Stripe webhooks.                                                             #
# ---------------------------------------------------------------------------- #

@app.route("/api/strp_events_account", methods=["POST"])
def strp_events_account():
  return cashout.strp_events_account(get_strp_webhook_event(
      conf.creds.stripe_account_webhook_secret))


@app.route("/api/strp_events_connect", methods=["POST"])
def strp_events_connect():
  return cashout.strp_events_connect(get_strp_webhook_event(
      conf.creds.stripe_connect_webhook_secret))


# ---------------------------------------------------------------------------- #
# Agent app.                                                                   #
# ---------------------------------------------------------------------------- #

@app.route("/cockpit", methods=["GET"])
def serve_cockpit():
  if auth_from_query():
    return flask.render_template(
        "cockpit_with_cashout.html",
        conf=conf)
  else:
    return flask.redirect("/", code=302)


@app.route("/api/available_calls", methods=["POST"])
def available_calls():
  return cockpit.available_calls(**get_post_params())


@app.route("/api/tw_token", methods=["POST"])
def tw_token():
  return cockpit.tw_token(**get_post_params())


@app.route("/api/call_exists", methods=["POST"])
def call_exists():
  return cockpit.call_exists(**get_post_params())


@app.route("/api/debrief", methods=["POST"])
def debrief():
  return cockpit.debrief(**get_post_params())


@app.route("/api/client_call_history", methods=["POST"])
def client_call_history():
  return cockpit.client_call_history(**get_post_params())


@app.route("/api/agent_call_history", methods=["POST"])
def agent_call_history():
  return cockpit.agent_call_history(**get_post_params())


# ---------------------------------------------------------------------------- #
# Twilio webhooks.                                                             #
# ---------------------------------------------------------------------------- #

@app.route("/api/tw_dial", methods=["POST"])
def tw_dial():
  return cockpit.tw_dial(**get_tw_webhook_params())


@app.route("/api/tw_status", methods=["POST"])
def tw_status():
  return cockpit.tw_status(**get_tw_webhook_params())
