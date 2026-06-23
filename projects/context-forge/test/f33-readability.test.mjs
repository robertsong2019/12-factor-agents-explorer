import { describe, it } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeDocReadability, formatReadabilityReport } from '../context-forge.mjs';

describe('analyzeDocReadability', () => {

  const GOOD_DOC = `# Project Guide

This is a well-structured document. It has clear headings and short paragraphs.

## Installation

First, install the package. Then configure it.

\`\`\`bash
npm install my-package
\`\`\`

## Usage

Here is how to use it. See [the docs](https://example.com) for more.

- Step one
- Step two
- Step three

### Advanced

For advanced usage, check the API reference.
`;

  const NO_HEADING_DOC = `This is a long document that goes on and on without any headings at all. ` +
    `It has lots of words but no structure to help the reader navigate through the content. ` +
    `This makes it hard to scan and understand quickly. The reader has to read every single ` +
    `word to find what they are looking for which is not ideal for documentation. `.repeat(20);

  const LONG_PARAGRAPH_DOC = `# Doc

## Section

${'This is a sentence in a very long paragraph. '.repeat(30)}

## End
`;

  const CODE_HEAVY_DOC = `# API Reference

\`\`\`javascript
${Array.from({ length: 80 }, (_, i) => `const x${i} = ${i};`).join('\n')}
\`\`\`

Done.
`;

  describe('basic analysis', () => {
    it('returns score and grade for good documentation', () => {
      const result = analyzeDocReadability(GOOD_DOC);
      assert.ok(result.score >= 70);
      assert.match(result.grade, /[A-D]/);
    });

    it('returns zero score for empty content', () => {
      const result = analyzeDocReadability('');
      assert.equal(result.score, 0);
      assert.equal(result.grade, 'F');
      assert.ok(result.issues.length > 0);
    });

    it('returns zero score for whitespace-only content', () => {
      const result = analyzeDocReadability('   \n\n  \n');
      assert.equal(result.score, 0);
    });
  });

  describe('heading analysis', () => {
    it('counts headings correctly', () => {
      const doc = '# H1\n\n## H2\n\n### H3\n\nText\n';
      const result = analyzeDocReadability(doc);
      assert.equal(result.metrics.headingCount, 3);
      assert.equal(result.metrics.maxHeadingDepth, 3);
    });

    it('detects heading hierarchy issues', () => {
      const doc = '# H1\n\n### H3 (skipped H2)\n\nText\n';
      const result = analyzeDocReadability(doc);
      assert.ok(result.metrics.hierarchyIssues > 0);
      assert.ok(result.issues.some(i => i.includes('hierarchy')));
    });

    it('reports low heading density for long docs', () => {
      const doc = '# Title\n\n' + 'Word word word.\n'.repeat(300);
      const result = analyzeDocReadability(doc);
      assert.ok(result.metrics.headingDensity < 0.02);
    });
  });

  describe('paragraph analysis', () => {
    it('counts paragraphs', () => {
      const doc = '# Title\n\nFirst paragraph here.\n\nSecond paragraph here.\n\nThird one.\n';
      const result = analyzeDocReadability(doc);
      assert.equal(result.metrics.paragraphCount, 3);
    });

    it('calculates average paragraph length', () => {
      const doc = '# Title\n\nOne two three four five.\n\nOne two three.\n';
      const result = analyzeDocReadability(doc);
      assert.ok(result.metrics.avgParagraphLength > 0);
    });

    it('detects overly long paragraphs', () => {
      const result = analyzeDocReadability(LONG_PARAGRAPH_DOC);
      assert.ok(result.metrics.longestParagraph > 200);
      assert.ok(result.issues.some(i => i.includes('Longest paragraph')));
    });
  });

  describe('sentence analysis', () => {
    it('counts sentences', () => {
      const doc = '# Title\n\nThis is sentence one. This is sentence two. This is sentence three.\n';
      const result = analyzeDocReadability(doc);
      assert.ok(result.metrics.sentenceCount >= 3);
    });

    it('calculates average sentence length', () => {
      const doc = '# Title\n\nThe cat sat. The dog ran. A bird flew.\n';
      const result = analyzeDocReadability(doc);
      assert.ok(result.metrics.avgSentenceLength > 0);
    });
  });

  describe('code block analysis', () => {
    it('counts code blocks', () => {
      const doc = '# Title\n\nText here.\n\n```js\nconst x = 1;\n```\n\nMore text.\n';
      const result = analyzeDocReadability(doc);
      assert.equal(result.metrics.codeBlockCount, 1);
      assert.ok(result.metrics.codeBlockLines > 0);
    });

    it('calculates code ratio', () => {
      const result = analyzeDocReadability(CODE_HEAVY_DOC);
      assert.ok(result.metrics.codeRatio > 0.5);
    });

    it('flags excessive code ratio', () => {
      const result = analyzeDocReadability(CODE_HEAVY_DOC);
      assert.ok(result.issues.some(i => i.includes('Code blocks')));
    });
  });

  describe('link analysis', () => {
    it('counts markdown links', () => {
      const doc = '# Title\n\nSee [docs](https://example.com) and [code](https://github.com/x/y).\n';
      const result = analyzeDocReadability(doc);
      assert.equal(result.metrics.linkCount, 2);
    });

    it('flags missing links in long docs', () => {
      const doc = '# Title\n\n' + 'Word '.repeat(400);
      const result = analyzeDocReadability(doc);
      assert.ok(result.issues.some(i => i.includes('no links')));
    });
  });

  describe('list analysis', () => {
    it('counts list items', () => {
      const doc = '# Title\n\n- Item one\n- Item two\n- Item three\n';
      const result = analyzeDocReadability(doc);
      assert.equal(result.metrics.listCount, 3);
    });
  });

  describe('scoring', () => {
    it('gives high score to well-structured doc', () => {
      const result = analyzeDocReadability(GOOD_DOC);
      assert.ok(result.score >= 80, `Expected score >= 80, got ${result.score}`);
    });

    it('penalizes missing headings in long docs', () => {
      const result = analyzeDocReadability(NO_HEADING_DOC);
      assert.ok(result.issues.some(i => i.includes('no headings')), 'Should flag missing headings');
    });

    it('clamps score to 0-100', () => {
      const badDoc = '# H1\n\n### H3\n\n###### H6\n\n' + 'Word '.repeat(500) + '\n\n' + 'Long sentence '.repeat(50) + '.\n';
      const result = analyzeDocReadability(badDoc);
      assert.ok(result.score >= 0 && result.score <= 100);
    });

    it('assigns correct grade boundaries', () => {
      // Grade A: score >= 90
      assert.equal(analyzeDocReadability(GOOD_DOC).grade <= 'B', true);
      // Grade F: score < 60
      assert.equal(analyzeDocReadability('').grade, 'F');
    });
  });
});

