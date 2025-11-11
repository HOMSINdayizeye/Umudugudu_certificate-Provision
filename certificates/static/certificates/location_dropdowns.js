// Province → District
document.getElementById('id_province').addEventListener('change', function () {
    const province = this.value;

    clearDropdowns(['id_district', 'id_sector', 'id_cell', 'id_village']);
    if (!province) return;

    fetch(`/get-districts/?province=${province}`)
        .then(res => res.json())
        .then(data => populateDropdown('id_district', data.districts))
        .catch(err => console.error('Error loading districts:', err));
});

// District → Sector
document.getElementById('id_district').addEventListener('change', function () {
    const province = document.getElementById('id_province').value;
    const district = this.value;

    clearDropdowns(['id_sector', 'id_cell', 'id_village']);
    if (!district) return;

    fetch(`/get-sectors/?province=${province}&district=${district}`)
        .then(res => res.json())
        .then(data => populateDropdown('id_sector', data.sectors))
        .catch(err => console.error('Error loading sectors:', err));
});

// Sector → Cell
document.getElementById('id_sector').addEventListener('change', function () {
    const province = document.getElementById('id_province').value;
    const district = document.getElementById('id_district').value;
    const sector = this.value;

    clearDropdowns(['id_cell', 'id_village']);
    if (!sector) return;

    fetch(`/get-cells/?province=${province}&district=${district}&sector=${sector}`)
        .then(res => res.json())
        .then(data => populateDropdown('id_cell', data.cells))
        .catch(err => console.error('Error loading cells:', err));
});

// Cell → Village
document.getElementById('id_cell').addEventListener('change', function () {
    const province = document.getElementById('id_province').value;
    const district = document.getElementById('id_district').value;
    const sector = document.getElementById('id_sector').value;
    const cell = this.value;

    clearDropdowns(['id_village']);
    if (!cell) return;

    fetch(`/get-villages/?province=${province}&district=${district}&sector=${sector}&cell=${cell}`)
        .then(res => res.json())
        .then(data => populateDropdown('id_village', data.villages))
        .catch(err => console.error('Error loading villages:', err));
});

// Helpers
function populateDropdown(id, items) {
    const select = document.getElementById(id);
    select.innerHTML = '<option value="">--- Select ---</option>';
    items.forEach(item => {
        const option = document.createElement('option');
        option.value = item;
        option.textContent = item;
        select.appendChild(option);
    });
}

function clearDropdowns(ids) {
    ids.forEach(id => {
        const select = document.getElementById(id);
        if (select) {
            select.innerHTML = '<option value="">--- Select ---</option>';
        }
    });
}
