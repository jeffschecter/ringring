/* ------------------------------------------------------------------------- *
 * Namespace everything to prevent conflicts!                                *
 * ------------------------------------------------------------------------- */

var cp = {
  stor: localStorage,
  sid: localStorage.getItem("sid"),
  ua: navigator.userAgent,
  page: location,
  tz: (new Date()).getTimezoneOffset() / 60,
  tw: Twilio,
  inflight: false,
  incall: false,
  message_timeout: null,

  employee: null,
  first_calls: [],
  followup_calls: [],
  active_client: null,
  active_history: [],

  active_call: {
    handle: null,
    answer_time: null,
  },

  device_ready: false,
  device_token: null,

  blocks: {
    load: document.querySelector(".loading-anim"),
    dashboard: document.querySelector("#dashboard"),
    firsts: document.querySelector("#first-calls-container"),
    followups: document.querySelector("#followup-calls-container"),
    detail: document.querySelector("#detail"),
    client_summary: document.querySelector("#client-summary"),
    client_history: document.querySelector("#client-history"),
    call: document.querySelector("#call-container"),
    call_notes: document.querySelector("#call-notes-container"),
    initiate_call: document.querySelector("#initiate-call"),
    in_call: document.querySelector("#in-call"),
    post_call: document.querySelector("#post-call"),
    cashout_info: document.querySelector("#cashout-info-collection-container"),
    cashout_dirdep: document.querySelector("#cashout-dirdep-container"),
    cashout_ssn: document.querySelector("#cashout-full-ssn-container"),
    cashout_document: document.querySelector("#cashout-id-document-container"),
    cashout_pending: document.querySelector("#cashout-pending-container"),
    cashout_withdraw: document.querySelector("#cashout-withdraw-container"),
    cashout_may_withdraw: document.querySelector(
        "#cashout-may-withdraw-container"),
  },

  tables: {
    firsts: document.querySelector("#first-calls-table"),
    followups: document.querySelector("#followup-calls-table"),
  },

  schemas: {
    firsts: ["monicker", "timezone", "schedule_note", "topic", "created_at"],
    followups: [
        "monicker", "timezone", "followup_note", "last_called", "expecting_call_after"],
  },

  inputs: {
    call_category: function() {
      return document.querySelector(
          "input[name=debrief-category]:checked").value},
    default_category: document.querySelector("#default-category"),
    call_notes: document.querySelector("#call-notes"),
    days_to_next: document.querySelector("#days-to-next-call"),
  },

  buttons: {
    refresh: document.querySelector("#refresh-calls"),
    exit_detail: document.querySelector("#exit-detail"),
    dial: document.querySelector("#initiate-call-button"),
    hangup: document.querySelector("#hangup-button"),
    submit_debrief: document.querySelector("#submit-debrief-button"),
    cashout: document.querySelector("#footer-balance"),
  },

  text: {
    greeting: document.querySelector("#agent-greeting"),
    message: document.querySelector("#messages"),
    monicker: document.querySelector("#client-monicker"),
    timezone: document.querySelector("#client-timezone"),
    schedule: document.querySelector("#client-schedule"),
    note: document.querySelector("#client-note"),
    last_called: document.querySelector("#client-last-called"),
    balance: document.querySelector("#footer-balance"),
    cashout_balance: document.querySelector("#cashout-balance"),
    cashout_last_withdrawal: document.querySelector("#cashout-last-withdrawal"),
  },

};


cp.isdefined = function(x) {
  return typeof(x) != "undefined";
};


cp.hasvalue = function(x) {
  return cp.isdefined(x) & (x != null);
};


cp.formatDollars = function(cents) {
  var roundFn;
  if (cents == null) {
    return "$0.00";
  }
  if (cents > 0) {
    roundFn = Math.floor;
  } else {
    roundFn = Math.ceil;
  }
  return (
    "$" + roundFn(cents / 100) +
    "." + ("00" + (cents % 100)).substr(-2, 2))
};


