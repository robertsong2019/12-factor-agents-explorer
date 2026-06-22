import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detectLicense, formatLicenseInfo } from '../context-forge.mjs';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import { join } from 'node:path';
import { tmpdir } from 'node:os';

const TEST_DIR = join(tmpdir(), 'cf-f30-test-' + Date.now());

async function setup(files) {
  await mkdir(TEST_DIR, { recursive: true });
  for (const [path, content] of Object.entries(files)) {
    const full = join(TEST_DIR, path);
    await mkdir(join(full, '..'), { recursive: true });
    await writeFile(full, content);
  }
}

async function cleanup() {
  await rm(TEST_DIR, { recursive: true, force: true });
}

test('F30: detectLicense from package.json string', async () => {
  await setup({
    'package.json': JSON.stringify({ name: 'test', license: 'MIT' }),
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'MIT');
    assert.equal(result.source, 'package.json');
    assert.equal(result.confidence, 'high');
  } finally { await cleanup(); }
});

test('F30: detectLicense from package.json object form', async () => {
  await setup({
    'package.json': JSON.stringify({ name: 'test', license: { type: 'Apache-2.0', url: '...' } }),
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'Apache-2.0');
    assert.equal(result.source, 'package.json');
  } finally { await cleanup(); }
});

test('F30: detectLicense from pyproject.toml', async () => {
  await setup({
    'pyproject.toml': `[project]\nname = "myproj"\nlicense = "MIT"\n`,
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'MIT');
    assert.equal(result.source, 'pyproject.toml');
    assert.equal(result.confidence, 'high');
  } finally { await cleanup(); }
});

test('F30: detectLicense from Cargo.toml', async () => {
  await setup({
    'Cargo.toml': `[package]\nname = "myapp"\nlicense = "MIT OR Apache-2.0"\n`,
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'MIT OR Apache-2.0');
    assert.equal(result.source, 'Cargo.toml');
  } finally { await cleanup(); }
});

test('F30: detectLicense from LICENSE file content - MIT', async () => {
  await setup({
    'LICENSE': `The MIT License (MIT)\n\nPermission is hereby granted, free of charge, to any person obtaining a copy\nof this software and associated documentation files...\n`,
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'MIT');
    assert.equal(result.file, 'LICENSE');
    assert.equal(result.confidence, 'high');
  } finally { await cleanup(); }
});

test('F30: detectLicense from LICENSE file content - Apache', async () => {
  await setup({
    'LICENSE': `Apache License, Version 2.0\n\nLicensed under the Apache License, Version 2.0...\n`,
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'Apache-2.0');
    assert.equal(result.file, 'LICENSE');
  } finally { await cleanup(); }
});

test('F30: detectLicense from BSD-3-Clause file', async () => {
  await setup({
    'LICENSE': `Redistribution and use in source and binary forms, with or without modification,\nare permitted provided that the following conditions are met:\n\nNeither the name of the copyright holder nor the names of its contributors may be used\nto endorse or promote products derived from this software without specific prior written permission.\n`,
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'BSD-3-Clause');
  } finally { await cleanup(); }
});

test('F30: detectLicense from COPYING file', async () => {
  await setup({
    'COPYING': `GNU GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007\n`,
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'GPL-3.0');
    assert.equal(result.file, 'COPYING');
  } finally { await cleanup(); }
});

test('F30: package.json takes priority over LICENSE file', async () => {
  await setup({
    'package.json': JSON.stringify({ license: 'ISC' }),
    'LICENSE': 'The MIT License (MIT)\nPermission is hereby granted, free of charge...',
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'ISC');
    assert.equal(result.source, 'package.json');
  } finally { await cleanup(); }
});

test('F30: detects Unlicense', async () => {
  await setup({
    'LICENSE': `This is free and unencumbered software released into the public domain.\n\nAnyone is free to copy, modify, publish, use...\n`,
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'Unlicense');
  } finally { await cleanup(); }
});

test('F30: detects MPL-2.0', async () => {
  await setup({
    'LICENSE': `Mozilla Public License, Version 2.0\n`,
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'MPL-2.0');
  } finally { await cleanup(); }
});

test('F30: returns none confidence when no license found', async () => {
  await setup({
    'app.js': 'const x = 1;',
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.confidence, 'none');
    assert.equal(result.id, null);
  } finally { await cleanup(); }
});

test('F30: LICENSE file exists but unrecognized pattern gives low confidence', async () => {
  await setup({
    'LICENSE': 'Some custom license that does not match any known pattern.\n',
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.confidence, 'low');
    assert.equal(result.file, 'LICENSE');
    assert.equal(result.id, null);
  } finally { await cleanup(); }
});

test('F30: detectLicense from README mention', async () => {
  await setup({
    'README.md': '# My Project\n\nSome description.\n\nLicense: BSD-3-Clause\n',
  });
  try {
    const result = await detectLicense(TEST_DIR);
    assert.equal(result.id, 'BSD-3-Clause');
    assert.equal(result.source, 'README.md');
    assert.equal(result.confidence, 'low');
  } finally { await cleanup(); }
});

test('F30: formatLicenseInfo produces output', () => {
  const report = formatLicenseInfo({ id: 'MIT', source: 'package.json', file: null, confidence: 'high' });
  assert.ok(report.includes('### License'));
  assert.ok(report.includes('MIT'));
  assert.ok(report.includes('🟢'));
  assert.ok(report.includes('package.json'));
});

test('F30: formatLicenseInfo handles no license', () => {
  const report = formatLicenseInfo({ confidence: 'none' });
  assert.ok(report.includes('No license'));
  assert.ok(report.includes('⚠️'));
});

test('F30: formatLicenseInfo shows file when present', () => {
  const report = formatLicenseInfo({ id: 'Apache-2.0', source: 'LICENSE', file: 'LICENSE', confidence: 'high' });
  assert.ok(report.includes('`LICENSE`'));
});
