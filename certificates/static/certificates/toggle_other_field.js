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
document.getElementById('id_province').addEventListener('change', function () {
    const province = this.value;

    // Clear dependent dropdowns
    ['id_district', 'id_sector', 'id_cell', 'id_village'].forEach(id => {
        const select = document.getElementById(id);
        select.innerHTML = '<option value="">--- Select ---</option>';
    });

    if (!province) return;

    fetch(`/get-districts/?province=${province}`)
        .then(res => res.json())
        .then(data => {
            const districtSelect = document.getElementById('id_district');
            districtSelect.innerHTML = '<option value="">--- Select District ---</option>';
            data.districts.forEach(d => {
                const option = document.createElement('option');
                option.value = d;
                option.textContent = d;
                districtSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error fetching districts:', error);
        });
});