cp.relativeDatestr = function(utcstr) {
  var year = Number(utcstr.slice(0, 4)),
    month = Number(utcstr.slice(5, 7)) - 1,
    day = Number(utcstr.slice(8, 10)),
    hour = Number(utcstr.slice(11, 13)),
    date = new Date(Date.UTC(year, month, day, hour)),
    now = new Date(),
    hourdiff = Math.round((now  - date) / (60 * 60 * 1000)),
    hournow = now.getHours(),
    daydiff = Math.ceil((hourdiff - hournow) / 24),
    hourthen = date.getHours(),
    raw_clockhour = hourthen > 12 ? hourthen - 12 : hourthen,
    clockhour = raw_clockhour == 0 ? 12 : raw_clockhour,
    ampm = hourthen >= 12 ? "pm" : "am",
    rawdaystr = daydiff + " days ago",
    daystr = daydiff == 0 ? "Today" : daydiff == 1 ? "Yesterday" : rawdaystr;
  return daystr + " at " + clockhour + ampm;
};


/* ------------------------------------------------------------------------- *
 * DOM manipulation.                                                         *
 * ------------------------------------------------------------------------- */

cp.hide = function(name) {cp.blocks[name].classList.remove("active-block")};
cp.show = function(name) {cp.blocks[name].classList.add("active-block")};
cp.write = function(name, msg) {cp.text[name].innerText = msg};


cp.activePanel = function(name) {
  var panels = ["dashboard", "detail", "cashout_info", "cashout_withdraw"],
    i;
  for (i = 0; i < panels.length; i++) {
    if (panels[i] == name) {
      cp.show(panels[i]);
    } else {
      cp.hide(panels[i]);
    }
  }
};


cp.activePhase = function(name) {
  var phases = ["initiate_call", "in_call", "post_call"],
    i;
  for (i = 0; i < phases.length; i++) {
    if (phases[i] == name) {
      cp.show(phases[i]);
    } else {
      cp.hide(phases[i]);
    }
  }
  if (name == "initiate_call") {
    cp.hide("call_notes");
  } else {
    cp.show("call_notes");
  }
};


cp.showDash = function() {
  cp.activePanel("dashboard");
  cp.activePhase("initiate_call");
  cp.clearClientHistoryDisplay();
  cp.inputs.call_notes.innerText = "";
  cp.inputs.days_to_next.value = "";
  cp.inputs.default_category.checked = true;
  cp.active_client = null;
  cp.active_call.handle = null;
  cp.active_history = [];
}


cp.displayMessage = function(text, ok) {
  cp.write("message", text);
  if (ok == true) {
    cp.text.message.classList.remove("messages-warn");
    cp.text.message.classList.add("messages-ok");
  } else {
    cp.text.message.classList.remove("messages-ok");
    cp.text.message.classList.add("messages-warn");
  }
  cp.text.message.classList.remove("message-fade-out");
  cp.text.message.classList.add("message-fade-in");
  clearTimeout(cp.message_timeout)
  cp.message_timeout = setTimeout(function() {
    cp.text.message.classList.remove("message-fade-in");
    cp.text.message.classList.add("message-fade-out");
  }, 5000);
};


cp.cellText = function(text, defaulttext) {
  defaulttext = defaulttext ? defaulttext : "";
  text = String(text ? text : defaulttext);
  if (text.match(/^\d{4}-\d{2}-\d{2}T\d{2}:/)) {
    text = text.slice(0, 10);
  }
  if (text.length > 200) {
    text = text.slice(0, 200) + "...";
  }
  return text.replace(/\n/g, " ");
};


cp.buildTable = function(container, schema, objs, callbackFactory) {
  var table = document.createElement("table"),
    row = document.createElement("tr"),
    cell, i, j, obj, value;
  if (objs.length == 0) {
    container.innerHTML = "";
    return;
  }

  // Create the header
  row.classList.add("header-row")
  for (i = 0; i < schema.length; i++) {
    cell = document.createElement("th");
    cell.innerText = schema[i].replace(/_/g, " ");
    cell.setAttribute("data", schema[i]);
    row.appendChild(cell);
  }
  table.appendChild(row);

  // Add the rows
  for (i = 0; i < objs.length; i++) {
    obj = objs[i];
    row = document.createElement("tr");
    row.setAttribute("data", obj.hash);
    if (i % 2 == 1) {
      row.classList.add("alt-row");
    }
    for (j = 0; j < schema.length; j++) {
      cell = document.createElement("td");
      value = obj[schema[j]]
      cell.title = value;
      if (value != null) {
        cell.innerText = cp.cellText(value);
      }
      row.appendChild(cell);
      if (callbackFactory != null) {
        row.addEventListener("click", callbackFactory(row));
        row.classList.add("action-row");
      }
    }
    table.appendChild(row);
  }

  // Insert into container
  container.innerHTML = "";
  container.appendChild(table);
};


