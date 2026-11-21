// 通过 Chrome DevTools Protocol 在设备页面上执行一段 JS
// 用法: node cdp.js <ws-url> "<expression>"
const url = process.argv[2];
const expr = process.argv[3];
const ws = new WebSocket(url);
const timer = setTimeout(function () {
  console.log('TIMEOUT');
  process.exit(2);
}, 15000);

ws.onopen = function () {
  ws.send(JSON.stringify({
    id: 1,
    method: 'Runtime.evaluate',
    params: { expression: expr, returnByValue: true, awaitPromise: true }
  }));
};

ws.onmessage = function (e) {
  const m = JSON.parse(e.data);
  if (m.id !== 1) return;
  clearTimeout(timer);
  if (m.result && m.result.exceptionDetails) {
    console.log('EXC ' + JSON.stringify(m.result.exceptionDetails.exception));
  } else {
    console.log(JSON.stringify(m.result && m.result.result ? m.result.result.value : m.result));
  }
  ws.close();
};

ws.onerror = function (e) {
  console.log('WSERR ' + (e && e.message));
};
