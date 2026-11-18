/* Keep the Teamspace alias in the address bar, including refresh/back navigation.
 * Native Desk routing is unchanged for every other page and document.
 */
(() => {
  const router = window.frappe?.router;
  if (!router || router.teamspace_alias_installed) return;
  router.teamspace_alias_installed = true;
  const subpath = router.get_sub_path_string;
  const onScreen = router.path_on_screen;
  const writeShell = router.write_shell_into_url;
  const isAlias = path => /^\/teamspace\/?$/.test(path || window.location.pathname);
  router.get_sub_path_string = function (route) {
    return isAlias(route) ? 'customer-workspace' : subpath.call(this, route);
  };
  router.path_on_screen = function () {
    return isAlias() ? '/desk/customer-workspace' : onScreen.call(this);
  };
  if (writeShell) router.write_shell_into_url = function () {
    if (this.current_route?.[0] === 'customer-workspace') {
      this.current_shell = null;
      if (!isAlias()) history.replaceState(history.state, '', '/teamspace' + window.location.search + window.location.hash);
      return;
    }
    return writeShell.call(this);
  };
})();
