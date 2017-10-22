/* ------------------------------------------------------------------------- *
 * Namespace everything to prevent conflicts!                                *
 * ------------------------------------------------------------------------- */

 var co = {
  dirdep_fields: [
    "given_name", "family_name", "date_of_birth", "ssn_last_digits",
    "address_line_1", "address_line_2", "address_city", "address_state",
    "address_zip", "account", "routing", "consent"],

  blocks: {
    dirdep: document.querySelector("#cashout-dirdep-container"),
    ssn: document.querySelector("#cashout-full-ssn-container"),
  },

  inputs: {
    // dirdep fields
    given_name: document.querySelector("#cashout-given-name"),
    family_name: document.querySelector("#cashout-family-name"),
    date_of_birth: document.querySelector("#cashout-dob"),
    ssn_last_digits: document.querySelector("#cashout-ssn"),
    address_line_1: document.querySelector("#cashout-addr-1"),
    address_line_2: document.querySelector("#cashout-addr-2"),
    address_city: document.querySelector("#cashout-addr-city"),
    address_state: document.querySelector("#cashout-addr-state"),
    address_zip: document.querySelector("#cashout-addr-zip"),
    account: document.querySelector("#cashout-account-number"),
    routing: document.querySelector("#cashout-routing-number"),
    consent: document.querySelector("#cashout-consent"),

    // additional ID verification
    full_ssn: document.querySelector("#cashout-full-ssn"),
    id_document: document.querySelector("#cashout-id-document"),
  },

  buttons: {
    submit_info: document.querySelector("#cashout-submit-info"),
    submit_full_ssn: document.querySelector("#cashout-submit-full-ssn"),
    submit_id_document: document.querySelector("#cashout-submit-id-document"),
    back: document.querySelector("#cashout-back-button"),
    withdraw: document.querySelector("#cashout-submit-withdrawal-button"),
  },

  valid: {},
  territories: [
    "AL", "AK", "AS", "AZ", "AR", "CA", "CO", "CT", "DE", "DC", "FM", "FL",
    "GA", "GU", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MH",
    "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM",
    "NY", "NC", "ND", "MP", "OH", "OK", "OR", "PW", "PA", "PR", "RI", "SC",
    "SD", "TN", "TX", "UT", "VT", "VI", "VA", "WA", "WV", "WI", "WY", "AE",
    "AP", "AA"
    ],
};


co.isdefined = function(x) {
  return typeof(x) != "undefined";
};

co.hide = function(name) {co.blocks[name].classList.remove("active-block")};
co.show = function(name) {co.blocks[name].classList.add("active-block")};


/* ------------------------------------------------------------------------- *
 * Input validation                                                          *
 * ------------------------------------------------------------------------- */

 co.addValidator = function(name, blankOK, regexp, fn) {
  co.inputs[name].addEventListener("focus", function() {
      co.inputs[name].classList.remove("textinput-verified");
      co.inputs[name].classList.remove("textinput-error");
  });
  co.inputs[name].addEventListener("blur", function() {
    var text = co.inputs[name].value;
    if ((text == "") & (blankOK != true)) {
      co.inputs[name].classList.remove("textinput-verified");
      co.inputs[name].classList.remove("textinput-error");
      co.valid[name] = null;
    } else if (co.isdefined(regexp) & (!text.match(regexp))) {
      co.inputs[name].classList.remove("textinput-verified");
      co.inputs[name].classList.add("textinput-error");
      co.valid[name] = false;
    } else if (co.isdefined(fn) ? !fn(text) : false) {
      co.inputs[name].classList.remove("textinput-verified");
      co.inputs[name].classList.add("textinput-error");
      co.valid[name] = false;
    } else {
      co.inputs[name].classList.add("textinput-verified");
      co.inputs[name].classList.remove("textinput-error");
      co.valid[name] = true;
    }
  });
 };


co.addValidator("given_name", false);
co.addValidator("family_name", false);
co.addValidator("date_of_birth", false, /^\d{2}\/\d{2}\/\d{4}$/,
  function(text) {
    var date = new Date(text),
      latest = new Date(),
      earliest = new Date();
    latest.setFullYear(latest.getFullYear() - 18);
    earliest.setFullYear(earliest.getFullYear() - 100);
    return !isNaN(date.getDate()) & (date > earliest) & (date < latest);
  });
co.addValidator("ssn_last_digits", false, /^\d{4}$/);
co.addValidator("address_line_1", false);
co.addValidator("address_line_2", true);
co.addValidator("address_city", false);
co.addValidator("address_state", false, /^[A-z]{2}$/,
    function(text) {return co.territories.indexOf(text.toUpperCase()) > 0});
