async function main() {
  try {
    console.log('Fetching 127.0.0.1...');
    const r1 = await fetch('http://127.0.0.1:9222/json/list');
    console.log('127.0.0.1 success:', r1.status);
    const j1 = await r1.json();
    console.log('127.0.0.1 count:', j1.length);
  } catch (err) {
    console.error('127.0.0.1 failed:', err.message);
  }

  try {
    console.log('Fetching localhost...');
    const r2 = await fetch('http://localhost:9222/json/list');
    console.log('localhost success:', r2.status);
    const j2 = await r2.json();
    console.log('localhost count:', j2.length);
  } catch (err) {
    console.error('localhost failed:', err.message);
  }
}
main();
