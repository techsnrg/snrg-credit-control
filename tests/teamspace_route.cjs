/* The alias must not alter native document routes or create extra history entries. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const source = fs.readFileSync('snrg_credit_control/public/js/teamspace_route.js', 'utf8');
const writes = [];
const location = {pathname:'/teamspace', search:'?customer=C1', hash:'#note'};
const router = {
  current_route:['customer-workspace'], current_shell:'Credit Control',
  get_sub_path_string(route) {return (route || location.pathname).replace(/^\/desk\//, '');},
  path_on_screen() {return location.pathname;},
  write_shell_into_url() {writes.push('native');return 'native';}
};
const context = {window:{frappe:{router}, location}, history:{state:null, replaceState(state, title, url) {writes.push(url);}}};
vm.runInNewContext(source, context);
assert.equal(router.get_sub_path_string(), 'customer-workspace');
assert.equal(router.get_sub_path_string('/teamspace/'), 'customer-workspace');
assert.equal(router.path_on_screen(), '/desk/customer-workspace');
router.write_shell_into_url();
assert.deepEqual(writes, []);
assert.equal(router.current_shell, null);
location.pathname='/desk/credit-control/customer-workspace';
router.write_shell_into_url();
assert.equal(writes.pop(), '/teamspace?customer=C1#note');
location.pathname='/desk/selling/customer/C1';router.current_route=['Form','Customer','C1'];
assert.equal(router.get_sub_path_string(), 'selling/customer/C1');
assert.equal(router.path_on_screen(), '/desk/selling/customer/C1');
assert.equal(router.write_shell_into_url(), 'native');
assert.equal(writes.pop(), 'native');
const installed = router.get_sub_path_string;
vm.runInNewContext(source, context);
assert.equal(router.get_sub_path_string, installed);
console.log('PASS: short route, old bookmarks, query/hash preservation, native navigation and idempotent setup');
