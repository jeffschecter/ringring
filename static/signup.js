/* ------------------------------------------------------------------------- *
 * Namespace everything to prevent conflicts!                                *
 * ------------------------------------------------------------------------- */

var su = {
  stor: localStorage,
  sid: null,
  sid_source: null,

  inflight: false,
  card_last_digits: null,
  error_message: null,
  monicker: null,
  phone_access_confirmed: null,
  phone_digits: null,
  schedule_note: null,
  session_confirmed: false,
  timezone: null,
  topic: null,
  ui_state: "splash",

  card: strp.card,
  page: location,

  blocks: {
    load: document.querySelector(".loading-anim"),
    phone: document.querySelector("#phone-container"),
    confirmation: document.querySelector("#confirmation-code-container"),
    details: document.querySelector("#details-container"),
    payment: document.querySelector("#payment-container"),
    finished: document.querySelector("#finished-container"),
    logout: document.querySelector("#logout-container"),
    delete: document.querySelector("#phone-delete-container"),
    cockpit: document.querySelector("#cockpit-link-container"),
  },

  inputs: {
    phone: document.querySelector("#phone-input"),
    confirmation: document.querySelector("#confirmation-code-input"),
    timezone: document.querySelector("#timezone-select"),
    schedulenote: document.querySelector("#schedule-note-input"),
    monicker: document.querySelector("#monicker-input"),
    topic: document.querySelector("#topic-input"),
  },

  buttons: {
    phoneSubmit: document.querySelector("#phone-submit"),
    confirmationSubmit: document.querySelector("#confirmation-code-submit"),
    confirmationResend: document.querySelector("#confirmation-code-resend"),
    detailsSubmit: document.querySelector("#details-submit"),
    pay: document.querySelector("#payment-submit"),
    logout: document.querySelector("#logout-submit"),
    phoneDelete: document.querySelector("#phone-delete-submit"),
    cockpit: document.querySelector("#cockpit-link"),
  },

  text: {
    message: document.querySelector("#messages"),
    progress1: document.querySelector("#progress-step-1"),
    progress2: document.querySelector("#progress-step-2"),
    progress3: document.querySelector("#progress-step-3"),
    progress4: document.querySelector("#progress-step-4"),
    phone: document.querySelector("#present-phone"),
    card: document.querySelector("#present-card"),
    name: document.querySelector("#present-name"),
  },

  ui_states: {},
  validTimezones: [
    "eastern", "central", "mountain", "pacific",
    "alaskan", "hawaiian"],
};


su.isdefined = function(x) {
  return typeof(x) != "undefined";
};


su.whenEnterKey = function(fn) {
  return function(event) {
    if (event.keyCode == 13) {
      fn();
      return false;
    }
  };
};


su.makePhoneString = function(raw_digits) {
  var digits = raw_digits == null ? "" : raw_digits,
    start = "(" + digits.slice(0, 3) + ") ",
    middle = digits.slice(3, 6) + "-",
    end = digits.slice(6, 10);
  return start + middle + end;
};


su.logout = function() {
  su.stor.clear();
  su.page.reload(true);
};


/* ------------------------------------------------------------------------- *
 * DOM manipulation.                                                         *
 * ------------------------------------------------------------------------- */

su.hide = function(name) {su.blocks[name].classList.remove("active-block")};
su.show = function(name) {su.blocks[name].classList.add("active-block")};
su.write = function(name, msg) {su.text[name].innerText = msg};


su.currentStep = function(n) {
  var i, steps = [
      su.text.progress1, su.text.progress2,
      su.text.progress3, su.text.progress4];
  for (i = 0; i < 4; i++) {
    if ((i + 1) == n) {
      steps[i].classList.add("active-progress-step");
      steps[i].classList.remove("inactive-progress-step");
    } else {
      steps[i].classList.remove("active-progress-step");
      steps[i].classList.add("inactive-progress-step");
    }
  }
};


su.activeBlock = function(name) {
  var blk;
  for (blk in su.blocks) {
    if (su.blocks.hasOwnProperty(blk)) {
      if (blk == name) {
        su.show(blk);
      } else {
        su.hide(blk);
      };
    };
  };
};


