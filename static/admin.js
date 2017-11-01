/* ------------------------------------------------------------------------- *
 * Namespace everything to prevent conflicts!                                *
 * ------------------------------------------------------------------------- */

 var dm = {};


 dm.createEmployee = function(digits) {
  cp.ajaxBlocking("admin_create_employee", [["digits", String(digits)]]);
 };
 