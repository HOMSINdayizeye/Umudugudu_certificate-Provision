// location_code.js
function fetchLocationCode() {
    const province = document.getElementById('province').value;
    const district = document.getElementById('district').value;
    const sector = document.getElementById('sector').value;
    const cell = document.getElementById('cell').value;
    const village = document.getElementById('village').value;

    fetch(`/get-location-code/?province=${province}&district=${district}&sector=${sector}&cell=${cell}&village=${village}`)
        .then(response => response.json())
        .then(data => {
            document.getElementById('location-code-display').innerText = data.code || 'Not found';
        });
}
