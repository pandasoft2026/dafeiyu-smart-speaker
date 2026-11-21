// 打印 CDP 原始返回，方便排查
const url = process.argv[2], expr = process.argv[3];
const ws = new WebSocket(url);
const t = setTimeout(() => { console.log('TIMEOUT'); process.exit(2); }, 10000);
ws.onopen = () => {
  ws.send(JSON.stringify({
    id: 1, method: 'Runtime.evaluate',
    params: { expression: expr, returnByValue: true, awaitPromise: false }
  }));
};
ws.onmessage = (e) => {
  console.log('RAW ' + String(e.data).slice(0, 600));
  clearTimeout(t);
  ws.close();
  setTimeout(() => process.exit(0), 200);
};
ws.onerror = (e) => console.log('WSERR ' + (e && e.message));
ws.onclose = (e) => console.log('CLOSE ' + e.code);
