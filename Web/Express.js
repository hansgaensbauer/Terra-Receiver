const express = require('express');
const cors = require('cors');
const app = express();
const PORT = 5000;
const fs = require("fs");
const http = require('http');
const WebSocket = require('ws');
const server = http.createServer(app); // single HTTP server
const wss = new WebSocket.Server({ server }); // attach WS to same server
app.use(cors());

app.set('view engine', 'ejs');


app.use(express.static('static'));
app.use(express.urlencoded({ extended: true }));

app.get('/', (req, res) => {
  res.render('index');
});
app.get("/:region/:timestamp", async (req, res) => {
  const response = await fetch(`http://127.0.0.1:8080/localstations/?region=${req.params.region}&time=${req.params.timestamp}`);
  const data = await response.json();
  res.json(data);
});
const connection = new Set()
wss.on('connection', (ws, req) => {
    ws.on('message', (data) => {
      let jsonobject = JSON.parse(data);
      if(jsonobject.source == "website"){
        console.log("Website connected.");
        connection.add(ws);
      }else{
        console.log(jsonobject);
        connection?.forEach(s => s.send(JSON.stringify(JSON.parse(data)))); 
      }
    });

    ws.on('close', () => {
        console.log(`Device disconnected.`);
    });
});

server.listen(PORT, () => {
  console.log(`Server running on http://localhost:${PORT}`);
});

