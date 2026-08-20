import { spawn } from 'child_process';
const args = process.argv.slice(2).length ? process.argv.slice(2) : ['test/afm.test.js'];
const p = spawn('node', args, { stdio: 'inherit', cwd: new URL('.', import.meta.url).pathname });
p.on('exit', (c) => process.exit(c ?? 1));
