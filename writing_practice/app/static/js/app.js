// Progressive enhancement only. Every sample below is also rendered server-side,
// so the page still works with JavaScript off -- the samples just stop updating.
(function () {
  "use strict";

  var form = document.querySelector("form.worksheet");
  var textarea = document.getElementById("text");
  var counter = document.getElementById("char-count");
  var live = document.getElementById("live-preview");
  var samples = Array.prototype.slice.call(document.querySelectorAll(".sample"));

  function updateCount() {
    if (textarea && counter) {
      counter.textContent = textarea.value.length.toLocaleString();
    }
  }

  // The first couple of non-empty lines are all a preview needs, and it keeps the
  // sample URL short even when the textarea holds 5,000 characters.
  function previewText() {
    if (!textarea) return "";
    return textarea.value
      .split("\n")
      .filter(function (line) { return line.trim(); })
      .slice(0, 2)
      .join("\n")
      .slice(0, 200);
  }

  function formParams() {
    var params = new URLSearchParams();
    if (!form) return params;
    new FormData(form).forEach(function (value, key) {
      if (key === "text") return;
      params.append(key, value);
    });
    return params;
  }

  function refresh(img, params) {
    var overrides = {};
    try {
      overrides = JSON.parse(img.dataset.override || "{}");
    } catch (error) {
      overrides = {};
    }
    var local = new URLSearchParams(params.toString());
    Object.keys(overrides).forEach(function (key) {
      var value = overrides[key];
      if (value === false) local.delete(key);
      else local.set(key, value === true ? "on" : value);
    });
    local.set("rows", img.dataset.rows || "1");
    local.set("w", img.dataset.w || "210");
    var text = img.dataset.text || previewText();
    if (text) local.set("text", text);
    img.src = img.dataset.base + "?" + local.toString();
  }

  function refreshAll() {
    var params = formParams();
    samples.forEach(function (img) { refresh(img, params); });
    if (live) {
      live.dataset.rows = params.get("rows_per_block") || "3";
      refresh(live, params);
    }
  }

  var pending;
  function scheduleRefresh() {
    window.clearTimeout(pending);
    pending = window.setTimeout(refreshAll, 300);
  }

  function markSelected() {
    document.querySelectorAll(".option-card").forEach(function (card) {
      var input = card.querySelector("input");
      card.classList.toggle("is-selected", !!(input && input.checked));
    });
  }

  if (textarea) {
    textarea.addEventListener("input", function () {
      updateCount();
      scheduleRefresh();
    });
    updateCount();
  }

  document.querySelectorAll(".chip").forEach(function (chip) {
    chip.addEventListener("click", function () {
      if (!textarea) return;
      textarea.value = chip.dataset.text || "";
      updateCount();
      scheduleRefresh();
      textarea.focus();
    });
  });

  document.querySelectorAll('input[type="range"][data-output]').forEach(function (range) {
    var output = document.getElementById(range.dataset.output);
    function sync() {
      if (output) output.textContent = range.value + "%";
    }
    range.addEventListener("input", sync);
    sync();
  });

  // Each letter style is controlled by a different knob: thickness for the
  // stroked styles, spacing and double/single trace marks for the broken ones,
  // solid layer/weight for solid. Hide (rather than disable) the irrelevant
  // ones so their values round-trip.
  var thicknessField = document.getElementById("letter-thickness-field");
  var spacingField = document.getElementById("trace-spacing-field");
  var traceLayersField = document.getElementById("trace-layers-field");
  var layersField = document.getElementById("solid-layers-field");
  var weightField = document.getElementById("solid-weight-field");

  function styleMatches(val) {
    var checked = document.querySelector('input[name="letters"]:checked');
    return (checked ? checked.value : "dashed") === val;
  }

  function syncStyleFields() {
    if (thicknessField) thicknessField.hidden = !styleMatches("dashed") && !styleMatches("dotted") && !styleMatches("outlined");
    if (spacingField) spacingField.hidden = !styleMatches("dashed") && !styleMatches("dotted");
    if (traceLayersField) traceLayersField.hidden = !styleMatches("dashed") && !styleMatches("dotted");
    if (layersField) layersField.hidden = !styleMatches("solid");
    if (weightField) {
      var layers = document.getElementById("solid_layers");
      weightField.hidden = !styleMatches("solid") || (layers && layers.value !== "double");
    }
  }

  if (form) {
    form.addEventListener("change", function () {
      syncStyleFields();
      markSelected();
      scheduleRefresh();
    });
    form.addEventListener("input", function (event) {
      if (event.target.type === "range") scheduleRefresh();
    });
  }

  syncStyleFields();
  markSelected();
})();