su.displayMessage = function(text) {
  su.write("message", text);
  su.text.message.classList.remove("message-fade-out");
  su.text.message.classList.add("message-fade-in");
  setTimeout(function() {
    su.text.message.classList.remove("message-fade-in");
    su.text.message.classList.add("message-fade-out");
  }, 5000);
};


/* ------------------------------------------------------------------------- *
 * Htting the API.                                                           *
 * ------------------------------------------------------------------------- */

su.preparePayload = function(kvs) {
  var i, payload;
  if (kvs == null) {
    kvs = [];
  };
  kvs.push(["sid", su.sid]);
  return JSON.stringify(kvs);
};


su.updateField = function(state, state_field, self_field) {
  if (self_field == null) {
    self_field = state_field;
  };
  if (state[state_field] != null) {
    su[self_field] = state[state_field];
  };
};


su.updateModel = function(state) {
  su.updateField(state, "card_last_digits");
  su.updateField(state, "error_message");
  su.updateField(state, "monicker");
  su.updateField(state, "new_session_id", "sid");
  su.updateField(state, "phone_access_confirmed");
  su.updateField(state, "phone_digits");
  su.updateField(state, "schedule_note");
  su.updateField(state, "session_confirmed");
  su.updateField(state, "timezone");
  su.updateField(state, "topic");
  su.updateField(state, "ui_state", "ui_state");
};


su.receiveState = function(state) {
  var ui = state.ui_state,
    error_message = state.error_message;
  su.updateModel(state);
  if (ui != null) {
    su.ui_states[ui]();
  }
  if (error_message != null) {
    su.displayMessage(error_message);
  }
  su.write("phone", su.makePhoneString(su.phone_digits));
  su.write("card", su.card_last_digits);
  su.write("name", su.monicker);

  // Display the logout button when we know a phone number
  if (su.phone_digits != null) {
    su.show("logout");
  } else {
    su.hide("logout");
  }

  // Display the delete account button when client has a confirmed phone
  if (su.phone_access_confirmed == true) {
    su.show("delete");
  } else {
    su.hide("delete");
  }

  // Display the cockpit link when client is an authed employee
  if (state.cockpit_link == true) {
    su.buttons.cockpit.href = "/cockpit?" + encodeURIComponent(su.sid);
    su.show("cockpit");
  } else if (state.cockpit_link == false) {
    su.hide("cockpit");
  }
};


su.ajax = function(endpoint, kvs) {
  var xhttp,
    payload = su.preparePayload(kvs);
  if (su.inflight) {
    return;
  }
  xhttp = new XMLHttpRequest()
  xhttp.onreadystatechange = function() {
    if (this.readyState == 4) {
      setTimeout(function() {
        su.blocks.load.classList.remove("in-flight");
      }, 150);
    }
    if (this.readyState == 4 && this.status == 200) {
      su.inflight = false;
      su.receiveState(JSON.parse(this.response));
    } else if (this.readyState == 4 && this.status != 200) {
      su.inflight = false;
      console.log(this);
    }
  };
  su.inflight = true;
  su.blocks.load.classList.add("in-flight");
  xhttp.open("POST", "api/" + endpoint, true);
  xhttp.send(payload);
};


/* ------------------------------------------------------------------------- *
 * Set the user's session ID based on either the ID served up by the app, or *
 * an existing session ID retrieved from local storage.                      *
 * ------------------------------------------------------------------------- */

su.setSessionId = function() {
  var stored_sid = su.stor.getItem("sid"),
    served_sid = SERVED_SESSION_ID;
  if (stored_sid != null) {
    su.sid = stored_sid;
    su.sid_source = "stored";
  } else if (su.isdefined(served_sid)) {
    su.sid = served_sid;
    su.sid_source = "served";
  } else {
    su.sid_source = "missing";
    return;
  };
  su.stor.setItem("sid", su.sid);
  su.ajax("ensure_session_created");
};


/* ------------------------------------------------------------------------- *
 * State change updates.                                                     *
 * ------------------------------------------------------------------------- */


su.ui_states.splash = function() {
  su.activeBlock("phone");
  su.currentStep(1);
  su.inputs.phone.focus();
};