describe('formatReadabilityReport', () => {
  it('formats a full report with metrics table', () => {
    const analysis = analyzeDocReadability('# Title\n\nSome text here.\n');
    const report = formatReadabilityReport(analysis);
    assert.match(report, /Documentation Readability/);
    assert.match(report, /Score.*\/100/);
    assert.match(report, /Grade.*[A-F]/);
    assert.match(report, /\| Metric/);
    assert.match(report, /\| Words/);
  });

  it('includes issues when present', () => {
    const analysis = {
      score: 50,
      grade: 'F',
      metrics: { wordCount: 0, headingCount: 0, headingDensity: 0, maxHeadingDepth: 0, hierarchyIssues: 0, paragraphCount: 0, avgParagraphLength: 0, longestParagraph: 0, sentenceCount: 0, avgSentenceLength: 0, codeBlockCount: 0, codeBlockLines: 0, codeRatio: 0, linkCount: 0, linkDensity: 0, listCount: 0 },
      issues: ['Test issue'],
      suggestions: ['Test suggestion'],
    };
    const report = formatReadabilityReport(analysis);
    assert.match(report, /Test issue/);
    assert.match(report, /Test suggestion/);
    assert.match(report, /💡/);
  });

  it('does not include issues section when clean', () => {
    const analysis = {
      score: 95,
      grade: 'A',
      metrics: { wordCount: 100, headingCount: 3, headingDensity: 0.05, maxHeadingDepth: 2, hierarchyIssues: 0, paragraphCount: 3, avgParagraphLength: 30, longestParagraph: 50, sentenceCount: 10, avgSentenceLength: 10, codeBlockCount: 1, codeBlockLines: 5, codeRatio: 0.1, linkCount: 2, linkDensity: 0.05, listCount: 3 },
      issues: [],
      suggestions: [],
    };
    const report = formatReadabilityReport(analysis);
    assert.doesNotMatch(report, /\*\*Issues/);
    assert.doesNotMatch(report, /\*\*Suggestions/);
  });
});
