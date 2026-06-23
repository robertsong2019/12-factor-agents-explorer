import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { detectSecrets, formatSecretReport } from '../context-forge.mjs';

describe('detectSecrets', () => {
  let tmpDir;

  async function setup() {
    tmpDir = await mkdtemp(join(tmpdir(), 'ctx-secret-'));
  }

  async function cleanup() {
    await rm(tmpDir, { recursive: true, force: true });
  }

  it('detects AWS access key ID', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'app.js'), 'const key = "AKIAIOSFODNN7EXAMPLE";\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.length > 0);
      assert.ok(results.some(r => r.type === 'aws_access_key' && r.risk === 'high'));
    } finally { await cleanup(); }
  });

  it('detects GitHub token', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'config.ts'), 'const token = ghp_1234567890abcdefghijklmnopqrstuvwxyz;\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.type === 'github_token' && r.risk === 'high'));
    } finally { await cleanup(); }
  });

  it('detects private key block', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'key.pem'), '-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA...\n-----END RSA PRIVATE KEY-----\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.type === 'private_key' && r.risk === 'high'));
    } finally { await cleanup(); }
  });

  it('detects JWT token', async () => {
    await setup();
    try {
      const jwt = 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIn0.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c';
      await writeFile(join(tmpDir, 'auth.js'), `const token = "${jwt}";\n`);
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.type === 'jwt_token' && r.risk === 'high'));
    } finally { await cleanup(); }
  });

  it('detects database URL with credentials', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'db.js'), 'const url = "mongodb://user:secretpass@localhost:27017/db";\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.type === 'db_url'));
    } finally { await cleanup(); }
  });

  it('detects password assignment (medium risk)', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'auth.py'), 'password = "supersecret123"\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.type === 'password' && r.risk === 'medium'));
    } finally { await cleanup(); }
  });

  it('detects token assignment (medium risk)', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'api.ts'), 'const authToken = "abcdef1234567890abcd";\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.risk === 'medium'));
    } finally { await cleanup(); }
  });

  it('detects Slack token', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'bot.js'), 'const slack = "xoxb-1234567890-1234567890123";\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.type === 'slack_token' && r.risk === 'high'));
    } finally { await cleanup(); }
  });

  it('detects Stripe key', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'payment.js'), 'const key = "sk_live_abcdef1234567890abcdef";\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.type === 'stripe_key' && r.risk === 'high'));
    } finally { await cleanup(); }
  });

  it('detects process.env reference (low risk)', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'config.js'), 'const apiKey = process.env.API_KEY;\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.type === 'env_reference' && r.risk === 'low'));
    } finally { await cleanup(); }
  });

  it('detects .env file secret key (low risk)', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, '.env'), 'DATABASE_PASSWORD=mypassword\n');
      const results = await detectSecrets(tmpDir);
      assert.ok(results.some(r => r.type === 'dotenv_key' && r.risk === 'low'));
    } finally { await cleanup(); }
  });

  it('returns empty array for clean codebase', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'clean.js'), 'const x = 1 + 2;\nconsole.log(x);\n');
      const results = await detectSecrets(tmpDir);
      assert.equal(results.length, 0);
    } finally { await cleanup(); }
  });

  it('respects maxDepth parameter', async () => {
    await setup();
    try {
      await mkdir(join(tmpDir, 'a', 'b', 'c'), { recursive: true });
      await writeFile(join(tmpDir, 'a', 'b', 'c', 'deep.js'), 'const key = "AKIAIOSFODNN7EXAMPLE";\n');
      const shallow = await detectSecrets(tmpDir, 2);
      const deep = await detectSecrets(tmpDir, 5);
      assert.equal(shallow.length, 0);
      assert.ok(deep.length > 0);
    } finally { await cleanup(); }
  });

  it('skips node_modules and .git', async () => {
    await setup();
    try {
      await mkdir(join(tmpDir, 'node_modules'), { recursive: true });
      await writeFile(join(tmpDir, 'node_modules', 'lib.js'), 'const key = "AKIAIOSFODNN7EXAMPLE";\n');
      const results = await detectSecrets(tmpDir);
      assert.equal(results.length, 0);
    } finally { await cleanup(); }
  });

  it('deduplicates findings from same line', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'multi.js'), 'const a = "AKIAIOSFODNN7EXAMPLE"; const b = process.env.API_KEY;\n');
      const results = await detectSecrets(tmpDir);
      // Same line can have multiple types, but no exact duplicates
      const keys = results.map(r => `${r.line}:${r.type}`);
      const unique = new Set(keys);
      assert.equal(keys.length, unique.size);
    } finally { await cleanup(); }
  });

  it('sorts by risk level (high first)', async () => {
    await setup();
    try {
      await writeFile(join(tmpDir, 'mixed.js'), [
        'const env = process.env.SECRET_KEY;',
        'const aws = "AKIAIOSFODNN7EXAMPLE";',
      ].join('\n'));
      const results = await detectSecrets(tmpDir);
      const highIdx = results.findIndex(r => r.risk === 'high');
      const lowIdx = results.findIndex(r => r.risk === 'low');
      assert.ok(highIdx >= 0 && lowIdx >= 0);
      assert.ok(highIdx < lowIdx, 'high risk should come before low risk');
    } finally { await cleanup(); }
  });
});

describe('formatSecretReport', () => {
  it('returns clean message for empty findings', () => {
    const report = formatSecretReport([]);
    assert.match(report, /No potential secrets detected/);
    assert.match(report, /✅/);
  });

  it('includes summary counts', () => {
    const findings = [
      { file: 'a.js', line: 1, type: 'aws_access_key', risk: 'high', description: 'AWS Access Key', snippet: 'const k = "AKIA..."' },
      { file: 'b.js', line: 2, type: 'password', risk: 'medium', description: 'Password', snippet: 'pw = "secret"' },
      { file: 'c.js', line: 3, type: 'env_reference', risk: 'low', description: 'Env Ref', snippet: 'env.KEY' },
    ];
    const report = formatSecretReport(findings);
    assert.match(report, /3.*potential secret/);
    assert.match(report, /1 high/);
    assert.match(report, /1 medium/);
    assert.match(report, /1 low/);
  });

  it('includes warning for high-risk findings', () => {
    const findings = [
      { file: 'a.js', line: 1, type: 'aws_access_key', risk: 'high', description: 'AWS Access Key', snippet: 'const k = "AKIA..."' },
    ];
    const report = formatSecretReport(findings);
    assert.match(report, /Action required/i);
    assert.match(report, /Rotate/i);
  });

  it('no warning when only low-risk findings', () => {
    const findings = [
      { file: 'a.js', line: 1, type: 'env_reference', risk: 'low', description: 'Env Ref', snippet: 'env.KEY' },
    ];
    const report = formatSecretReport(findings);
    assert.doesNotMatch(report, /Action required/i);
  });

  it('formats file:line with snippet', () => {
    const findings = [
      { file: 'src/config.js', line: 42, type: 'api_key', risk: 'high', description: 'API Key', snippet: 'const key = "abc123"' },
    ];
    const report = formatSecretReport(findings);
    assert.match(report, /src\/config\.js:42/);
    assert.match(report, /const key/);
  });
});


