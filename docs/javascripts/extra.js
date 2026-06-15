/* Site enhancements. Re-runs on every page load, including Material's
 * instant navigation (document$ re-emits per page). */
(function () {
  function enhance() {
    /* Compatibility-matrix fold: the toggle row reveals/hides the
     * alphabetical tbody.matrix-others (hidden at render time). */
    document.querySelectorAll(".harness-matrix").forEach(function (table) {
      var others = table.querySelector(".matrix-others");
      var button = table.querySelector(".matrix-toggle button");
      if (!others || !button || button.dataset.bound) return;
      button.dataset.bound = "1";
      button.addEventListener("click", function () {
        var hidden = others.toggleAttribute("hidden");
        button.textContent = hidden ? button.dataset.show : button.dataset.hide;
      });
    });
  }

  if (window.document$) {
    window.document$.subscribe(enhance);
  } else {
    document.addEventListener("DOMContentLoaded", enhance);
  }
})();