co.addValidator("address_zip", false, /^\d{5}$/);
co.addValidator("account", false, /^\d{6,16}$/);
co.addValidator("routing", false, /^\d{9}$/);
co.addValidator("consent", false, /^I Agree$/i);
co.addValidator("full_ssn", false, /^\d{9}$/);


/* ------------------------------------------------------------------------- *
 * Submitting dir dep info                                                   *
 * ------------------------------------------------------------------------- */

co.dirDepInfoReady = function() {
  var i, key;
  for (i = 0; i < co.dirdep_fields.length; i++) {
    key = co.dirdep_fields[i];
    if (co.inputs.hasOwnProperty(key)) {
      if (co.valid[key] != true) {
        return false;
      }
    }
  }
  return true;
};


co.checkSetupDone = function(resp) {
  if ((resp.success == true) & (resp.employee.setup_done)) {
    cp.activePanel("dashboard");
  }
};


co.submitDirDepInfo = function(token) {
  cp.ajaxBlocking(
      "submit_dirdep",
      [["stripe_token", token],
       ["id_info", {
         "given_name": co.inputs.given_name.value,
         "family_name": co.inputs.family_name.value,
         "date_of_birth": co.inputs.date_of_birth.value,
         "ssn_last_digits": co.inputs.ssn_last_digits.value,
         "address_line_1": co.inputs.address_line_1.value,
         "address_line_2": co.inputs.address_line_2.value,
         "address_city": co.inputs.address_city.value,
         "address_state": co.inputs.address_state.value,
         "address_zip": co.inputs.address_zip.value}]],
      co.checkSetupDone);
};


co.getStripeTokenAndSubmitDirDep = function() {
  var promise;
  if (!co.dirDepInfoReady()) {
    cp.displayMessage("Something's not right! Double-check your info.");
    return;
  }
  promise = strp.stripe.createToken("bank_account", {
    "country": "us",
    "currency": "usd",
    "routing_number": co.inputs.routing.value,
    "account_number": co.inputs.account.value,
    "account_holder_name": (
        co.inputs.given_name.value + " " + co.inputs.family_name.value),
    "account_holder_type": "individual"});
  promise.then(function(result) {
    if (result.error != null) {
      cp.displayMessage("Stripe didn't accept your bank account info.");
    } else {
      co.submitDirDepInfo(result.token);
    }
  });
};


co.buttons.submit_info.addEventListener(
    "click", co.getStripeTokenAndSubmitDirDep);


/* ------------------------------------------------------------------------- *
 * Submitting personal ID number.                                            *
 * ------------------------------------------------------------------------- */

co.submitPersonalIdNumber = function() {
  if (co.valid.full_ssn == true) {
    cp.ajaxBlocking(
        "submit_personal_id",
        [["pid", co.inputs.full_ssn.value]],
        co.checkSetupDone);
  } else {
    cp.displayMessage("That's not a valid Social Security number.");
  }
};


 co.buttons.submit_full_ssn.addEventListener(
    "click", co.submitPersonalIdNumber);


/* ------------------------------------------------------------------------- *
 * Submitting photo ID document.                                             *
 * ------------------------------------------------------------------------- */


co.submitIdDocument = function() {
  var doc = co.inputs.id_document.files[0],
    reader = new FileReader();
  if (!co.isdefined(doc)) {
    cp.displayMessage("No document selected!");
    return;
  }
  if (doc.type != "image/jpeg") {
    cp.displayMessage("Document must be an image in .jpg format!");
    return;
  }
  if (doc.size > (250 * 1000)) {
    cp.displayMessage("File too large! Max size is 250 KB.");
    return;
  }
  reader.onload = function() {
    cp.ajaxBlocking(
        "submit_id_document",
        [["datauri", reader.result]],
        co.checkSetupDone);
  };
  reader.readAsDataURL(doc);
};


co.buttons.submit_id_document.addEventListener(
    "click", function() {cp.showDash()});


/* ------------------------------------------------------------------------- *
 * Withdrawals.                                                              *
 * ------------------------------------------------------------------------- */

co.submitWithdrawBalance = function() {
  cp.ajaxBlocking(
      "submit_withdraw_balance", [],
      function(resp) {
        if (resp.success == true) {
          cp.displayMessage(
              "Funds will appear in your account within 2 business days.",
              true)
          cp.showDash();
        } else {
          cp.displayMessage("Unable to process withdrawal request.");
        }
      });
};


co.buttons.back.addEventListener("click", cp.showDash);


co.buttons.withdraw.addEventListener("click", co.submitWithdrawBalance);
