import { test } from 'node:test';
import assert from 'node:assert/strict';
import { inferTechStack, formatTechStack } from '../context-forge.mjs';

test('F21: inferTechStack — detects React', () => {
  const info = { dependencies: { react: '^18.0.0', 'react-dom': '^18.0.0' } };
  const langs = new Map([['.jsx', 10], ['.js', 5]]);
  // scanLanguages returns [ext, languageName], but here we pass a map of ext→name
  // Actually langs is Map<ext, count> from scanLanguages... let me check
  // Actually looking at the code, langs is Map<ext_string, count_number>
  // But inferTechStack uses langs.values() and checks .includes(l) where l is from STACK_SIGNATURES.lang
  // The values of the langs map would be counts, not language names...
  // Let me re-check scanLanguages
  const langNames = new Map([['JavaScript (React)', 10], ['JavaScript', 5]]);
  // Wait, scanLanguages returns entries like ['.js', 'JavaScript'] ... no
  // Let me look at the code again. It returns a Map of language_name -> count
  // Actually: const lang = LANGUAGE_MAP[ext]; langs.set(lang, (langs.get(lang)||0)+1)
  // So langs keys ARE language names, values are counts.
  // But [...langs.values()] gives counts, not names. We need keys.
  // The inferTechStack code does [...langs.values()].flatMap(l => [l, l.split(' ')[0]])
  // That's wrong - it should be [...langs.keys()]
  // Let me fix this in the implementation...
  const stack = inferTechStack(info, langNames, { allImports: ['react'] }, {});

  const react = stack.stack.find(s => s.name === 'react');
  assert.ok(react, 'Should detect React');
  assert.equal(react.category, 'Frontend');
  assert.ok(react.confidence > 0);
});

test('F21: inferTechStack — detects Express backend', () => {
  const info = { dependencies: { express: '^4.18.0' } };
  const langs = new Map([['JavaScript (ESM)', 20]]);
  const stack = inferTechStack(info, langs, { allImports: ['express'] }, {});

  const express = stack.stack.find(s => s.name === 'express');
  assert.ok(express, 'Should detect Express');
  assert.equal(express.category, 'Backend');
});

test('F21: inferTechStack — detects multiple frameworks', () => {
  const info = {
    dependencies: { react: '^18.0.0', 'react-dom': '^18.0.0', express: '^4.18.0', vite: '^5.0.0' },
    devDependencies: { jest: '^29.0.0' },
  };
  const langs = new Map([['JavaScript (React)', 15], ['TypeScript', 5]]);
  const stack = inferTechStack(info, langs, { allImports: ['react', 'express', 'vite'] }, {});

  const names = stack.stack.map(s => s.name);
  assert.ok(names.includes('react'));
  assert.ok(names.includes('express'));
  assert.ok(names.includes('vite'));
  assert.ok(names.includes('jest'));
});

test('F21: inferTechStack — groups by category', () => {
  const info = { dependencies: { react: '^18.0.0', tailwindcss: '^3.0.0' } };
  const langs = new Map([['JavaScript (React)', 10]]);
  const stack = inferTechStack(info, langs, { allImports: ['react'] }, {});

  assert.ok(stack.byCategory.Frontend);
  assert.ok(stack.byCategory.Styling);
});

test('F21: inferTechStack — detects Python frameworks', () => {
  const info = { dependencies: {} };
  const langs = new Map([['Python', 30]]);
  const stack = inferTechStack(info, langs, { allImports: ['fastapi', 'sqlalchemy'] }, {});

  const fastapi = stack.stack.find(s => s.name === 'fastapi');
  assert.ok(fastapi, 'Should detect FastAPI');
  assert.equal(fastapi.category, 'Backend');

  const sqlalchemy = stack.stack.find(s => s.name === 'sqlalchemy');
  assert.ok(sqlalchemy, 'Should detect SQLAlchemy');
  assert.equal(sqlalchemy.category, 'Database');
});

test('F21: inferTechStack — detects Docker from config', () => {
  const info = { dependencies: {} };
  const langs = new Map([['JavaScript', 10]]);
  const stack = inferTechStack(info, langs, { allImports: [] }, { Dockerfile: true });

  const docker = stack.stack.find(s => s.name === 'docker');
  assert.ok(docker, 'Should detect Docker from config');
  assert.equal(docker.category, 'DevOps');
});

test('F21: inferTechStack — confidence scoring', () => {
  const info = { dependencies: { react: '^18.0.0' } };
  const langs = new Map([['JavaScript (React)', 10]]);
  const stack = inferTechStack(info, langs, { allImports: ['react'] }, {});

  const react = stack.stack.find(s => s.name === 'react');
  // dep match (0.5) + lang match (0.3) = 0.8
  assert.ok(react.confidence >= 0.8, `Expected confidence >= 0.8, got ${react.confidence}`);
});

test('F21: inferTechStack — returns empty for plain project', () => {
  const info = { dependencies: {} };
  const langs = new Map([['JavaScript', 5]]);
  const stack = inferTechStack(info, langs, { allImports: [] }, {});

  assert.equal(stack.stack.length, 0);
});

test('F21: formatTechStack — produces valid markdown', () => {
  const info = { dependencies: { react: '^18.0.0', express: '^4.18.0' } };
  const langs = new Map([['JavaScript (React)', 10]]);
  const stack = inferTechStack(info, langs, { allImports: ['react', 'express'] }, {});
  const md = formatTechStack(stack);

  assert.ok(md.includes('# Tech Stack'));
  assert.ok(md.includes('## Frontend'));
  assert.ok(md.includes('## Backend'));
  assert.ok(md.includes('react'));
});

test('F21: inferTechStack — detects Rust frameworks', () => {
  const info = { dependencies: {} };
  const langs = new Map([['Rust', 20]]);
  const stack = inferTechStack(info, langs, { allImports: ['actix-web', 'tokio'] }, {});

  const actix = stack.stack.find(s => s.name === 'actix');
  assert.ok(actix, 'Should detect Actix');
  assert.equal(actix.category, 'Backend');
});

test('F21: inferTechStack — summary strings', () => {
  const info = { dependencies: { react: '^18.0.0' } };
  const langs = new Map([['JavaScript (React)', 5]]);
  const stack = inferTechStack(info, langs, { allImports: ['react'] }, {});

  assert.ok(stack.summary.length > 0);
  assert.ok(stack.summary[0].includes('react'));
  assert.ok(stack.summary[0].includes('Frontend'));
});
