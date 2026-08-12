/* Narrow the feed from a query string.
 *
 * The feed's HTML already contains every published story. This script only hides
 * the items that do not match, so with JavaScript unavailable the page is simply
 * the complete collection — never empty, never broken (FR-011b). Filtering is a
 * convenience; it is never the only route to a story (FR-021b).
 */
(function () {
  "use strict";

  var FILTERS = ["character", "location"];

  function readFilter() {
    var params = new URLSearchParams(window.location.search);
    for (var i = 0; i < FILTERS.length; i++) {
      var value = params.get(FILTERS[i]);
      if (value) {
        return { kind: FILTERS[i], slug: value.trim() };
      }
    }
    return null;
  }

  function slugsOf(item, kind) {
    var raw = item.getAttribute("data-" + kind + "s") || "";
    return raw.split(/\s+/).filter(Boolean);
  }

  function labelFor(item, filter) {
    /* Prefer a human-readable label, but the slug is an honest fallback. */
    return filter.slug.replace(/-/g, " ");
  }

  function apply() {
    var filter = readFilter();
    var items = Array.prototype.slice.call(
      document.querySelectorAll("#feed .feed-item")
    );
    var banner = document.getElementById("feed-filter-banner");
    var label = document.getElementById("feed-filter-label");
    var empty = document.getElementById("feed-filter-empty");

    if (!filter) {
      items.forEach(function (item) {
        item.hidden = false;
      });
      if (banner) banner.hidden = true;
      if (empty) empty.hidden = true;
      return;
    }

    var matched = 0;
    items.forEach(function (item) {
      var match = slugsOf(item, filter.kind).indexOf(filter.slug) !== -1;
      item.hidden = !match;
      if (match) matched++;
    });

    if (banner && label) {
      label.textContent = labelFor(items[0], filter);
      banner.hidden = false;
    }
    if (empty) empty.hidden = matched !== 0;
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", apply);
  } else {
    apply();
  }

  /* Clearing the filter returns the full collection without leaving the page. */
  document.addEventListener("click", function (event) {
    var target = event.target;
    if (target && target.id === "feed-filter-clear") {
      event.preventDefault();
      window.history.pushState({}, "", window.location.pathname);
      apply();
    }
  });

  window.addEventListener("popstate", apply);
})();