cp.clearClientHistoryDisplay = function() {
  cp.blocks.client_history.innerHTML = "";
};


cp.buildClientHistoryDisplay = function() {
  var nCalls = cp.active_history.length,
    i, call, container, datespan, durationspan, notediv;
  if (nCalls == 0) {
    container = document.createElement("div");
    container.classList.add("client-history-empty");
    container.innerText = "Nobody's called this client yet!";
    cp.blocks.client_history.appendChild(container);
    return;
  }
  for (i = 0; i < nCalls; i++) {
    call = cp.active_history[i];
    container = document.createElement("div");
    container.classList.add("client-history-item");
    datespan = document.createElement("span");
    datespan.classList.add("client-history-date");
    datespan.innerText = cp.relativeDatestr(call.created_at);
    datespan.title = call.created_at;
    durationspan = document.createElement("span");
    durationspan.classList.add("client-history-duration");
    durationspan.innerText = Math.round(
        call.duration_seconds / 60) + " minutes";
    notediv = document.createElement("div");
    notediv.classList.add("client-history-note")
    notediv.innerText = cp.cellText(call.notes, "No note");
    notediv.title = call.notes;
    container.appendChild(datespan);
    container.appendChild(durationspan);
    container.appendChild(notediv);
    cp.blocks.client_history.appendChild(container);
  }
};


/* ------------------------------------------------------------------------- *
 * Client detail view.                                                       *
 * ------------------------------------------------------------------------- */

cp.receiveClientHistory = function(resp) {
  cp.active_history = resp.calls;
  cp.clearClientHistoryDisplay();
  cp.buildClientHistoryDisplay();
};


cp.showDetail = function(hash) {
  var nFirst = cp.first_calls.length,
    nFollow = cp.followup_calls.length,
    candidate, client, i, note, schedule;

  // Find our client
  for (i = 0; i < nFirst + nFollow; i++) {
    if (i < nFirst) {
      candidate = cp.first_calls[i];
    }  else {
      candidate = cp.followup_calls[i - nFirst];
    }
    if (candidate.hash == hash) {
      client = candidate;
    }
  }

  // Populate and show detail view
  if (client != null) {
    cp.active_client = client;
    note = client.followup_note ? client.followup_note : client.topic;
    if (client.expecting_call_after != null) {
      schedule = "Call on " + client.expecting_call_after.slice(0, 10);
    } else {
      schedule = client.schedule_note;
    }
    cp.write("monicker", client.monicker);
    cp.write("timezone", client.timezone);
    cp.write("schedule", schedule);
    cp.write("note", note);
    cp.activePanel("detail");
  }

  // fetch client call history
  cp.ajaxBlocking(
      "client_call_history", 
      [["phone_hash", cp.active_client.hash]],
      cp.receiveClientHistory);
};


cp.showDetailFactory = function(row) {
  return function(evt) {
    cp.showDetail(Number(row.getAttribute("data")));
  };
};


/* ------------------------------------------------------------------------- *
 * State updates.                                                            *
 * ------------------------------------------------------------------------- */

