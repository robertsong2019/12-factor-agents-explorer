import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, writeFileSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { detectApiRoutes, formatApiRoutesReport } from '../context-forge.mjs';

function makeFixture() {
  return mkdtempSync(join(tmpdir(), 'cf-api-'));
}

describe('F42: detectApiRoutes — Express', () => {
  it('detects Express GET/POST routes', async () => {
    const dir = makeFixture();
    try {
      writeFileSync(join(dir, 'app.js'), [
        'const express = require("express");',
        'const app = express();',
        'app.get("/users", (req, res) => {});',
        'app.post("/users", (req, res) => {});',
        'app.delete("/users/:id", (req, res) => {});',
      ].join('\n'));
      const result = await detectApiRoutes(dir);
      assert.equal(result.count, 3);
      assert.ok(result.frameworks.includes('express'));
      assert.equal(result.byMethod.GET, 1);
      assert.equal(result.byMethod.POST, 1);
      assert.equal(result.byMethod.DELETE, 1);
    } finally {
      rmSync(dir, { recursive: true });
    }
  });

  it('detects Express Router routes', async () => {
    const dir = makeFixture();
    try {
      mkdirSync(join(dir, 'routes'));
      writeFileSync(join(dir, 'routes', 'products.js'), [
        'const router = require("express").Router();',
        'router.get("/", (req, res) => {});',
        'router.post("/", (req, res) => {});',
        'router.put("/:id", (req, res) => {});',
        'router.patch("/:id", (req, res) => {});',
      ].join('\n'));
      const result = await detectApiRoutes(dir);
      assert.equal(result.count, 4);
      assert.ok(result.frameworks.includes('express'));
      const methods = Object.keys(result.byMethod).sort();
      assert.deepEqual(methods, ['GET', 'PATCH', 'POST', 'PUT']);
    } finally {
      rmSync(dir, { recursive: true });
    }
  });

  it('detects app.all() routes', async () => {
    const dir = makeFixture();
    try {
      writeFileSync(join(dir, 'server.js'), 'app.all("/api/*", middleware);');
      const result = await detectApiRoutes(dir);
      assert.equal(result.count, 1);
      assert.equal(result.routes[0].method, 'ALL');
      assert.equal(result.routes[0].path, '/api/*');
    } finally {
      rmSync(dir, { recursive: true });
    }
  });
});

describe('F42: detectApiRoutes — Python', () => {
  it('detects FastAPI decorators', async () => {
    const dir = makeFixture();
    try {
      writeFileSync(join(dir, 'main.py'), [
        'from fastapi import FastAPI',
        'app = FastAPI()',
        '',
        '@app.get("/items")',
        'def list_items(): pass',
        '',
        '@app.post("/items")',
        'def create_item(): pass',
        '',
        '@app.delete("/items/{item_id}")',
        'def delete_item(item_id): pass',
      ].join('\n'));
      const result = await detectApiRoutes(dir);
      assert.equal(result.count, 3);
      assert.ok(result.frameworks.includes('fastapi'));
      assert.equal(result.byMethod.GET, 1);
      assert.equal(result.byMethod.POST, 1);
      assert.equal(result.byMethod.DELETE, 1);
    } finally {
      rmSync(dir, { recursive: true });
    }
  });

  it('detects Flask @app.route decorators', async () => {
    const dir = makeFixture();
    try {
      writeFileSync(join(dir, 'app.py'), [
        'from flask import Flask',
        'app = Flask(__name__)',
        '',
        '@app.route("/")',
        'def index(): pass',
        '',
        '@app.route("/users/<id>", methods=["GET", "POST"])',
        'def user(id): pass',
      ].join('\n'));
      const result = await detectApiRoutes(dir);
      assert.ok(result.count >= 2);
      assert.ok(result.frameworks.includes('flask'));
    } finally {
      rmSync(dir, { recursive: true });
    }
  });

  it('detects Django URL patterns', async () => {
    const dir = makeFixture();
    try {
      mkdirSync(join(dir, 'myproject'));
      writeFileSync(join(dir, 'myproject', 'urls.py'), [
        'from django.urls import path',
        'urlpatterns = [',
        '    path("", views.index),',
        '    path("articles/<int:year>/", views.year_archive),',
        '    path("api/users/", UsersView.as_view()),',
        ']',
      ].join('\n'));
      const result = await detectApiRoutes(dir);
      assert.ok(result.count >= 3);
      assert.ok(result.frameworks.includes('django'));
    } finally {
      rmSync(dir, { recursive: true });
    }
  });
});

