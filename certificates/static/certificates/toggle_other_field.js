document.addEventListener("DOMContentLoaded", function () {
  const certSelect = document.getElementById("id_cert_type");
  const otherField = document.getElementById("other-description");

  function toggleOtherField() {
    const selectedText = certSelect.options[certSelect.selectedIndex].text.toLowerCase();
    otherField.style.display = selectedText === "other" ? "block" : "none";
  }

  certSelect.addEventListener("change", toggleOtherField);
  toggleOtherField(); // Run on page load
});