cp.updateEmployee = function() {
  var needDirDep, needPID, needDoc, bal, mayWithdraw;
  // Parse verification fields needed
  if (cp.hasvalue(cp.employee.verification_fields_needed)) {
    if (typeof(cp.employee.verification_fields_needed == "string")) {
      cp.employee.verification_fields_needed = JSON.parse(
          cp.employee.verification_fields_needed);
    }
  }

  // Do we need to collect direct deposit info?
  if (cp.employee.setup_done != true) {
    cp.activePanel("cashout_info");
    needDirDep = cp.employee.given_name == null;
    if (cp.employee.verification_fields_needed != null) {
      needPID = cp.employee.verification_fields_needed.indexOf(
          "legal_entity.personal_id_number") >= 0;
      needDoc = cp.employee.verification_fields_needed.indexOf(
          "legal_entity.verification.document") >= 0;
    }
    if (needDirDep == true) {
      cp.hide("cashout_ssn");
      cp.hide("cashout_document");
      cp.show("cashout_dirdep");
      cp.hide("cashout_pending");
    } else if (needPID == true) {
      cp.show("cashout_ssn");
      cp.hide("cashout_document");
      cp.hide("cashout_dirdep");
      cp.hide("cashout_pending");
    } else if (needDoc == true) {
      cp.hide("cashout_ssn");
      cp.show("cashout_document");
      cp.hide("cashout_dirdep");
      cp.hide("cashout_pending");
    } else {
      cp.hide("cashout_ssn");
      cp.hide("cashout_document");
      cp.hide("cashout_dirdep");
      cp.show("cashout_pending");
    }
  }

  // How do we greet the agent?
  if (cp.employee.given_name == null) {
    cp.text.greeting.innerText = "Please finish filling out employee details!"
  } else {
    cp.text.greeting.innerText = "Hello, " + cp.employee.given_name;
  }

  // What's the agent's balance?
  bal = cp.formatDollars(cp.employee.balance_cents);
  cp.write("balance", "[current balance: " + bal + "]");
  cp.write("cashout_balance", bal);
  if (cp.employee.last_cashout != null) {
    cp.write(
        "cashout_last_withdrawal",
        ("You last cashed out your balance on " +
         cp.employee.last_cashout.slice(0, 10) + "."));
  }
  mayWithdraw = cp.employee.balance_cents >= PAYOUT_CENTS_MINIMUM;
  if (mayWithdraw) {
    cp.show("cashout_may_withdraw");
  } else {
    cp.hide("cashout_may_withdraw");
  }
};


cp.updateFirstCalls = function() {
  cp.buildTable(
      cp.tables.firsts, cp.schemas.firsts, cp.first_calls,
      cp.showDetailFactory)
};


cp.updateFollowupCalls = function() {
  cp.buildTable(
      cp.tables.followups, cp.schemas.followups, cp.followup_calls,
      cp.showDetailFactory);
};


/* ------------------------------------------------------------------------- *
 * Htting the API.                                                           *
 * ------------------------------------------------------------------------- */

cp.preparePayload = function(kvs) {
  var i, payload;
  if (kvs == null) {
    kvs = [];
  };
  kvs.push(["sid", cp.sid]);
  return JSON.stringify(kvs);
};


cp.receiveState = function(state) {
  if (state.employee != null) {
    cp.employee = state.employee;
    cp.updateEmployee();
  }
  if (state.first_calls != null) {
    cp.first_calls = state.first_calls;
    cp.updateFirstCalls();
  }
  if (state.followup_calls != null) {
    cp.followup_calls = state.followup_calls;
    cp.updateFollowupCalls();
  }
  if (state.device_token != null) {
    cp.device_token = state.device_token;
    cp.tw.Device.setup(cp.device_token);
  }
};


cp.ajaxBlocking = function(endpoint, kvs, callback) {
  var xhttp,
    payload = cp.preparePayload(kvs);
  if (cp.inflight) {
    return;
  }
  if (callback == null) {
    callback = console.log;
  }
  xhttp = new XMLHttpRequest()
  xhttp.onreadystatechange = function() {
    if (this.readyState == 4) {
      setTimeout(function() {
        cp.blocks.load.classList.remove("in-flight");
      }, 150);
    }
    if (this.readyState == 4 && this.status == 200) {
      cp.inflight = false;
      resp = JSON.parse(this.response);
      cp.receiveState(resp);
      callback(resp);
    } else if (this.readyState == 4 && this.status != 200) {
      cp.inflight = false;
      console.log(this);
      cp.displayMessage("Something went wrong on the server");
    }
  };
  cp.inflight = true;
  cp.blocks.load.classList.add("in-flight");
  xhttp.open("POST", "api/" + endpoint, true);
  xhttp.send(payload);
};


cp.ajax = function(endpoint, kvs, callback) {
  var xhttp,
    payload = cp.preparePayload(kvs);
  if (callback == null) {
    callback = console.log;
  }
  xhttp = new XMLHttpRequest()
  xhttp.onreadystatechange = function() {
    if (this.readyState == 4 && this.status == 200) {
      resp = JSON.parse(this.response);
      cp.receiveState(resp);
      callback(resp);
    } else if (this.readyState == 4 && this.status != 200) {
      console.log(this);
    }
  };
  xhttp.open("POST", "api/" + endpoint, true);
  xhttp.send(payload);
};