describe('F42: detectApiRoutes — Edge cases', () => {
  it('returns empty for projects with no routes', async () => {
    const dir = makeFixture();
    try {
      writeFileSync(join(dir, 'utils.js'), 'function add(a, b) { return a + b; }');
      const result = await detectApiRoutes(dir);
      assert.equal(result.count, 0);
      assert.deepEqual(result.routes, []);
      assert.deepEqual(result.frameworks, []);
    } finally {
      rmSync(dir, { recursive: true });
    }
  });

  it('respects maxDepth option', async () => {
    const dir = makeFixture();
    try {
      mkdirSync(join(dir, 'a', 'b', 'c'), { recursive: true });
      writeFileSync(join(dir, 'app.js'), 'app.get("/top", handler);');
      writeFileSync(join(dir, 'a', 'b', 'c', 'deep.js'), 'app.get("/deep", handler);');
      const result = await detectApiRoutes(dir, { maxDepth: 1 });
      assert.equal(result.count, 1);
      assert.equal(result.routes[0].path, '/top');
    } finally {
      rmSync(dir, { recursive: true });
    }
  });

  it('respects gitignore patterns', async () => {
    const dir = makeFixture();
    try {
      mkdirSync(join(dir, 'node_modules'));
      writeFileSync(join(dir, 'app.js'), 'app.get("/real", handler);');
      writeFileSync(join(dir, 'node_modules', 'lib.js'), 'app.get("/fake", handler);');
      const result = await detectApiRoutes(dir, { gitignore: ['node_modules'] });
      assert.equal(result.count, 1);
      assert.equal(result.routes[0].path, '/real');
    } finally {
      rmSync(dir, { recursive: true });
    }
  });

  it('skips files larger than maxFileSize', async () => {
    const dir = makeFixture();
    try {
      const padding = 'x'.repeat(200);
      writeFileSync(join(dir, 'app.js'), padding + '\napp.get("/big", handler);');
      const result = await detectApiRoutes(dir, { maxFileSize: 100 });
      assert.equal(result.count, 0);
    } finally {
      rmSync(dir, { recursive: true });
    }
  });

  it('records correct file and line number', async () => {
    const dir = makeFixture();
    try {
      writeFileSync(join(dir, 'server.js'), [
        'const express = require("express");',
        'const app = express();',
        '',
        'app.get("/health", (req, res) => res.json({ ok: true }));',
      ].join('\n'));
      const result = await detectApiRoutes(dir);
      assert.equal(result.routes[0].file, 'server.js');
      assert.equal(result.routes[0].line, 4);
      assert.equal(result.routes[0].method, 'GET');
      assert.equal(result.routes[0].path, '/health');
    } finally {
      rmSync(dir, { recursive: true });
    }
  });

  it('detects routes across multiple frameworks', async () => {
    const dir = makeFixture();
    try {
      writeFileSync(join(dir, 'api.js'), 'app.get("/users", handler);');
      writeFileSync(join(dir, 'views.py'), [
        '@app.route("/page")',
        'def page(): pass',
      ].join('\n'));
      const result = await detectApiRoutes(dir);
      assert.ok(result.frameworks.includes('express'));
      assert.ok(result.frameworks.includes('flask'));
      assert.equal(result.count, 2);
    } finally {
      rmSync(dir, { recursive: true });
    }
  });
});

describe('F43: formatApiRoutesReport', () => {
  it('formats empty result gracefully', () => {
    const report = formatApiRoutesReport({ routes: [], frameworks: [], count: 0, byMethod: {} });
    assert.ok(report.includes('No API routes detected'));
  });

  it('formats null/undefined result gracefully', () => {
    const report = formatApiRoutesReport(null);
    assert.ok(report.includes('No API routes detected'));
  });

  it('includes framework and count in header', () => {
    const data = {
      routes: [{ file: 'app.js', line: 5, method: 'GET', path: '/health', framework: 'express' }],
      frameworks: ['express'],
      count: 1,
      byMethod: { GET: 1 },
    };
    const report = formatApiRoutesReport(data);
    assert.ok(report.includes('express'));
    assert.ok(report.includes('**Total routes:** 1'));
  });

  it('includes method summary table', () => {
    const data = {
      routes: [
        { file: 'a.js', line: 1, method: 'GET', path: '/', framework: 'express' },
        { file: 'a.js', line: 5, method: 'POST', path: '/', framework: 'express' },
        { file: 'a.js', line: 10, method: 'GET', path: '/:id', framework: 'express' },
      ],
      frameworks: ['express'],
      count: 3,
      byMethod: { GET: 2, POST: 1 },
    };
    const report = formatApiRoutesReport(data);
    assert.ok(report.includes('| GET | 2 |'));
    assert.ok(report.includes('| POST | 1 |'));
  });

  it('includes route detail table with file:line', () => {
    const data = {
      routes: [
        { file: 'src/api.js', line: 42, method: 'DELETE', path: '/items/:id', framework: 'express' },
      ],
      frameworks: ['express'],
      count: 1,
      byMethod: { DELETE: 1 },
    };
    const report = formatApiRoutesReport(data);
    assert.ok(report.includes('DELETE'));
    assert.ok(report.includes('/items/:id'));
    assert.ok(report.includes('src/api.js:42'));
    assert.ok(report.includes('express'));
  });
});
