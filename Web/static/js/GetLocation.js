
const ws = new WebSocket('ws://localhost:5000');
var circle = L.circle();
var layerGroup = L.layerGroup().addTo(map);ws.onopen = (event) => {
    ws.send(JSON.stringify({ source: "website" }));
    console.log("WebSocket connection established.");
}
ws.onmessage = (event) => {
    layerGroup.clearLayers();
    jsonObj = JSON.parse(event.data)
    map.setView([jsonObj.client.Long,jsonObj.client.Lat], 13);
    L.marker([jsonObj.client.Long, jsonObj.client.Lat]).addTo(map)
        .bindPopup("Client")
        .openPopup().addTo(layerGroup);   
    console.log(jsonObj);
    map.removeLayer(circle);
    jsonObj.stations.forEach(stations => {
        L.marker([stations.Long, stations.Lat]).addTo(layerGroup)
            .bindPopup(stations.Name);
        L.circle([stations.Long, stations.Lat], { radius: Math.abs(stations.radius) }).addTo(layerGroup);
    });
    
    // const coords = event.data.split(",");
    // circle = new L.circle([Number.parseFloat(coords[0]),Number.parseFloat(coords[1])], {radius: 5});
    // map.addLayer(circle);
    // console.log('Longitude:' + coords[0] + " | Latitude: " + coords[1]);
};