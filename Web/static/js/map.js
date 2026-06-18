// function caller() {
//   return sendGETRequest();
// }



const map = L.map('map').setView([39.6769511,-104.9596142], 26);
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '&copy; OpenStreetMap contributors'
}).addTo(map);

// sendGETRequest().then(result => {
//     for (const element of result) {
//         console.log(element)
//         L.marker([element[1], element[2]]).addTo(map)
//             .bindPopup(element[0])
//             .openPopup();
//     }
// });