/* ------------------------------------------------------------------------- *
 * Make a call.                                                              *
 * ------------------------------------------------------------------------- */

cp.dial = function() {
  var params = {},
    handle = (new Date()).getTime() + "." + cp.employee.hash + Math.random();
  if (!cp.device_ready) {
    cp.displayMessage("Device not yet ready to make calls");
    return;
  }
  if (cp.incall) {
    cp.displayMessage("Already in call, can't dial");
    return;
  }
  if (cp.active_client == null) {
    cp.displayMessage("No active client to call");
    return
  }
  cp.incall = true;
  cp.active_call.handle = handle;
  params.sid = cp.sid;
  params.user_agent = cp.ua;
  params.phone_hash = cp.active_client.hash;
  params.handle_for_agent = handle;
  cp.tw.Device.connect(params);
};


cp.checkCallOver = function() {
  cp.ajaxBlocking("call_exists",
      [["handle", cp.active_call.handle], ["include_history", true]],
    function(resp) {
      if (resp.exists == true & resp.answered == true) {
        cp.activePhase("post_call");
      } else {
        cp.active_call.handle = null;
        cp.activePhase("initiate_call");
      }
      if (cp.isdefined(resp.calls)) {
        if (resp.calls.length > cp.active_history.length) {
          cp.receiveClientHistory(resp);
        }
      }
    });
};


cp.submitDebrief = function() {
  var category = cp.inputs.call_category(),
    notes = cp.inputs.call_notes.innerText,
    days_to_next = cp.inputs.days_to_next.value,
    call_again = category == "retry" | category == "followup";
  if (notes.length == 0 & call_again) {
    cp.displayMessage("Leave notes when we need to call the client again!");
    return;
  }
  if (days_to_next.length == 0 & call_again) {
    cp.displayMessage("How many days should we wait before calling again?");
    return;
  }
  if (!(Number(days_to_next) > -1) & call_again) {
    cp.displayMessage("Days to next call must be a number 0 or higher!");
    return;
  }
  cp.ajaxBlocking(
      "debrief",
      [["handle", cp.active_call.handle],
       ["category", category],
       ["notes", notes],
       ["days_to_next", days_to_next]],
      function(resp) {
        if (resp.success == true) {
          cp.showDash();
          cp.displayMessage("Call task completed!", true);
        } else {
          cp.displayMessage("We couldn't process your call feedback");
        }
      });
};


cp.tw.Device.ready(function(device) {
  cp.device_ready = true;
  cp.displayMessage("Phone ready to make calls", true);
});


cp.tw.Device.error(function(err) {
  cp.displayMessage(
      "Call error; this task may have been claimed by another agent");
  console.log(err);
  cp.page.reload(true);
});


cp.tw.Device.connect(function(evt) {
  cp.displayMessage("Call connected", true);
  console.log(evt);
  cp.activePhase("in_call");
});


cp.tw.Device.disconnect(function(evt) {
  cp.incall = false;
  cp.displayMessage("Call ended", true)
  console.log(evt);
  cp.checkCallOver();
});


/* ------------------------------------------------------------------------- *
 * UI Listener functions.                                                    *
 * ------------------------------------------------------------------------- */

cp.buttons.refresh.addEventListener(
    "click", function() {cp.ajaxBlocking("available_calls")});


cp.buttons.exit_detail.addEventListener(
    "click", function() {
        cp.showDash();
        cp.ajaxBlocking("available_calls");
    });


cp.buttons.dial.addEventListener(
    "click", cp.dial);


cp.buttons.hangup.addEventListener(
    "click", function() {cp.tw.Device.disconnectAll()});


cp.buttons.submit_debrief.addEventListener(
    "click", cp.submitDebrief);


cp.buttons.cashout.addEventListener(
    "click", function() {
      if ((cp.active_client == null) & (cp.employee.setup_done == true)) {
        cp.activePanel("cashout_withdraw")
      }
    });

/* ------------------------------------------------------------------------- *
 * Script.                                                                   *
 * ------------------------------------------------------------------------- */

 cp.ajax("available_calls");
 cp.ajax("tw_token");