su.ui_states.awaiting_confirmation = function() {
  su.activeBlock("confirmation");
  su.currentStep(1);
  su.inputs.confirmation.focus();
};


su.ui_states.details = function() {
  su.activeBlock("details");
  su.currentStep(2);
  su.inputs.monicker.focus();
};


su.ui_states.payment = function() {
  su.activeBlock("payment");
  su.currentStep(3);
};


su.ui_states.finished = function() {
  su.activeBlock("finished");
  su.currentStep(4);
};


su.ui_states.logout = su.logout;


/* ------------------------------------------------------------------------- *
 * Listener functions.                                                       *
 * ------------------------------------------------------------------------- */

su.phoneSubmit = function() {
  var digits = su.inputs.phone.value,
    valid_phone;
  digits = digits.replace(/[^0-9]/g, "");
  if (digits.length == 11) {
    digits = digits.slice(1, 11);
  }
  valid_phone = digits.match(/^\d{10}$/);
  if (valid_phone) {
    su.phone_digits = digits;
    su.ajax("set_phone", [["digits", digits]]);
  } else  if (digits == "") {
    su.displayMessage("Please enter a valid U.S. phone number.");
  } else {
    su.displayMessage("\"" + digits + "\" is not a valid U.S. phone number.");
  }
};
su.buttons.phoneSubmit.addEventListener(
    "click", su.phoneSubmit);
su.buttons.confirmationResend.addEventListener(
    "click", su.phoneSubmit);
su.inputs.phone.addEventListener(
    "keydown", su.whenEnterKey(su.phoneSubmit));


su.confirmationSubmit = function() {
  var code = su.inputs.confirmation.value,
    valid_code = code.toLowerCase().match(
        /^[abcdefghijkmnpqrstuvwxyz0123456789]{4}$/);
  if (valid_code) {
    su.ajax(
        "confirm_phone",
        [["digits", su.phone_digits], ["confirmation_code", code]]);
  } else {
    su.displayMessage("\"" + code + "\" is not a valid confirmation code.");
  }
};
su.buttons.confirmationSubmit.addEventListener(
    "click", su.confirmationSubmit);
su.inputs.confirmation.addEventListener(
    "keydown", su.whenEnterKey(su.confirmationSubmit));


su.detailsSubmit = function() {
  var tz = su.inputs.timezone.value,
    schedulenote = su.inputs.schedulenote.value,
    monicker = su.inputs.monicker.value,
    topic = su.inputs.topic.value;
  if (su.validTimezones.indexOf(tz) == -1) {
    su.displayMessage("Please select your timezone!");
  } else if (schedulenote.length < 3) {
    su.displayMessage("Please tell us when we should call you!");
  } else if (monicker.length == 0) {
    su.displayMessage("Please tell us your name!");
  } else if (topic.length < 5) {
    su.displayMessage("Please tell us what you'd like to talk about!");
  } else {
    su.ajax("submit_details",
        [["tz", tz],
         ["schedule", schedulenote],
         ["monicker", monicker],
         ["topic", topic]]);
  }
};
su.buttons.detailsSubmit.addEventListener(
    "click", su.detailsSubmit);


su.card.addEventListener("change", function(event) {
  if (event.error) {
    su.displayMessage(event.error.message);
  } else {
    su.displayMessage("");
  }
});


su.paymentSubmit = function() {
  strp.stripe.createToken(su.card).then(function(result) {
    if (result.error) {
      su.displayMessage(result.error.message);
    } else {
      su.ajax("payment_token",
          [["stripe_token", result.token]]);
    }
  });
};
su.buttons.pay.addEventListener(
    "click", su.paymentSubmit)


su.deletePhoneSubmit = function() {
  var inp;
  for (inp in su.inputs) {
    if(su.inputs.hasOwnProperty(inp)) {
      su.inputs[inp].value = null;
    }
  }
  su.ajax("delete_phone", []);
};
su.buttons.phoneDelete.addEventListener(
    "click", su.deletePhoneSubmit)


su.buttons.logout.addEventListener(
    "click", su.logout);


/* ------------------------------------------------------------------------- *
 * Script                                                                    *        
 * ------------------------------------------------------------------------- */

su.setSessionId();
