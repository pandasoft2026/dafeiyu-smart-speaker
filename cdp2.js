const url = process.argv[2], expr = process.argv[3];
const ws = new WebSocket(url);
ws.onopen = () => { console.log('OPEN'); ws.send(JSON.stringify({id:1,method:'Runtime.evaluate',params:{expression:expr,returnByValue:true}})); };
ws.onmessage = (e) => { console.log('MSG ' + String(e.data).slice(0,500)); };
ws.onerror = (e) => console.log('ERR ' + JSON.stringify(e && e.message || e));
ws.onclose = (e) => console.log('CLOSE ' + e.code);
setTimeout(()=>process.exit(0), 6000);
